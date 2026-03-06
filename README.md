# CostCutter

> AWS Key 한 번 등록으로 클라우드 과스펙을 자동 감지하고 AWS / GCP / Azure 3사 비교 기반 절감 솔루션을 제공하는 FinOps 서비스

---

## 목차

- [서비스 소개](#서비스-소개)
- [기술 스택](#기술-스택)
- [시스템 아키텍처](#시스템-아키텍처)
- [데이터 파이프라인 — Bronze / Silver / Gold](#데이터-파이프라인--bronze--silver--gold)
- [전체 데이터 흐름](#전체-데이터-흐름)
- [보안 설계](#보안-설계)
- [API 목록](#api-목록)
- [아키텍처 의사결정](#아키텍처-의사결정)
- [시스템 고려사항 및 트러블슈팅](#시스템-고려사항-및-트러블슈팅)
- [대용량 파이프라인 부하 분석](#대용량-파이프라인-부하-분석)
- [리전 매핑](#리전-매핑)
- [시작하기](#시작하기)

---

## 서비스 소개

AWS를 사용하는 스타트업 팀을 대상으로, 실제 사용 데이터 기반으로 과스펙 인스턴스를 자동 감지하고 3사 가격 비교를 통해 최적의 절감 방안을 제시합니다.

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
- 단순 가격 비교가 아닌 실제 사용률(Compute Optimizer 14일 분석) 기반 진단
- 3사 동일 스펙 비교로 클라우드 전환 시 절감 효과 수치 제시

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| 백엔드 | Django 6.0, Django REST Framework |
| 데이터베이스 | PostgreSQL |
| AI | Gemini API (gemini-2.5-flash) |
| 파이프라인 오케스트레이션 | Prefect (`@task` / `@flow` / 스케줄 / UI) |
| 비동기 큐 | django-q2 |
| 클라우드 연동 | AWS boto3, GCP Cloud Billing API, Azure Retail Prices API |
| 인증 | JWT (djangorestframework-simplejwt) |
| 보안 | django-encrypted-model-fields (Fernet 암호화), DRF Throttle |
| 캐시 | Django FileBasedCache |
| 패키지 관리 | uv |

---

## 시스템 아키텍처

### 계층 분리 원칙

서비스 레이어와 데이터 레이어를 명확하게 분리하고, 두 레이어가 `UserInventory`, `CloudService` 모델에서 만나는 구조입니다.

```
┌──────────────────────────────────────────────┐
│  Service Layer  (apps/)                      │
│  유저 요청 → Serializer → Service → Model    │
│  REST API 서빙 / JWT 인증 / CRUD             │
└──────────────────┬───────────────────────────┘
                   │  공유 모델
                   │  UserInventory — pipeline이 적재, apps가 서빙
                   │  CloudService  — pipeline이 적재, apps가 비교 API로 서빙
┌──────────────────┴───────────────────────────┐
│  Pipeline Layer  (pipeline/)                 │
│  외부 API → Extract → Load(raw) →            │
│  Transform → Load(mart)                      │
│  Prefect 오케스트레이션 / 스케줄 수집         │
└──────────────────────────────────────────────┘
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
│   ├── raw/                - RawEC2Snapshot, RawPriceSnapshot (Append-Only Bronze)
│   ├── flows/
│   │   └── inventory_flow.py   - Prefect @flow 오케스트레이션
│   └── tasks/
│       ├── extract/aws.py      - @task AWS API 호출 + 캐시
│       ├── transform/
│       │   ├── normalize.py    - @task 리전 정규화, DTO 변환
│       │   └── validate.py     - @task 비정상값 감지, Prefect 로그
│       └── load/
│           ├── raw.py          - @task RawSnapshot Append-Only 저장
│           ├── inventory.py    - @task UserInventory upsert (Silver)
│           └── prices.py       - @task 가격 검증 + CloudService upsert
│
├── docs/
│   ├── ARCHITECTURE.md     - 상세 아키텍처 설계
│   ├── DECISIONS.md        - 아키텍처 의사결정 기록 (ADR)
│   ├── TROUBLESHOOTING.md  - 트러블슈팅 기록 + 대용량 부하 분석
│   └── ONBOARDING_IAM.md   - AWS IAM 최소 권한 설정 가이드
│
└── costcut/                - Django 설정
```

---

## 데이터 파이프라인 — Bronze / Silver / Gold

### 왜 ETL이 아닌 ELT인가?

**원본 데이터를 먼저 저장(Load)**하고 이후에 변환(Transform)하는 구조입니다.

| | ETL | CostCutter (ELT) |
|---|---|---|
| 순서 | Extract → Transform → Load | Extract → **Load(raw)** → Transform → Load |
| 원본 보관 | 변환 후 소실 | Bronze 테이블에 원본 영구 보존 |
| Backfill | Transform 로직 변경 시 재수집 필요 | Raw payload로 언제든 재처리 가능 |

> API 응답 구조가 바뀌거나 AI 분석 프롬프트가 변경되어도, raw 원본이 있으므로 **서비스 중단 없이 로직만 수정해 Backfill 가능**

### ELT 흐름

```
[E]  extract/aws.py
     AWS API 4개 조합 호출 + 레이어별 캐시
     ├ EC2 describe_instances()           → 실행 중인 인스턴스 목록  (캐시 1h)
     ├ Cost Explorer get_cost_and_usage() → 이번 달 실제 청구 비용  (캐시 24h)
     ├ Compute Optimizer                  → 14일 분석 기반 과스펙 판단 (캐시 12h)
     └ describe_instance_types()          → vcpu, memory_gb 동적 조회 (캐시 7일)

[L-raw]  load/raw.py  ← Bronze Layer
     raw dict → RawEC2Snapshot.create()
     SHA-256 payload_hash 기반 중복 방지 (Append-Only)

[T]  transform/normalize.py
     RawSnapshot.payload → EC2InventoryDTO 변환
     ap-northeast-2 → KR 리전 정규화

[T]  transform/validate.py
     vcpu=0 / memory=0 / cost > 10,000 등 비정상값 필터링
     이상값은 Prefect UI에 warning 로그 기록

[L-mart]  load/inventory.py  ← Silver Layer
     EC2InventoryDTO → UserInventory.update_or_create()
```

### 데이터 계층 구조

| 계층 | 테이블 | 쓰기 방식 | 목적 |
|---|---|---|---|
| Bronze (Raw) | RawEC2Snapshot, RawPriceSnapshot | Append-Only | 원본 보존, Backfill |
| Silver (Mart) | UserInventory, CloudService | update_or_create | 서비스 서빙용 정제 데이터 |
| Gold (Analytics) | Recommendation, RecommendationItem | create | AI 분석 결과 |

### Raw 테이블 설계 원칙

- **Append-Only**: create만 사용, update/upsert 금지 — 특정 시점 데이터 재처리 보장
- **Hash 기반 중복 제거**: payload_hash(SHA-256) 동일하면 저장 생략 — 의미 없는 I/O 제거
- **Retention**: Hot(3개월 이내 PostgreSQL) / Cold(3개월 이후 S3 아카이빙)

### Prefect 오케스트레이션

각 ELT 단계를 `@task`로, 전체 흐름을 `@flow`로 감싸 Prefect UI(localhost:4200)에서 단계별 실행 이력과 경고 로그를 확인합니다.

```python
@flow(name="sync-user-inventory")   # 24h 자동 스케줄
def sync_user_inventory(credential_id):
    raw_data    = extract_ec2_instances(credential)    # @task E
    snapshot    = save_raw_ec2(credential, raw_data)   # @task L-raw (Bronze)
    dtos        = normalize_inventory(snapshot)         # @task T
    dtos        = validate_inventory(dtos)              # @task T
    inventories = load_inventory(credential.user, dtos) # @task L-mart (Silver)
    _run_audit_for_inventories(inventories)             # Gold

@flow(name="sync-cloud-prices")     # 주 1회 자동
def sync_cloud_prices():
    # 3사 가격 ELT: fetch → save_raw_price → validate_prices → load_prices
```

---

## 전체 데이터 흐름

### Step 1 — 백엔드 검증 (Service Layer)

```
Client: AWS Credential 입력
  → Django URLs → DRF Serializer (유효성 검사)
  → ORM: CloudCredential 저장 (암호화 필드)
```

### Step 2 — 자동 수집 (Pipeline Layer, 24h)

```
Prefect Scheduler 트리거
  → extract_ec2_instances(credential)
  │   ├ EC2 API    → i-abc123, t3.medium, ap-northeast-2
  │   ├ Cost Explorer → $45.2/월
  │   ├ Compute Optimizer → cpu_usage_avg: 12.5%, OVER_PROVISIONED
  │   └ describe_instance_types → vcpu: 2, memory: 4GB
  ↓
  → save_raw_ec2()  [Bronze: Append-Only + Hash 중복 제거]
  ↓
  → normalize() → validate()  [DTO 변환 + 비정상값 필터]
  ↓
  → load_inventory()  [Silver: UserInventory.update_or_create()]
```

### Step 3 — AI 분석 (Gold Layer)

```
UserInventory 저장 완료 → audit 트리거
  ├ UserInventory 조회  → t3.medium / $45.2/월 / CPU 12.5%
  ├ CloudService 3사 비교
  │   AWS  t3.medium  $30/월
  │   GCP  e2-medium  $24/월
  │   Azure B2s       $30/월
  │
  ├ Python: 절감액 계산 ($45.2 - $22 = $23.2/월)  ← LLM에게 숫자 계산 위임하지 않음
  └ Gemini: 설명 생성
      "CPU 12.5% 과스펙. t3.small 전환 시 $23/월 절감.
       GCP e2-small 전환 시 추가 절감 가능."
        ↓
      Recommendation + RecommendationItem 저장 (Gold)
```

### Step 4 — 유저 확인

```
GET /api/recommendations/
→ 현재 비용: $45.2/월
  절감 가능: $27.2/월 (60%)
  추천 1: t3.small 다운그레이드 → $22/월
  추천 2: GCP e2-small 전환    → $18/월
```

---

## 보안 설계

### AWS Key 암호화

`CloudCredential` 모델의 민감 필드를 `django-encrypted-model-fields` (Fernet 대칭 암호화)로 저장합니다. DB 덤프가 유출되어도 암호화 키 없이는 복호화 불가능합니다.

**암호화 대상 필드:**
- `aws_access_key_id` / `aws_secret_access_key`
- `gcp_service_account_json`
- `azure_client_secret`

### API 남용 방지 (DRF Throttle)

봇이 sync/audit를 반복 호출하면 **유저 AWS 계정에서 Cost Explorer API 비용이 발생**하고 Gemini API 비용이 선형으로 증가합니다. 단순 서버 보호가 아닌 고객 보호 차원의 설계입니다.

| 엔드포인트 | 기준 | 제한 | 이유 |
|---|---|---|---|
| `POST /api/users/login/` | IP | 10회/분 | brute force 차단 |
| `POST /api/users/signup/` | IP | 10회/시간 | 계정 대량 생성 차단 |
| `POST /api/inventories/sync/` | 유저 | 1회/10분 | 유저 AWS 비용 + 큐 폭발 방지 |
| `POST /api/recommendations/audit/` | 유저 | 1회/5분 | Gemini API 비용 방지 |
| `POST /api/costs/sync/*/` | 전역 | 1회/1시간 | 가격 DB는 공유 자원 |

### IAM 최소 권한 원칙

유저에게 아래 4개 Action만 허용하도록 온보딩 가이드에서 안내합니다. (`docs/ONBOARDING_IAM.md`)

```json
{
  "Action": [
    "ec2:DescribeInstances",
    "ec2:DescribeInstanceTypes",
    "ce:GetCostAndUsage",
    "compute-optimizer:GetEC2InstanceRecommendations"
  ]
}
```

키 등록 후 `POST /api/users/credentials/<pk>/test/`로 권한을 즉시 검증합니다.

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
| POST | `/api/users/credentials/<pk>/test/` | 권한 검증 (ec2 / cost_explorer / compute_optimizer) |

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

## 아키텍처 의사결정

자세한 내용은 `docs/DECISIONS.md` 참고

### 왜 CloudWatch 대신 Compute Optimizer?

CloudWatch를 직접 호출하면 유저 수 증가 시 **유저의 AWS 계정에서 API 비용이 선형으로 증가**합니다.

Compute Optimizer는 AWS가 내부적으로 14일치 지표를 분석해 라이트사이징 추천을 제공하며, 별도 호출 비용이 없습니다. 유저는 자신의 AWS 계정에서 Compute Optimizer를 1회 활성화(무료)하면 됩니다.

### 왜 ETL이 아닌 ELT?

AI Audit 프롬프트나 정규화 로직이 바뀌었을 때 ETL은 재수집이 필요합니다. ELT는 Raw 원본을 보존하므로 **서비스 중단 없이 로직만 수정해 Backfill**할 수 있습니다.

### 왜 Airflow 대신 Prefect?

- 1인 개발 환경에서 Airflow는 메타DB, 웹서버, 스케줄러 등 별도 인프라가 과도함
- `@task` / `@flow` 데코레이터만으로 기존 함수를 DAG으로 전환 가능
- `prefect server start` 한 줄로 로컬 UI(localhost:4200) 실행 — 별도 Docker 불필요

### 왜 인스턴스 스펙을 하드코딩하지 않는가?

기존 `EC2_INSTANCE_SPECS` 딕셔너리(18개 타입 한정) 대신 AWS `describe_instance_types()` API를 사용해 **모든 인스턴스 타입의 스펙을 동적으로 조회**합니다. t4g, c6i, m7g 등 신규 타입도 자동 지원됩니다.

### 왜 sync/audit에 Throttle이 필요한가?

API Rate Limit은 서버 보호만이 목적이 아닙니다. sync 엔드포인트는 유저 AWS 계정의 Cost Explorer를 호출하기 때문에, 봇이 반복 호출하면 **고객의 AWS 계정에서 비용이 발생**합니다. 고객 보호 차원에서 유저별 쿨다운이 필요합니다.

---

## 시스템 고려사항 및 트러블슈팅

자세한 내용은 `docs/TROUBLESHOOTING.md` 참고

### 발견한 문제와 해결 방향

| 문제 | 원인 | 해결 방향 | 상태 |
|---|---|---|---|
| 원본 데이터 부재 → Backfill 불가 | ETL 구조, 가공 후 원본 소실 | ELT 전환 + Bronze Raw 테이블 도입 | ✅ 완료 |
| AWS Key 평문 저장 | 모델 필드 타입 미적용 | `django-encrypted-model-fields` | 구현 예정 |
| `get_monthly_cost()` 예외 시 전체 파이프라인 실패 | AccessDeniedException 구분 없이 raise | AccessDeniedException → 0.0 반환 + warning | 구현 예정 |
| 인스턴스 1개 실패 시 전체 실패 | Partial Failure 처리 없음 | 인스턴스별 try/except + skip | 구현 예정 |
| sync 남용 시 유저 AWS 비용 발생 | Rate Limit 없음 | DRF Throttle (유저별 1회/10분) | 구현 예정 |
| Compute Optimizer 순차 호출 | 인스턴스별 개별 API 호출 | ARN 배열로 1회 호출 통합 | 구현 예정 |

### 파이프라인 Graceful Degradation 설계

권한이 부족한 AWS Key를 등록해도 파이프라인이 멈추지 않도록 설계합니다.

```
EC2 권한 없음 → 수집 자체 불가 (필수 권한, 에러 반환)
Cost Explorer 권한 없음 → monthly_cost=0.0으로 처리, 나머지 정상 수집
Compute Optimizer 미활성화 → cpu_usage_avg=None으로 처리, 나머지 정상 수집
```

---

## 대용량 파이프라인 부하 분석

더미 데이터 테스트 전 예상 병목 지점을 사전 분석합니다. (`docs/TROUBLESHOOTING.md` #009)

### 병목 순위

| 순위 | 지점 | 언제 터지나 | 심각도 | 금전 피해 |
|---|---|---|---|---|
| 1 | Gemini audit 동시 트리거 | 유저 10명+ 동시 수집 완료 | 치명적 | Gemini 비용 폭발 |
| 2 | Cost Explorer 인스턴스별 순차 호출 | 인스턴스 50개+ 유저 | 높음 | 유저 AWS 비용 |
| 3 | `load_inventory()` 개별 쿼리 | 인스턴스 200개+ | 높음 | 없음 (느려짐) |
| 4 | RawSnapshot 개별 INSERT | 유저 50명+ | 중간 | 없음 (느려짐) |
| 5 | normalize 메모리 OOM | 인스턴스 1,000개+ | 중간 | 없음 |
| 6 | 스케줄 정각 집중 | 유저 30명+ | 낮음 | 없음 |

### 대응 방향

| 지점 | 현재 | 개선 방향 |
|---|---|---|
| Gemini 동시 트리거 | 수집 완료 직후 자동 실행 | 큐에 넣어 순차 처리 + DRF Throttle |
| Cost Explorer 호출 | 인스턴스별 개별 호출 | GroupBy로 1회 호출 통합 |
| DB 적재 | 건별 `update_or_create()` 루프 | `bulk_create` / `bulk_update` 분리 |
| normalize | 전체 리스트 메모리 적재 | 청크 단위 처리 (100건씩) |
| 스케줄 집중 | 정각에 모든 유저 동시 시작 | jitter(무작위 지연)로 분산 |

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
# 필수: SECRET_KEY, DB_*, GEMINI_API_KEY, FIELD_ENCRYPTION_KEY

# 3. DB 마이그레이션
python manage.py migrate

# 4. Prefect 서버 실행 (터미널 1)
prefect server start
# UI: http://localhost:4200

# 5. Prefect 스케줄 등록 (최초 1회)
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
python pipeline/flows/inventory_flow.py

# 6. django-q2 워커 실행 (터미널 2)
python manage.py qcluster

# 7. 서버 실행 (터미널 3)
python manage.py runserver
```

### 검증 순서

```bash
# 1. AWS Key 등록
POST /api/users/credentials/csv/

# 2. 권한 검증
POST /api/users/credentials/<pk>/test/
# → { "ec2": "OK", "cost_explorer": "OK", "compute_optimizer": "OK" }

# 3. 수동 수집 트리거
POST /api/inventories/sync/

# 4. AI 진단 실행
POST /api/recommendations/audit/  { "inventory_id": 1 }

# 5. 추천 결과 확인
GET /api/recommendations/
```

### 환경변수 목록

| 변수 | 설명 |
|---|---|
| `SECRET_KEY` | Django 시크릿 키 |
| `DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT` | PostgreSQL 연결 정보 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `FIELD_ENCRYPTION_KEY` | AWS Key 암호화용 Fernet 키 (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |
| `GCP_CREDENTIALS_PATH` | GCP Service Account JSON 경로 (선택) |
