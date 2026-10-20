# CostCutter — 멀티클라우드 비용 최적화 플랫폼

> AWS/GCP/Azure 3사 인프라를 통합 비교하고, AI가 과스펙을 감지해 절감 방안을 추천하는 서비스

**GitHub:** [링크]  
**배포:** [링크]  
**기간:** 2025.01 ~ (1인 개발)  
**스택:** Django · DRF · PostgreSQL · Prefect · Gemini API · Next.js · Docker

---

## 프로젝트 배경

이전 프로젝트(디스코드 봇)를 AWS에 배포하면서 예상 외 비용이 발생했습니다. 프리티어 내에서 EC2 + RDS를 구성했지만 어떤 인스턴스가 과스펙인지, 다른 클라우드가 더 저렴한지 판단할 기준이 없었습니다.

기존 FinOps 도구들(AWS Cost Explorer, CloudHealth 등)은 이미 클라우드를 운영 중인 전문가를 대상으로 하며, **클라우드 선택 단계부터 운영 최적화까지 하나의 흐름으로 연결하는 서비스는 없었습니다.** 이 공백을 채우기 위해 CostCutter를 만들었습니다.

---

## 핵심 기능

### 1. AI 컨설팅 채팅 (배포 전 — 클라우드 선택 단계)

서비스 기획만 있으면 AWS/GCP/Azure 3사 중 최적의 인프라를 추천합니다. 전문 용어 없이 자연어로 질문하면 3사 가격 DB 기반으로 비교 결과를 제공합니다.

- Gemini 멀티턴 API + HTTP 기반 채팅 (history 배열로 맥락 유지)
- `user_state` 3단계 분기: 미등록 → 키등록(데이터 부족) → 키등록(데이터 충분)
- 단계별로 다른 수준의 분석 제공 (3사 가격 비교 → 스펙 기반 → 실계정 기반)

### 2. 자동 비용 분석 (배포 후 — 운영 최적화 단계)

AWS Key 등록 한 번으로 24시간마다 자동 수집 → 과스펙 감지 → 절감 추천까지 수행합니다.

- EC2 + Cost Explorer + Compute Optimizer 데이터 자동 수집
- Mode A (다운사이징): CPU 사용률 30% 미만 → 하위 스펙 후보 탐색
- Mode B (크로스클라우드): 동일 스펙 기준 3사 최저가 비교
- Python이 모든 수치 계산, Gemini는 설명 생성만 담당 (할루시네이션 방지)

### 3. 두 모드의 자연스러운 연결 (PLG 온보딩)

컨설팅 채팅에서 가치를 먼저 제공 → AWS Key 등록 CTA → 자동 분석으로 전환되는 PLG(Product-Led Growth) 구조입니다.

---

## 아키텍처

### 전체 구조

```
[서비스 레이어 — apps/]          [데이터 레이어 — pipeline/]
유저 요청 → DRF API 서빙         외부 API → Extract → Load(Raw) → Transform → Load(Mart)
                  ↕ 공유 모델: UserInventory, CloudService
```

- **apps/**: Django REST API — 유저 인증, 인벤토리 CRUD, AI 추천, 컨설팅 채팅
- **pipeline/**: ELT 데이터 파이프라인 — 3사 API 수집 → Raw 보존 → 정규화 → 서비스 테이블 적재
- **apps/core/adapters/**: AWS/GCP/Azure SDK 호출 (양쪽에서 공유, Adapter 패턴)

### ELT 파이프라인

```
[Extract]  AWS/GCP/Azure API 호출 (@task, retries=3, 캐시 적용)
    ↓
[Load-Raw] RawSnapshot Append-Only 저장 (Bronze — 원본 보존)
    ↓
[Transform] 리전 정규화 + DTO 변환 + 비정상값 검증 (chunk_size=100)
    ↓
[Load-Mart] UserInventory / CloudService upsert (Silver/Gold)
```

- Raw 테이블을 먼저 저장하는 ELT 구조 → API 응답 구조가 바뀌어도 Raw 데이터로 Backfill 가능
- Prefect로 오케스트레이션: 실행 이력 UI, 스케줄 관리, 실패 시 재시도

### 3사 리전 정규화

AWS(`ap-northeast-2`), GCP(`asia-northeast3`), Azure(`koreacentral`) — 같은 서울 리전이지만 이름이 모두 다릅니다. `NormalizedRegion.KR`로 통합하여 동일 기준 비교가 가능하게 했습니다.

---

## 주요 기술적 의사결정

### 왜 Airflow 대신 Prefect인가

1인 개발 환경에서 Airflow는 스케줄러 + 웹서버 + DB 등 인프라 오버헤드가 큽니다. Prefect는 Python-native로 `@flow`/`@task` 데코레이터만으로 파이프라인을 구성할 수 있고, 추가 인프라 없이 로컬에서 UI까지 실행 가능합니다.

### 왜 CloudWatch를 직접 호출하지 않았는가

CloudWatch 직접 호출은 유저 수가 늘어날수록 유저의 AWS 계정에서 API 비용이 선형 증가합니다. Compute Optimizer는 AWS 내부에서 14일치 메트릭을 분석해 과스펙 판단을 제공하며, 호출 비용이 없습니다.

### LLM 응답을 어떻게 통제했는가

초기에는 자유 텍스트 응답 + 키워드 블랙리스트 후처리 방식을 썼지만, Gemini가 매번 다른 표현으로 우회하는 문제가 반복됐습니다. 근본 해결은 두 가지였습니다.

1. 입력 데이터에서 언급하면 안 되는 항목(storage_gb)을 아예 제거
2. 출력을 JSON 구조화 응답으로 전환해 정해진 필드만 반환하도록 설계

"이 말 하지 마"를 강제하는 게 아니라, **"이 데이터 자체를 안 줬으니 말할 수 없는" 구조**를 만든 것이 핵심입니다.

### user_state 3분기를 왜 만들었는가

AWS Key 등록 직후 Compute Optimizer 데이터가 쌓이려면 14일이 필요합니다. 그 사이 "데이터 없음, 기다리세요"만 보여주면 유저가 이탈합니다. 단계별로 다른 수준의 가치를 제공해야 유저가 남습니다.

- `NOT_REGISTERED`: 3사 가격 비교로 즉시 가치 제공
- `REGISTERED_NO_DATA`: 스펙 기반 비교(신뢰도: 중간) + 14일 후 정밀 분석 예고
- `REGISTERED_WITH_DATA`: 실계정 사용률 기반 분석(신뢰도: 높음)

### AI 역할 분리 — 왜 Python이 계산하고 Gemini는 설명만 하는가

LLM에게 숫자 계산을 맡기면 부정확한 결과가 나올 수 있습니다. 절감액, 사용률, 스코어링 등 모든 수치 계산은 Python의 결정적(deterministic) 로직이 담당하고, Gemini는 "왜 이 서버가 과스펙인지"를 사람이 이해하기 쉬운 언어로 설명하는 역할만 합니다.

---

## 성능 최적화 및 부하 테스트

### DB 인덱싱

- `CloudService` 복합 인덱스: `[vcpu, memory_gb, region_normalized, pricing_model]` → 3사 스펙 비교 쿼리 **Index Scan 0.317ms** 달성
- `RawSnapshot` 복합 인덱스: `[credential_id, fetched_at]` → 유저별 최신 스냅샷 조회 최적화

### 파이프라인 부하 테스트

- 더미데이터 시드 스크립트로 대량 데이터 생성 후 테스트
- `bulk_create` 처리량: **~28,000 rows/s** (데이터 규모 무관 일정)
- 유저별 인벤토리 조회: 데이터 40배 증가에도 **0.02ms 유지** (인덱스 효과 확인)
- 발견된 병목: bcrypt 패스워드 해싱 (시드 스크립트 한정, 실서비스 영향 없음)

---

## 보안 설계

- AWS Key는 `django-encrypted-model-fields`(Fernet)로 DB 암호화 저장, API 호출 시점에만 복호화
- 읽기 전용 권한만 사용 — 유저 인스턴스를 중지/삭제하는 기능 없음
- DRF Throttle로 로그인/sync/audit/price_sync 엔드포인트별 호출 제한
- Credential Validation API로 등록 직후 권한 체크, 권한 부족 시 graceful 처리

---

## 트러블슈팅 주요 사례

| # | 문제 | 원인 | 해결 |
|---|------|------|------|
| 1 | Gemini가 프롬프트 제약을 무시하고 storage 비용 언급 | 자유 텍스트 응답에서는 블랙리스트 후처리가 비효과적 | 입력에서 storage_gb 제거 + JSON 구조화 출력 전환 |
| 2 | Cost Explorer ValidationException | RESOURCE_ID GroupBy 미지원 계정 존재 | 0.0 반환 + warning 로그로 graceful 처리 |
| 3 | Docker 컨테이너에서 `uv run` 심볼릭 링크 깨짐 | CMD에서 uv run 사용 시 .venv 경로 불일치 | `.venv` 직접 실행으로 변경 |
| 4 | validate_inventory에서 cost<=0 필터가 전체 인스턴스 제거 | Cost Explorer 미지원 계정은 모든 인스턴스 cost가 0 | cost<=0 필터 조건 제거 |

전체 트러블슈팅 20건은 `docs/TROUBLESHOOTING.md`에 기록되어 있습니다.

---

## 문서화

| 문서 | 내용 |
|------|------|
| `docs/ARCHITECTURE.md` | Bronze/Silver/Gold 구조, 전체 흐름도, 보안 아키텍처 |
| `docs/DECISIONS.md` | 아키텍처 의사결정 기록 (ADR) 22건 |
| `docs/TROUBLESHOOTING.md` | 문제 발견 → 원인 분석 → 해결 과정 18건 |
| `docs/ONBOARDING_IAM.md` | 유저용 AWS IAM 최소 권한 설정 가이드 |

---

## 현재 한계 및 향후 계획

**인지하고 있는 한계:**

- EC2 인스턴스에 집중 — S3, RDS, 네트워크 비용은 미분석
- Reserved/Spot 중 Spot은 미수집 — On-Demand + Reserved(1yr No Upfront)까지만 구현
- Azure Reserved 가격 미수집 (AWS/GCP Reserved는 완료)

**향후 작업:**

- EC2 외 서비스(S3, RDS) 분석 확장
- Azure Reserved 가격 수집 추가
- Spot 가격 데이터 수집 (CloudService.pricing_model 필드 준비 완료)

---

## 기술 스택 상세

| 영역 | 기술 | 선택 이유 |
|------|------|-----------|
| Backend | Django 6.0 + DRF | Python 생태계 + ORM + REST API 빠른 구축 |
| Database | PostgreSQL (JSONB) | Raw 데이터 유연 저장 + 복합 인덱스 지원 |
| Pipeline | Prefect (@flow/@task) | 경량 오케스트레이션, 1인 개발 환경에 적합 |
| Cloud APIs | boto3 / GCP Client / Azure SDK | 3사 공식 SDK, Adapter 패턴으로 추상화 |
| AI | Gemini 2.5 Flash | 비용 효율적 (채팅 1턴 $0.0005 미만), 구조화 출력 지원 |
| Auth | SimpleJWT | DRF + 프론트엔드 분리 구조에 적합 |
| Security | Fernet 암호화 + DRF Throttle | AWS Key 보호 + API 남용 방지 |
| Frontend | Next.js 14 + Tailwind CSS | 대시보드 + 채팅 UI |
| Infra | Docker Compose (5 services) | 로컬 개발환경 통합 (app/db/qcluster/prefect/worker) |