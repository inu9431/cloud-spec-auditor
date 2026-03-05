# CostCutter

> AWS Key 한 번 등록으로 클라우드 과스펙을 자동 감지하고 AWS / GCP / Azure 3사 비교 기반 절감 솔루션을 제공하는 FinOps 서비스

---

## 목차

- [서비스 소개](#서비스-소개)
- [기술 스택](#기술-스택)
- [아키텍처](#아키텍처)
- [ELT 파이프라인](#elt-파이프라인)
- [데이터 흐름](#데이터-흐름)
- [API 목록](#api-목록)
- [주요 설계 결정](#주요-설계-결정)
- [시스템 고려사항](#시스템-고려사항)
- [리전 매핑](#리전-매핑)
- [시작하기](#시작하기)

---

## 서비스 소개

AWS를 사용하는 스타트업 팀을 대상으로, 실제 사용 데이터를 기반으로 과스펙 인스턴스를 자동 감지하고 3사 가격 비교를 통해 최적의 절감 방안을 제시합니다.

```
AWS Key 1회 등록
      ↓
EC2 + Cost Explorer + Compute Optimizer 자동 수집 (24h)
      ↓
AWS / GCP / Azure 3사 가격 자동 비교 (주 1회)
      ↓
Gemini AI 과스펙 진단 + 절감 추천 자동 생성
      ↓
유저: 대시보드에서 결과 확인
```

**핵심 포인트**
- 유저는 AWS Key만 등록하면 이후 모든 과정이 자동화
- 단순 가격 비교가 아닌 실제 사용률(Compute Optimizer) 기반 진단
- 3사 동일 스펙 비교로 클라우드 전환 시 절감 효과 수치 제시

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| 백엔드 | Django 6.0, Django REST Framework |
| 데이터베이스 | PostgreSQL |
| AI | Gemini API (gemini-2.5-flash) |
| 파이프라인 오케스트레이션 | Prefect |
| 비동기 큐 | django-q2 |
| 클라우드 연동 | AWS boto3, GCP Cloud Billing API, Azure Retail Prices API |
| 인증 | JWT (djangorestframework-simplejwt) |
| 캐시 | Django FileBasedCache |
| 패키지 관리 | uv |

---

## 아키텍처

### 계층 분리

서비스 레이어와 데이터 레이어를 명확하게 분리하고, 두 레이어가 `UserInventory`, `CloudService` 모델에서 만나는 구조입니다.

```
┌──────────────────────────────────────────┐
│           apps/  (서비스 레이어)            │
│   REST API 서빙 / 유저 요청 처리 / 모델      │
└─────────────────┬────────────────────────┘
                  │  UserInventory, CloudService (공유 모델)
                  │  pipeline이 적재 → apps가 API로 서빙
┌─────────────────┴────────────────────────┐
│          pipeline/  (데이터 레이어)         │
│   외부 API 수집 / ELT / Raw 원본 보존       │
└──────────────────────────────────────────┘
          │
    apps/core/adapters/  (공유 어댑터)
    AWS / GCP / Azure / Gemini SDK 호출
```

### 프로젝트 구조

```
cloud-spec-auditor/
│
├── apps/
│   ├── core/               - 공통 어댑터, DTO, 유틸, 예외
│   │   ├── adapters/       - aws_adapter.py, cloud_price_adapter.py, gemini_adapter.py
│   │   ├── dto/            - cloud_service_dto.py, inventory_dto.py
│   │   └── utils/          - region_mapper.py (3사 리전 정규화)
│   ├── costs/              - 3사 가격 비교 API
│   ├── inventories/        - 인벤토리 CRUD API
│   ├── recommendations/    - AI 추천 API
│   └── users/              - 유저, JWT, CloudCredential
│
├── pipeline/
│   ├── raw/                - RawEC2Snapshot, RawPriceSnapshot (Append-Only)
│   ├── flows/
│   │   └── inventory_flow.py   - Prefect @flow 오케스트레이션
│   └── tasks/
│       ├── extract/aws.py      - @task AWS API 호출 + 캐시
│       ├── transform/
│       │   ├── normalize.py    - @task 리전 정규화, DTO 변환
│       │   └── validate.py     - @task 비정상값 감지, Prefect 로그
│       └── load/
│           ├── raw.py          - @task RawSnapshot Append-Only 저장
│           ├── inventory.py    - @task UserInventory upsert
│           └── prices.py       - @task 가격 검증 + CloudService upsert
│
└── costcut/                - Django 설정
```

---

## ELT 파이프라인

### ETL이 아닌 ELT를 선택한 이유

**Raw 원본을 먼저 저장(Load)**하고 이후에 변환(Transform)하는 구조입니다.

| | ETL | CostCutter (ELT) |
|---|---|---|
| 순서 | Extract → Transform → Load | Extract → **Load(raw)** → Transform → Load |
| 원본 보관 | 변환 후 버림 | RawSnapshot에 원본 영구 보존 |
| Backfill | transform 로직 변경 시 재수집 필요 | raw payload로 재처리 가능 |

> AWS API 응답 구조가 바뀌거나 transform 로직에 버그가 생겨도, raw 원본이 있으므로 **서비스 중단 없이 로직만 수정해 Backfill 가능**

### ELT 흐름

```
[E]  extract/aws.py
     AWS API 4개 조합 호출 + 레이어별 캐시
     ├ EC2 describe_instances()          → 실행 중인 인스턴스 목록  (캐시 1h)
     ├ Cost Explorer get_cost_and_usage() → 이번 달 실제 청구 비용 (캐시 24h)
     ├ Compute Optimizer                 → 14일 분석 기반 과스펙 판단 (캐시 12h)
     └ describe_instance_types()         → vcpu, memory_gb 동적 조회 (캐시 7일)

[L-raw]  load/raw.py
     raw dict → RawEC2Snapshot.create()
     SHA-256 payload_hash 기반 중복 방지 (Append-Only)

[T]  transform/normalize.py
     RawSnapshot.payload → EC2InventoryDTO 변환
     ap-northeast-2 → KR 리전 정규화

[T]  transform/validate.py
     vcpu=0 / memory=0 / cost > 10,000 등 비정상값 필터링
     이상값은 Prefect UI에 warning 로그 기록

[L-mart]  load/inventory.py
     EC2InventoryDTO → UserInventory.update_or_create()
```

### Raw 테이블 설계 원칙

- **Append-Only**: create만 사용, update/upsert 금지
- **Hash 기반 중복 제거**: payload_hash(SHA-256) 동일하면 저장 생략
- **Retention 계획**: Hot(3개월 이내 PostgreSQL) / Cold(3개월 이후 S3 아카이빙)

### Prefect 오케스트레이션

각 ELT 단계를 `@task`로, 전체 흐름을 `@flow`로 감싸 Prefect UI에서 단계별 실행 이력과 경고 로그를 확인할 수 있습니다.

```python
@flow(name="sync-user-inventory")
def sync_user_inventory(credential_id):
    raw_data    = extract_ec2_instances(credential)    # @task E
    snapshot    = save_raw_ec2(credential, raw_data)   # @task L-raw
    dtos        = normalize_inventory(snapshot)         # @task T
    dtos        = validate_inventory(dtos)              # @task T
    inventories = load_inventory(credential.user, dtos) # @task L-mart
    _run_audit_for_inventories(inventories)

@flow(name="sync-cloud-prices")          # 주 1회 자동
def sync_cloud_prices():
    # 3사 가격 ELT: fetch → save_raw_price → validate_prices → load_prices
```

---

## 데이터 흐름

### 유저가 AWS Key를 등록했을 때 전체 흐름

#### Step 1 — AWS Key 등록
```
POST /api/users/credentials/
  └ CloudCredential DB 저장
```

#### Step 2 — 자동 수집 (24h마다 Prefect 스케줄)
```
extract_ec2_instances(credential)
  ├ EC2 API    → i-abc123, t3.medium, ap-northeast-2
  ├ Cost Explorer → $45.2/월
  ├ Compute Optimizer → cpu_usage_avg: 12.5%, OVER_PROVISIONED
  └ describe_instance_types → vcpu: 2, memory: 4GB
      ↓
save_raw_ec2()
  └ RawEC2Snapshot에 원본 JSON 저장 (hash 중복 방지)
      ↓
normalize_inventory() → validate_inventory()
  └ EC2InventoryDTO 변환 + 비정상값 필터링
      ↓
load_inventory()
  └ UserInventory.update_or_create()
```

#### Step 3 — AI 분석 자동 실행
```
UserInventory 저장 완료 → audit 자동 트리거
  ├ UserInventory 조회  → t3.medium / $45.2/월 / CPU 12.5%
  ├ CloudService 3사 비교
  │   AWS  t3.medium  $30/월
  │   GCP  e2-medium  $24/월
  │   Azure B2s       $30/월
  └ Gemini API 호출
      입력: 현재 스펙 + 실사용률 + 3사 비교 결과
      출력: "CPU 12.5% 과스펙. t3.small 전환 시 $22/월.
             GCP e2-small 전환 시 $18/월로 추가 절감 가능."
        ↓
      Recommendation + RecommendationItem DB 저장
```

#### Step 4 — 유저 확인
```
GET /api/recommendations/
→ 현재 비용: $45.2/월
  절감 가능: $27.2/월 (60%)
  추천 1: t3.small 다운그레이드 → $22/월
  추천 2: GCP e2-small 전환    → $18/월
```

---

## API 목록

### 인증
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/users/signup/` | 회원가입 |
| POST | `/api/users/login/` | 로그인 (JWT 발급) |
| POST | `/api/users/logout/` | 로그아웃 |

### AWS 연동
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/users/credentials/` | AWS Key 직접 입력 |
| POST | `/api/users/credentials/csv/` | IAM CSV 파일 업로드 |
| GET | `/api/users/credentials/` | 등록된 자격증명 목록 |

### 인벤토리
| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/inventories/` | 내 인스턴스 목록 |
| POST | `/api/inventories/sync/` | 수동 재수집 트리거 (즉시 202 반환) |

### 비용 비교
| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/costs/instance-compare/` | 3사 동일 스펙 가격 비교 |
| POST | `/api/costs/sync/aws/` | AWS 가격 수동 최신화 |
| POST | `/api/costs/sync/gcp/` | GCP 가격 수동 최신화 |
| POST | `/api/costs/sync/azure/` | Azure 가격 수동 최신화 |

### AI 추천
| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/api/recommendations/audit/` | AI 진단 실행 |
| GET | `/api/recommendations/` | 추천 결과 조회 |

---

## 주요 설계 결정

### 왜 CloudWatch 대신 Compute Optimizer?

CloudWatch를 직접 호출하면 유저 수 증가 시 **유저의 AWS 계정에서 API 비용이 선형으로 증가**합니다.

Compute Optimizer는 AWS가 내부적으로 14일치 지표를 분석해 라이트사이징 추천을 제공하며, 별도 호출 비용이 없습니다. 유저가 자신의 AWS 계정에서 Compute Optimizer를 활성화(무료, 1회 설정)하면 됩니다.

### 왜 ETL이 아닌 ELT?

API 응답 구조 변경이나 transform 로직 버그 발생 시, ETL은 재수집이 필요합니다. ELT는 Raw 원본을 보존하므로 **서비스 중단 없이 로직만 수정해 Backfill**할 수 있습니다.

### 왜 Airflow 대신 Prefect?

- 경량 Python-native 도구로 1인 개발 환경에 적합
- 추가 인프라(Docker, Redis 등) 없이 로컬 UI 실행 가능
- `@task` / `@flow` 데코레이터만으로 기존 함수를 DAG으로 전환 가능

### 인스턴스 스펙 하드코딩 제거

기존 `EC2_INSTANCE_SPECS` 딕셔너리(18개 타입 한정) 대신 AWS `describe_instance_types()` API를 사용해 **모든 인스턴스 타입의 스펙을 동적으로 조회**합니다. t4g, c6i, m7g 등 신규 타입도 자동 지원됩니다.

---

## 시스템 고려사항

프로덕션 수준에서 발생할 수 있는 리스크와 대응 방향을 정리합니다.

### 1. 보안 — AWS Key 암호화

현재 `CloudCredential` 모델에 AWS Key를 평문으로 저장합니다.

| 위험 | 대응 방향 |
|---|---|
| DB 유출 시 유저 AWS 계정 전체 노출 | AWS KMS / django-encrypted-fields로 저장 시 AES-256 암호화 |
| 로그에 Key 노출 가능 | 로깅 필터에서 `aws_access_key_id` 마스킹 |

> 유저의 AWS 계정에 접근하는 서비스이므로 Key 보안은 MVP 이후 가장 먼저 적용해야 할 항목입니다.

### 2. 멀티 클라우드 확장 (GCP / Azure 파이프라인)

현재 파이프라인은 AWS 전용입니다. GCP / Azure 인스턴스 수집을 추가하려면:

- `CloudCredential`에 GCP / Azure 인증 정보 필드 추가 (스키마는 이미 대비됨)
- `pipeline/tasks/extract/gcp.py`, `extract/azure.py` 모듈 추가
- `pipeline/flows/inventory_flow.py`에 provider 분기 추가
- `RawEC2Snapshot` → `RawInstanceSnapshot`으로 범용화

### 3. 파이프라인 실패 대응

Prefect `@task`에 자동 재시도와 실패 격리를 적용합니다.

```python
@task(retries=3, retry_delay_seconds=60)
def extract_ec2_instances(credential): ...
```

| 실패 패턴 | 대응 |
|---|---|
| 일시적 네트워크 오류 | `retries=3, retry_delay_seconds=60` |
| 특정 유저만 실패 | Prefect UI에서 해당 Flow Run만 재실행 |
| 전체 Flow 실패 | Dead Letter Queue (django-q2 실패 태스크 별도 큐) |

### 4. LLM 역할 분리

Gemini API는 **자연어 설명 생성에만** 사용하고, 수치 계산은 Python에서 처리합니다.

```
Python: 절감액 계산 ($45.2 - $22 = $23.2/월)
Gemini: "t3.medium의 CPU 사용률이 12.5%로 과스펙입니다. t3.small 전환 시 월 $23 절감 가능합니다."
```

Gemini API 장애 시 수치 데이터는 정상 서빙하고, AI 설명 부분만 fallback 메시지로 대체합니다.

### 5. 성능 — 대용량 대응

| 병목 구간 | 현재 | 개선 방향 |
|---|---|---|
| AWS API 호출 | 유저당 순차 호출 | `asyncio.gather()` 또는 `ThreadPoolExecutor` 병렬화 |
| DB 적재 | 인스턴스별 `update_or_create()` 루프 | `bulk_create(update_conflicts=True)` |
| Raw 테이블 증가 | PostgreSQL 단일 테이블 | 3개월 이후 S3 아카이빙 (Retention 정책) |

### 6. AWS 권한 부족 대응

Compute Optimizer나 Cost Explorer가 비활성화된 경우, 전체 sync가 실패합니다.

- **Credential Validation API**: Key 등록 시 권한을 사전 검증 (`sts:GetCallerIdentity`)
- **Graceful Degradation**: Compute Optimizer 미활성화 시 `cpu_usage_avg=None`으로 처리하고 나머지 데이터는 정상 적재
- 온보딩 가이드에 Compute Optimizer 활성화 방법 안내

### 7. AWS API Rate Limit 대응

Cost Explorer / Compute Optimizer는 계정당 호출 한도가 있습니다.

- `describe_instance_types()` : 7일 캐시로 반복 호출 차단
- Cost Explorer : 24h 캐시
- Compute Optimizer : 12h 캐시
- 429 응답 시 Prefect `retry_delay_seconds` exponential backoff 적용

### 8. 비용 데이터 지연 UX

AWS Cost Explorer는 실제 사용 후 **최대 24시간 지연**으로 데이터가 반영됩니다.

- `UserInventory`에 `cost_updated_at` 필드 추가
- API 응답에 `"cost_updated_at": "2025-03-04T12:00:00Z"` 포함
- 프론트엔드에서 "비용 데이터는 최대 24시간 지연될 수 있습니다" 안내

---

## 리전 매핑

3사의 서로 다른 리전 체계를 `NormalizedRegion`으로 통일해 동일 기준 가격 비교를 가능하게 합니다.

| NormalizedRegion | AWS | GCP | Azure |
|---|---|---|---|
| KR | ap-northeast-2 | asia-northeast3 | koreacentral |
| JP | ap-northeast-1 | asia-northeast1 | japaneast |
| US_EAST | us-east-1 | us-east1 | eastus |

---

## 시작하기

```bash
# 1. 의존성 설치
uv sync

# 2. 환경변수 설정
cp .env.example .env

# 3. DB 마이그레이션
python manage.py migrate

# 4. Prefect 서버 실행 (터미널 1)
prefect server start
# UI: http://localhost:4200

# 5. Prefect 스케줄 등록 (터미널 2, 최초 1회)
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
python pipeline/flows/inventory_flow.py

# 6. django-q2 워커 실행 (터미널 3)
python manage.py qcluster

# 7. 서버 실행 (터미널 4)
python manage.py runserver
```

### 검증 순서

```bash
# AWS Key 등록
POST /api/users/credentials/csv/

# 수동 수집 트리거
POST /api/inventories/sync/

# AI 진단 실행
POST /api/recommendations/audit/  { "inventory_id": 1 }

# 추천 결과 확인
GET /api/recommendations/
```
