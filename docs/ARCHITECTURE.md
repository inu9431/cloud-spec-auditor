# 시스템 아키텍처

## 프로젝트 개요

AWS, GCP, Azure 인프라 비용을 분석하고 절감 솔루션을 제공하는 클라우드 비용 최적화 서비스.
유저가 AWS Key를 한 번 등록하면, 자동으로 인스턴스 과스펙을 감지하고 3사 비교 기반 절감 솔루션을 제공한다.

---

## 1. 계층 분리 원칙

시스템은 두 개의 독립적인 레이어로 구성된다.

```
┌──────────────────────────────────────────────┐
│  Service Layer (apps/)                       │
│  유저 요청 → Serializer → Service → Model    │
│  REST API 서빙, JWT 인증, CRUD               │
└──────────────────┬───────────────────────────┘
                   │ 공유 모델
                   │ (UserInventory, CloudService)
┌──────────────────┴───────────────────────────┐
│  Pipeline Layer (pipeline/)                  │
│  외부 API → Extract → Load(raw) →            │
│  Transform → Load(mart)                      │
│  Prefect 오케스트레이션, 스케줄 수집          │
└──────────────────────────────────────────────┘
```

**두 레이어가 만나는 지점:**
- `UserInventory` — pipeline이 적재, apps가 API로 서빙
- `CloudService` — pipeline이 적재, apps가 비교 API로 서빙

**`apps/core/adapters/`** — AWS/GCP/Azure SDK 호출은 양쪽 레이어에서 공유

---

## 2. 데이터 3계층 구조 (Bronze / Silver / Gold)

### 배경 및 문제 제기

기존 구조에서는 사용자가 API를 호출할 때마다 외부 API(AWS/GCP)에서 데이터를 즉시 가공하여 반환했다.

**한계:**
- 외부 API 응답 지연 시 사용자 경험 저하
- 원본 데이터가 남지 않아 데이터 정합성 이슈 발생 시 원인 파악 불가능
- 분석 로직(AI Audit 등)이 변경되었을 때 과거 데이터에 소급 적용 불가

**해결 방향:** 수집 → 원본 보존 → 정제 → 분석 결과를 명확히 분리하는 3계층 구조 도입

---

### Bronze Layer (Raw 테이블 — 원본 보존)

- 외부 API 응답을 **가공 없이 JSONB 타입으로 즉시 적재**
- Append-Only 방식 — 수정/삭제 금지
- Hash 기반 중복 제거 (SHA-256)
- 목적: 데이터 유실 방지, Backfill 가능성 확보

```
RawEC2Snapshot    — EC2 API 응답 원본 (AWS)
RawGCPSnapshot    — Compute Engine API 응답 원본 (GCP)
RawAzureSnapshot  — VM API 응답 원본 (Azure)
RawPriceSnapshot  — 3사 가격 API 응답 원본
```

### Silver Layer (Mart 테이블 — 정제된 데이터)

- Raw 데이터를 읽어 서비스 규격에 맞춰 변환
- 리전 정규화 (AWS ap-northeast-2 → NormalizedRegion.KR)
- 인스턴스 상태 표준화
- update_or_create (idempotent)

```
UserInventory — 유저의 실제 사용 인스턴스 (자동 수집)
CloudService  — 3사 가격 데이터 (On-Demand 기준)
```

### Gold Layer (분석 결과 테이블)

- 정제된 데이터를 바탕으로 Gemini AI 분석 수행
- 사용자에게는 이미 가공된 결과를 서빙 → 빠른 응답 속도
- Python이 비용 계산, LLM은 설명 생성만 담당

```
Recommendation     — AI 진단 결과
RecommendationItem — 개별 추천 항목 (대안 인스턴스)
```

---

## 3. 전체 데이터 흐름도

### Step 1 — 백엔드 검증 (Service Layer)

```
Client
  → Route (Django URLs)
  → Schema (DRF Serializer: 입력 유효성 검사)
  → ORM (Django Models: CloudCredential 저장)
```

유저가 AWS 키를 등록하거나 대시보드에 진입할 때의 흐름.
여기까지가 전형적인 백엔드 CRUD 로직.

---

### Step 2 — 데이터 수집 및 적재 (Extract & Load — Bronze)

```
Task (Prefect Scheduler: 24h 주기 or 수동 트리거)
  → Adapter (Boto3: CloudCredential 키로 AWS API 호출)
  → Hash Check (JSON 응답 SHA-256 해싱 → 기존 데이터와 비교)
  → Append-Only Write (변경 있을 때만 RawEC2Snapshot 적재)
```

이 단계가 "원본을 보존하는 Bronze 레이어"

캐시 전략:
- EC2 인스턴스 목록: 1시간
- Cost Explorer 비용: 24시간
- Compute Optimizer 추천: 12시간
- 인스턴스 스펙 (describe_instance_types): 7일

---

### Step 3 — 데이터 정제 및 변환 (Transform — Silver)

```
Transform (RawSnapshot.payload 읽기)
  → Normalize (리전 매핑, 스펙 변환 → InventoryDTO)
  → Validate (비정상값 감지: 음수 비용, 0 vcpu 등)
  → Load (UserInventory.update_or_create)
```

정제된 데이터 = 사용자가 대시보드에서 조회하는 "깨끗한 데이터"

---

### Step 4 — AI 분석 및 결과 제공 (Analytics — Gold)

```
AI Task (Gemini API)
  → 입력: 정제된 인벤토리 + 3사 가격 비교 결과
  → Python이 비용 절감액 계산 (LLM에게 숫자 계산 위임하지 않음)
  → LLM은 설명 생성만 담당
  → Recommendation / RecommendationItem 저장
  → Response: Silver + Gold 결합하여 사용자에게 서빙
```

---

## 4. ELT 흐름 (ETL 아님)

Load(raw)를 Transform보다 먼저 수행하는 이유: **Backfill 가능성 확보**

```
[E] extract/aws.py
    AWS API 호출 + 캐시 → raw dict 반환

[L-raw] load/raw.py
    raw dict → RawEC2Snapshot.create() (Append-Only, 원본 보존)

[T] transform/normalize.py
    RawSnapshot.payload → InventoryDTO 변환 (리전 정규화, 스펙 매핑)

[T] transform/validate.py
    DTO 리스트 비정상값 검증 → 정상 DTO만 통과

[L-mart] load/inventory.py
    InventoryDTO → UserInventory.update_or_create()
```

Transform 로직이 바뀌어도 Raw 데이터를 기반으로 언제든 재처리 가능.

---

## 5. Prefect 오케스트레이션

```python
@flow(name="sync-user-inventory")   # 24h 스케줄
def sync_user_inventory(credential_id):
    raw_data    = extract_ec2_instances(credential)  # E
    snapshot    = save_raw_ec2(credential, raw_data) # L-raw
    dtos        = normalize_inventory(snapshot)       # T
    dtos        = validate_inventory(dtos)            # T
    inventories = load_inventory(user, dtos)          # L-mart
    _run_audit_for_inventories(inventories)           # Gold

@flow(name="sync-cloud-prices")     # 주 1회 스케줄
def sync_cloud_prices():
    # 3사 가격 ELT: fetch → save_raw_price → validate_prices → load_prices
```

Prefect UI(localhost:4200)에서 단계별 실행 이력 + 경고 로그 확인 가능

---

## 6. 데이터 생명 주기 (Retention)

서비스가 장기화될수록 Raw 테이블 크기가 기하급수적으로 커져 쿼리 성능 저하 문제 발생 가능.

| 구분 | 저장소 | 기간 | 용도 |
|---|---|---|---|
| Hot Data | PostgreSQL | 최근 3개월 | 실시간 AI Audit 분석 |
| Cold Data | S3 (JSON) | 3개월 이후 | 장기 보관, 감사 용도 |

Cold 이전 후 DB에서 삭제 → 메인 DB 인덱스 크기 유지 → 조회 성능 방어

적용 시점: 유료 고객 확보 이후

---

## 7. 보안 아키텍처

### AWS Key 암호화

`CloudCredential` 모델의 민감 필드를 `django-encrypted-model-fields`로 암호화 저장.

```
평문 → Fernet 대칭 암호화 → PostgreSQL 저장
복호화는 AWSAdapter 초기화 시점에만 수행
```

암호화 대상 필드:
- `aws_access_key_id`
- `aws_secret_access_key`
- `gcp_service_account_json`
- `azure_client_secret`

### API 남용 방지 (DRF Throttle)

베타 배포 기준 봇 공격 대응:

| 엔드포인트 | 기준 | 제한 |
|---|---|---|
| `POST /api/users/login/` | IP | 10회/분 |
| `POST /api/users/signup/` | IP | 10회/시간 |
| `POST /api/inventories/sync/` | 유저 | 1회/10분 |
| `POST /api/recommendations/audit/` | 유저 | 1회/5분 |
| `POST /api/costs/sync/*/` | 전역 | 1회/1시간 |

sync/audit 제한이 중요한 이유: 봇이 반복 호출 시 유저 AWS 계정에서 Cost Explorer API 비용 발생 + Gemini API 비용 폭발.

---

## 8. 확장성 고려

**새로운 클라우드 공급자 추가 시:**
- Bronze/Silver/Gold 파이프라인 구조 재사용 가능
- `pipeline/tasks/extract/gcp.py`, `azure.py` 파일만 추가
- `inventory_flow.py`에 provider 분기만 추가

**AI 분석 프롬프트 변경 시:**
- Raw 데이터를 다시 돌리는 것만으로 전체 리포트 갱신 가능 (Backfill)

**유저 증가 시:**
- `@task(retries=3)` + Partial Failure 허용으로 일시 장애 대응
- 인스턴스별 ThreadPoolExecutor 병렬 호출
- `bulk_create` / `bulk_update`로 DB 부하 감소

---

## 9. AI 컨설팅 채팅 아키텍처

클라우드 경험이 없는 유저도 자연어로 인프라 추천을 받을 수 있는 멀티턴 채팅 기능.

### 서비스 전체 흐름 (2단계)

```
[1단계: 컨설팅] 클라우드 몰라도 기획 언어로 질문
유저: "쇼핑몰 만들건데 유저 1000명 예상이고 이미지가 많아"
AI:  "추천 1: GCP e2-medium — 월 $24 (가장 저렴)
      추천 2: AWS t3.small — 월 $22 (가장 안정적)
      이미지가 많으시면 스토리지 50GB 이상 권장합니다."
유저: "AWS로 하려는데 어떻게 시작해?"
AI:  "AWS Key를 등록하시면 이후 자동으로 관리해드립니다.
      [AWS Key 등록하기]"
         ↓
[2단계: 실계정 관리] AWS Key 등록 후 자동 수집 + 과스펙 진단 + 지속 관리
```

→ "클라우드 선택부터 운영 최적화까지" 전 과정 커버

### user_state 기반 3분기

유저 상태에 따라 AI 응답 톤과 제공 데이터가 달라진다.

| user_state | 조건 | AI 응답 방식 |
|---|---|---|
| `NOT_REGISTERED` | 키 미등록 | 컨설팅 모드, 3사 가격 비교 + 키 등록 유도 |
| `REGISTERED_NO_DATA` | 키 등록 + 14일 미도달 | 스펙 기반 비교 (신뢰도: 중간), 14일 후 정밀 분석 예고 |
| `REGISTERED_WITH_DATA` | 키 등록 + 사용률 데이터 있음 | 실계정 기반 분석, 과스펙 감지 포함 (신뢰도: 높음) |

```python
system_prompt = """
너는 CostCutter의 클라우드 컨설턴트야.

규칙:
1. 전문 용어를 쓰지 마. "인스턴스" 대신 "서버", "vcpu" 대신 "CPU 성능"으로.
2. 가격을 항상 월 기준으로 말해.
3. 추천할 때 3사를 비교해서 보여줘.
4. 유저가 특정 클라우드를 선택하면, Key 등록으로 자연스럽게 안내해.
5. 숫자(가격, 절감액)는 내가 제공한 데이터만 사용해. 절대 직접 계산하지 마.

유저 상태: {user_state}
"""
```

### 14일 문제 해결 — 단계적 가치 제공

키 등록 직후에도 이탈 없이 가치를 제공한다.

```
키 등록 직후 (REGISTERED_NO_DATA):
  → 스펙 기반 비교. "t3.medium 동일 스펙 기준 GCP가 $6 더 저렴합니다."
  → 신뢰도: 중간 표시
  → "14일 후 사용률 기반 정밀 분석을 해드립니다" 안내

14일 후 (REGISTERED_WITH_DATA):
  → 사용률 기반 분석. "CPU 10%만 쓰고 있어서 과스펙입니다. t3.small 전환 시 $23 절감."
  → 신뢰도: 높음 표시
```

"아직 데이터가 없으니 기다리세요"가 아니라 단계별로 다른 가치를 제공하는 것이 핵심.

### 멀티턴 구현 방식

WebSocket 없이 HTTP + 프론트엔드 히스토리 관리:
- 프론트에서 `messages: [{role, content}, ...]` 배열 유지
- 매 요청마다 전체 히스토리를 함께 전송
- 백엔드는 `gemini.start_chat(history=[...])` 로 멀티턴 맥락 복원

```python
# 첫 메시지: 3사 가격 조회(CloudService DB) → Gemini 설명 생성
# 후속 메시지: history만 넘겨서 Gemini 멀티턴 (DB 재조회 불필요)
chat = model.start_chat(history=convert_history(request_history))
response = chat.send_message(user_message)
```

### API 비용 설계

Gemini 2.5 Flash 기준:
- 입력 100만 토큰당 $0.15 / 출력 100만 토큰당 $0.60
- 채팅 1턴 ≈ 입력 1,000토큰 + 출력 500토큰 → 약 $0.0005/턴
- 유저가 하루 50턴 채팅해도 $0.025 수준

남용 방지: 기존 DRF Throttle 패턴으로 유저당 50회/일 제한.

### UX 언어 원칙

클라우드 모르는 유저가 이해할 수 있게:
- "인스턴스" → "서버"
- "vcpu" → "CPU 성능"
- 가격은 항상 월 기준
- 기술적 디테일은 "더 보기"로 숨김
- 3사 비교는 월 가격 기준으로 항상 표시

### 프론트엔드 탭 구조

```
[3개 탭]

1. 컨설팅 (채팅)          ← 진입점, 키 없이 바로 사용
   - 기획 언어로 질문 → AI가 3사 추천
   - 멀티턴 대화 (이전 대화 맥락 유지)
   - 키 등록 CTA로 자연스러운 온보딩 연결

2. 대시보드               ← 키 등록 후
   - 자동 수집 인스턴스 목록 + 비용 요약
   - 신뢰도 표시 (SPEC_BASED / USAGE_BASED)

3. AI 추천                ← 키 등록 후
   - 과스펙 진단 결과
   - 3사 비교 절감 추천
```
