# 아키텍처 의사결정 기록 (ADR)

의사결정 당시의 맥락과 선택 이유를 기록한다.
"왜 이렇게 만들었는가"에 대한 답변 문서.

---

## ADR-001: ETL 대신 ELT 구조 선택

**날짜:** 2026-04

**결정:** Transform 전에 Load(raw)를 먼저 수행하는 ELT 구조 채택

**배경:**
- ETL(Transform 먼저) 구조에서는 가공 로직에 버그가 있으면 원본 데이터 자체가 손실됨
- AI Audit 프롬프트나 정규화 로직이 바뀌었을 때 과거 데이터에 소급 적용 불가

**선택 이유:**
- Raw 데이터를 먼저 저장하면 Transform 로직이 변경되어도 Raw 기반으로 언제든 Backfill 가능
- 외부 API 응답 구조가 바뀌어도 서비스 중단 없이 Transform 로직만 수정

**트레이드오프:**
- DB 저장 공간 추가 소요 (Raw + Mart 이중 저장)
- 수용 이유: 데이터 신뢰성과 재처리 가능성이 스토리지 비용보다 중요

---

## ADR-002: Append-Only Raw 테이블 설계

**날짜:** 2026-04

**결정:** Raw 테이블은 INSERT만 허용, UPDATE/DELETE 금지

**배경:**
- Update/Upsert를 사용할 경우 과거 특정 시점 데이터가 유실됨
- 장애 발생 시 어떤 시점의 데이터로 되돌아갈지 기준이 없어짐

**선택 이유:**
- Append-Only = 불변 로그(Immutable Log) → 특정 시점 재처리(Backfill) 가능
- 수정된 상태값이 필요할 경우 Silver 레이어(mart)에서만 갱신

**구현:**
```python
# load/raw.py — create만 사용, update 금지
RawEC2Snapshot.objects.create(
    credential=credential,
    payload=raw_data,
    payload_hash=sha256(raw_data),
)
```

---

## ADR-003: Hash 기반 중복 제거 전략

**날짜:** 2026-04

**결정:** API 응답 JSON을 SHA-256 해싱하여 동일 데이터 재적재 방지

**배경:**
- 24시간 스케줄러가 돌 때 인스턴스 상태 변화가 없으면 동일한 데이터가 반복 적재됨
- DB 용량 낭비 + 의미 없는 레코드 누적

**선택 이유:**
- 해시 비교로 불필요한 I/O 제거
- 데이터의 실제 변경 시점(Event Time)을 명확히 식별 가능
- MD5 대신 SHA-256 선택: 충돌 저항성, 보안 표준 권장

**구현:**
```python
payload_hash = hashlib.sha256(json.dumps(raw_data, sort_keys=True).encode()).hexdigest()
if RawEC2Snapshot.objects.filter(credential=credential, payload_hash=payload_hash).exists():
    return  # 동일 데이터 → 저장 생략
```

---

## ADR-004: CloudWatch 미사용 결정

**날짜:** 2026-03

**결정:** CloudWatch 직접 호출 제거, Compute Optimizer로 대체

**배경:**
- EC2 CPU 사용률을 가져오기 위해 초기 구현에서 CloudWatch GetMetricStatistics 호출

**문제:**
- 유저 수 증가 시 유저 AWS 계정에서 CloudWatch API 비용 선형 증가
- 유저당 인스턴스 10개 × 유저 100명 = 1,000번 API 호출/수집 주기

**선택 이유 (Compute Optimizer):**
- AWS가 내부적으로 14일치 CloudWatch 데이터를 분석해 라이트사이징 추천 제공
- 호출 비용 없음 (AWS 무료 서비스)
- 유저가 자기 AWS 계정에서 Compute Optimizer 활성화 필요 (무료, 콘솔 1회 설정)

**트레이드오프:**
- Compute Optimizer 미활성화 유저는 CPU 사용률 데이터 없음
- 수용 이유: 온보딩 가이드로 해결, 비용 절감이 더 중요

---

## ADR-005: Airflow 대신 Prefect 선택

**날짜:** 2026-04

**결정:** 파이프라인 오케스트레이션 도구로 Prefect 채택

**검토한 대안:**
- Apache Airflow: 업계 표준, 기능 풍부
- Prefect: 경량, Python-native
- Celery Beat: Django 친화적이나 DAG 개념 없음

**Prefect 선택 이유:**
- 1인 개발 환경에서 Airflow는 별도 메타DB, 웹서버, 스케줄러 등 인프라 과도
- Python 코드 그대로 `@flow` / `@task` 데코레이터만 붙이면 됨 — 별도 DSL 없음
- 로컬에서 `prefect server start` 한 줄로 UI(localhost:4200) 실행 가능
- 실행 이력, 실패 로그, 단계별 상태를 UI에서 바로 확인

**트레이드오프:**
- Airflow 대비 생태계 작음
- 수용 이유: 포트폴리오 + 1인 개발 규모에서 운영 단순성이 생태계 크기보다 중요

---

## ADR-006: DRF Throttle 적용 범위 결정

**날짜:** 2026-03

**결정:** 로그인/sync/audit 엔드포인트에 DRF 내장 Throttle 적용, WAF/IP 차단은 제외

**배경:**
- 베타 배포 후 봇이 sync를 반복 호출할 경우 유저 AWS 계정에서 Cost Explorer API 비용 발생
- audit 반복 호출 시 Gemini API 비용 선형 증가

**선택 이유:**
- DRF `AnonRateThrottle` / `UserRateThrottle` + Custom Throttle로 코드 변경 최소화
- WAF / Fail2ban / Cloudflare: Railway 환경에서 설정 복잡, 베타 단계 과잉 대응

**적용 범위:**

| 엔드포인트 | 기준 | 제한 |
|---|---|---|
| login | IP | 10회/분 |
| signup | IP | 10회/시간 |
| sync | 유저 | 1회/10분 |
| audit | 유저 | 1회/5분 |
| 가격 sync | 전역 | 1회/1시간 |

---

## ADR-007: AWS Key 암호화 방식 결정

**날짜:** 2026-03 (문제 발견) → 2026-05 (적용 예정)

**결정:** `django-encrypted-model-fields` (Fernet 대칭 암호화) 적용

**문제:**
- `aws_access_key_id`, `aws_secret_access_key`, `gcp_service_account_json`, `azure_client_secret`이 PostgreSQL에 평문 저장
- DB 덤프 1회로 전 고객 클라우드 계정 탈취 가능

**검토한 대안:**
- AWS KMS: 키 관리 서비스, 높은 보안 수준이나 설정 복잡 + 비용
- HashiCorp Vault: 엔터프라이즈급, 베타 과잉
- `django-encrypted-model-fields`: Fernet 대칭 암호화, 필드 타입 변경만으로 적용

**선택 이유:**
- 모델 필드 타입 변경 + `.env`에 Fernet 키 하나 추가하는 수준으로 즉시 적용
- 복호화는 AWSAdapter 초기화 시점에만 수행 → 최소 노출

**트레이드오프:**
- 서버 환경변수(`FIELD_ENCRYPTION_KEY`)가 유출되면 복호화 가능
- 수용 이유: DB 직접 접근보다 환경변수 유출 위험이 낮음, KMS는 이후 단계에서 도입

---

## ADR-008: 3사 가격 On-Demand 기준 수집

**날짜:** 2026-03

**결정:** AWS/GCP/Azure 가격을 On-Demand 기준으로만 수집

**배경:**
- Reserved/Spot 가격까지 수집하면 구조 복잡도 증가

**선택 이유:**
- MVP 단계에서 On-Demand 비교만으로도 충분한 가치 제공
- `CloudService.pricing_model` 필드가 이미 있어 스키마 변경 없이 나중에 데이터만 추가 적재 가능
- Gemini 프롬프트에 "On-Demand 기준, Reserved/Spot 사용 시 추가 절감 가능" 명시로 단기 해결

**이후 계획:** Reserved 가격 별도 수집 (AWS: TermType=Reserved / GCP: CUD SKU / Azure: priceType=Reservation)

---

## ADR-009: 베타 배포 환경 결정

**날짜:** 2026-03

**결정:** Railway (App + PostgreSQL + django-q2 Worker) 사용

**배경:**
- AWS 프리티어는 t2.micro 1GB 메모리로 django-q2 Worker + Prefect 동시 실행이 빠듯함
- 1인 개발 환경에서 EC2 + Nginx + gunicorn 직접 관리 부담

**선택 이유 (Railway):**
- App $5/월 + PostgreSQL $5/월 + Worker $5/월 = 총 $15/월
- 배포 자동화 (GitHub Push → 자동 빌드/배포)
- 운영 오버헤드 없이 서비스 개발에 집중 가능
- 포트폴리오 단계에서 인프라 관리보다 서비스 완성도가 우선

**이후 계획:** 유료 고객 확보 후 EC2 + Nginx + gunicorn + RDS로 이전, VPC 분리는 그 이후

---

## ADR-010: Next.js 대시보드 모노레포 구조 선택

**날짜:** 2026-03

**결정:** 별도 레포 대신 프로젝트 루트의 `frontend/` 폴더에 Next.js 추가

**검토한 대안:**
- 별도 레포 (`cloud-spec-auditor-frontend`): 관심사 분리 명확
- 모노레포 (`frontend/` 폴더): 단일 레포 관리

**선택 이유 (모노레포):**
- 1인 개발 환경에서 레포 2개 동기화 부담
- 면접 시 "풀스택 포트폴리오" 단일 링크로 제시 가능
- Next.js와 Django 각각 Railway 서비스로 배포 → 구조상 차이 없음

**구현:**
- Next.js 14 (App Router) + Tailwind CSS + shadcn/ui
- `frontend/lib/api.ts` — Django REST API 클라이언트 + 타입 정의
- 4개 페이지: 로그인 / 대시보드 / AI추천 / AWS키관리
- `NEXT_PUBLIC_API_URL` 환경변수로 백엔드 URL 관리

---

## ADR-011: Cost Explorer GroupBy fallback 전략

**날짜:** 2026-03

**결정:** RESOURCE_ID GroupBy 실패 시 비용 0.0 반환 + 파이프라인 계속 진행

**배경:**
GroupBy `RESOURCE_ID`는 Cost Explorer 리소스 수준 데이터 활성화 계정에서만 지원. 일반 계정에서 `ValidationException` 발생.

**선택 이유:**
- 비용 데이터 없어도 인스턴스 목록 수집/저장은 가능
- 비용 0.0은 "데이터 없음"으로 처리, AI 분석에서 On-Demand 가격 기준으로 대체 계산
- 파이프라인 중단보다 부분 데이터 제공이 UX상 낫다고 판단

**트레이드오프:**
- Cost Explorer 미지원 계정 유저는 실제 청구 비용 대신 0.0 표시
- 수용 이유: 3사 비교 기준 가격(On-Demand)으로 여전히 절감 추천 가능

---

## ADR-012: AI 추천 정확성 — Compute Optimizer 미활성화 대응 전략

**날짜:** 2026-03

**결정:** Compute Optimizer 데이터 유무에 따라 Gemini 프롬프트를 분기, 데이터 없으면 가격 비교만 제공

**배경:**
- Compute Optimizer는 유저가 AWS 콘솔에서 직접 활성화 + 14일 데이터 누적 필요
- 미활성화 상태에서 audit 실행 시 사용률 근거 없이 "과스펙" 추천이 나올 수 있음

**결정 이유:**
- 근거 없는 추천은 서비스 신뢰도를 해침 → 데이터 없을 때는 가격 비교로만 한정
- 3사 가격 비교는 Compute Optimizer 없이도 정확하게 동작함 → 핵심 가치는 유지
- 온보딩에서 Compute Optimizer 활성화를 안내해 데이터 확보 유도

**트레이드오프:**
- 신규 유저는 14일간 가격 비교만 제공, 과스펙 감지 불가
- 수용 이유: 부정확한 추천보다 제한된 정확한 추천이 낫다고 판단

---

## ADR-013: 추천 매칭 모드 — Mode A(다운사이징) / Mode B(동급 비교) 분기

**날짜:** 2026-03

**결정:** 과스펙 여부에 따라 두 가지 매칭 모드를 분기해서 실행

**배경:**
- 현재 `compare_by_spec()`이 항상 exact match(vcpu=, memory_gb=)로만 동작
- 과스펙 인스턴스에게 "같은 스펙 더 싼 것"을 추천하면 의미 없음 — 다운사이징이 맞음
- 적정 스펙 인스턴스에게는 동급 비교가 맞음

**모드 A — 다운사이징 (과스펙일 때):**
```
필요 vcpu   = cpu_usage_avg / 100 × 현재 vcpu × 1.5 (버퍼)
필요 memory = memory_usage_avg / 100 × 현재 memory × 1.5 (버퍼)
최소 보장: vcpu >= 1, memory >= 0.5GB
→ 필요 스펙 이상 + 현재보다 저렴한 인스턴스 검색
```

**모드 B — 동급 비교 (적정 스펙일 때, SPEC_BASED 포함):**
```
같은 vcpu, memory ±20% 범위에서 더 저렴한 인스턴스 검색
```

**트레이드오프:**
- 모드 A는 사용률 데이터가 있어야 의미 있음 → SPEC_BASED면 모드 B로 fallback
- 수용 이유: 데이터 품질에 따라 자동으로 적절한 모드를 선택하는 구조가 더 안전

---

## ADR-014: 추천 스코어링 — 가격 최저순 대신 다차원 점수 기반 정렬

**날짜:** 2026-03

**결정:** 추천 후보 정렬 기준을 `price_per_hour` 단순 오름차순에서 스코어링 공식으로 전환

**배경:**
- 가장 싼 인스턴스가 항상 최선이 아님
- GCP/Azure 전환은 마이그레이션 부담이 있어 절감액이 크더라도 실행 가능성이 낮음
- 같은 클라우드 내 다운사이징이 실행 가능성이 가장 높음

**스코어링 공식:**
```python
score = (
    cost_saving_pct * 0.5          # 비용 절감률 50%
    + min(vcpu_headroom, 3) * 10   # 스펙 여유도 30% (상한 cap)
    + same_provider_bonus          # 동일 클라우드 보너스 20%
)
```

**트레이드오프:**
- 가중치가 고정값이라 워크로드 특성에 따라 최적이 아닐 수 있음
- 수용 이유: MVP 단계에서 단순하고 설명 가능한 기준이 복잡한 ML 모델보다 신뢰도 높음

---

## ADR-015: analysis_type — USAGE_BASED / SPEC_BASED 분기와 API 응답 노출

**날짜:** 2026-03

**결정:** audit 결과에 `analysis_type`과 `confidence`를 포함해 유저에게 분석 신뢰도를 명시

**배경:**
- Compute Optimizer 데이터 없을 때 "14일 후 재방문"만 안내하면 첫 경험에서 이탈
- 데이터 품질이 다른 두 케이스를 같은 결과로 보여주면 유저 신뢰도 저하

**분기 기준:**
```
USAGE_BASED (confidence: HIGH)
  → cpu_usage_avg 있음
  → 모드 A 적용, 과스펙 판단 포함

SPEC_BASED (confidence: MEDIUM)
  → cpu_usage_avg 없음 (Compute Optimizer 미활성화 or 14일 미도달)
  → 모드 B 적용, 가격 비교만 제공
  → "Compute Optimizer 활성화 후 14일이 지나면 정밀 분석 가능" 안내
```

**트레이드오프:**
- MEDIUM 표시가 유저에게 불안감을 줄 수 있음
- 수용 이유: 신뢰도를 숨기는 것보다 명시하는 게 장기 신뢰도에 유리

---

## ADR-016: 인스턴스 비교 정확성 — ARM/버스터블 처리 전략

**날짜:** 2026-03

**배경:**
같은 vcpu + memory_gb라도 아키텍처와 성능 특성이 다른 케이스가 존재.

**케이스 1 — ARM vs x86:**
- t3.medium(x86)과 t4g.medium(ARM, Graviton) 모두 vcpu=2, memory=4GB
- ARM 호환 안 되는 앱에 t4g 추천 시 틀린 추천
- **결정:** `CloudService`에 `cpu_arch` 필드 추가, 비교 시 동일 아키텍처만 매칭 (중기)

**케이스 2 — 버스터블 vs 고정 성능:**
- t3.medium(버스터블)과 m5.large(고정) 모두 vcpu=2, memory=4GB
- 지속 부하 시 t3는 크레딧 소진으로 성능 저하 가능
- **단기 결정:** 프롬프트에 `instance_type`명 전달 → LLM이 버스터블 여부를 맥락 설명에 포함
- **중기 결정:** `CloudService`에 `is_burstable` 필드 추가

**케이스 3 — GCP 데이터 누락:**
- GCP 일부 머신 타입이 DB에 없으면 비교에서 조용히 빠짐
- 유저가 "GCP 없음"인지 "GCP가 더 비쌈"인지 구분 불가
- **결정:** 비교 결과에 provider별 데이터 존재 여부 명시

---

## ADR-017: 로그 전략 — 이중 로깅 + 구조화 태그

**날짜:** 2026-03

**결정:** Prefect `@task` 내에서 run_logger(Prefect UI)와 Django logger(서버 로그) 둘 다 호출, 구조화 태그로 나중에 파싱 가능하게 설계

**배경:**
- 현재 Prefect 로그와 Django 로그가 분리되어 장애 추적 어려움
- Cost Explorer 등 유저 AWS 계정에서 비용 발생하는 API 호출을 별도로 추적해야 함

**태그 체계:**
```
BILLING_EVENT  — 유저 AWS 계정 비용 발생 API (Cost Explorer, Compute Optimizer)
RETRY_ERROR    — 재시도 가능한 일시 장애 (Throttling, 타임아웃)
PERM_ERROR     — 재시도 불가 에러 (AccessDeniedException)
ABUSE_ALERT    — 남용 감지 (sync 단시간 반복 호출)
```

**확장 방향:** 로그 포맷을 지금부터 구조화해두면 배포 후 AWS CloudWatch Logs로 전환 시 쿼리 바로 가능

**트레이드오프:**
- 로그 호출이 2배로 늘어나 코드가 약간 번거로움
- 수용 이유: 1인 운영 환경에서 장애 추적 가능성이 코드 간결함보다 중요
