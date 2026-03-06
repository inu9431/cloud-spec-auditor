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

**결정:** AWS 프리티어 (EC2 t2.micro + RDS) 사용, Railway 제외

**배경:**
- Railway 프리티어 2023년 폐지, Hobby 플랜 $5/월 + 종량제 → App + DB + Worker 시 월 $15~20

**선택 이유 (AWS 프리티어):**
- EC2 t2.micro 750h/월 + RDS t2.micro 750h/월 12개월 무료
- 이 프로젝트가 AWS 비용 최적화 서비스 → AWS에 배포하는 것이 일관성 있음
- "EC2 + Nginx + gunicorn + RDS 직접 배포" 경험이 포트폴리오에서 플러스

**제약:**
- Prefect UI는 로컬에서만 실행 (t2.micro 메모리 1GB로 빠듯)
- django-q2 Worker는 같은 EC2에서 실행

**이후 계획:** 유료 고객 확보 후 t3.medium으로 업그레이드 or RDS 분리
