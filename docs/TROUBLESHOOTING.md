 # 트러블슈팅 기록

발생한 문제, 원인 분석, 해결 방법을 기록한다.
"어떤 문제를 어떻게 해결했는가"에 대한 문서.

---

## #001: 원본 데이터 부재로 Backfill 불가

**발견 시점:** 2026-04 (pipeline-etl 설계 중)

**문제:**
AI Audit 프롬프트를 수정하거나 리전 정규화 로직을 변경했을 때, 이미 가공된 `UserInventory` 데이터만 남아있어 과거 데이터에 소급 적용 불가능.

외부 API 응답이 바뀌었을 때도 원본이 없으니 원인 파악 불가.

**원인:**
기존 구조가 ETL (Transform 먼저) 방식이어서 가공 전 원본 데이터를 저장하지 않았음.

**해결:**
ELT 구조로 전환 — Load(raw)를 Transform 전에 먼저 수행.

```
pipeline/raw/models.py
  RawEC2Snapshot    — EC2 API 응답 원본 (JSONB, Append-Only)
  RawPriceSnapshot  — 3사 가격 API 응답 원본 (JSONB, Append-Only)
```

Transform 로직이 변경되어도 Raw payload 기반으로 언제든 재처리 가능.

**배운 점:**
데이터 파이프라인에서 원본 보존은 선택이 아닌 필수. 스토리지 비용보다 재처리 가능성이 중요.

---

## #002: AWS Key 평문 저장 발견

**발견 시점:** 2026-03 (코드 리뷰 중)

**문제:**
`CloudCredential` 모델의 `aws_access_key_id`, `aws_secret_access_key`, `gcp_service_account_json`, `azure_client_secret`이 PostgreSQL에 평문으로 저장되고 있었음.

```python
# 문제 코드 (models.py)
aws_access_key_id = models.CharField(
    max_length=200,
    help_text="AWS Access Key ID (암호화 필요)",  # 주석만 있고 실제 미적용
)
```

DB 덤프 1회로 전 고객 AWS 계정이 탈취될 수 있는 심각한 보안 취약점.

**해결 방향:**
`django-encrypted-model-fields` 라이브러리로 필드 타입 변경.

```python
from encrypted_model_fields.fields import EncryptedCharField

aws_access_key_id = EncryptedCharField(max_length=200, ...)
aws_secret_access_key = EncryptedCharField(max_length=200, ...)
```

`.env`에 Fernet 키 추가:
```
FIELD_ENCRYPTION_KEY=<Fernet.generate_key()로 생성>
```

**현재 상태:** ✅ 완료 — `django-encrypted-model-fields` (Fernet) 적용, 마이그레이션 완료

**배운 점:**
"암호화 필요" 주석은 보안이 아님. 모델 설계 시점에 필드 타입부터 암호화 타입으로 지정해야 함.

---

## #003: get_monthly_cost() 권한 부족 시 파이프라인 전체 실패

**발견 시점:** 2026-03 (AWS Key 등록 테스트 중)

**문제:**
유저가 Cost Explorer 권한 없는 IAM Key를 등록하면 `get_monthly_cost()` 호출 시 `AccessDeniedException` 발생 → 파이프라인 전체 중단.

```python
# 문제 코드 (aws_adapter.py)
except (BotoCoreError, ClientError) as e:
    raise CloudWatchConnectionError(f"Cost Explorer 조회 실패: {str(e)}")
    # AccessDeniedException이든 네트워크 오류든 구분 없이 전체 실패
```

반면 `get_rightsizing_recommendations()`는 이미 `{}` 반환으로 graceful 처리되어 있었음.

**해결 방향:**
AccessDeniedException은 파이프라인을 멈추지 말고 0.0 반환 + warning 로그.

```python
except ClientError as e:
    if e.response["Error"]["Code"] == "AccessDeniedException":
        logger.warning("Cost Explorer 권한 없음 — monthly_cost=0.0 반환: %s", instance_id)
        return 0.0
    raise  # 다른 오류는 정상적으로 raise
```

**현재 상태:** ✅ 완료 — AccessDeniedException / ValidationException → 0.0 반환 + warning 로그 처리

**배운 점:**
에러 처리는 에러 종류를 구분해야 함. 권한 부족은 재시도해도 해결 안 됨 → graceful degradation이 맞음.
네트워크 오류나 서버 오류는 재시도 대상.

---

## #004: Partial Failure 없어서 인스턴스 1개 실패 시 전체 실패

**발견 시점:** 2026-04 (pipeline 설계 검토 중)

**문제:**
`load_inventory()`에서 인스턴스를 순차적으로 저장할 때, 하나가 실패하면 예외가 전파되어 해당 유저의 전체 인벤토리 저장이 실패함.

```python
# 문제 코드 (load/inventory.py)
for dto in dtos:
    inventory, created = UserInventory.objects.update_or_create(...)
    # 예외 발생 시 전체 중단
```

**해결 방향:**
인스턴스별 try/except로 부분 실패 허용. 실패한 인스턴스는 skip + warning 로그.

```python
for dto in dtos:
    try:
        UserInventory.objects.update_or_create(...)
    except Exception as e:
        logger.warning("인스턴스 저장 실패 skip: resource_id=%s error=%s", dto.resource_id, e)
        continue
```

**현재 상태:** ✅ 완료 — bulk_create / bulk_update 분리 + 인스턴스별 try/except Partial Failure 허용

**배운 점:**
파이프라인에서 "전부 아니면 전무(All or Nothing)"는 외부 API 의존 시 비현실적.
일부 실패해도 나머지는 처리하는 Partial Failure 허용 설계가 운영 안정성을 높임.

---

## #005: @task에 retries 없어서 일시 장애 시 전체 실패

**발견 시점:** 2026-04 (pipeline 설계 검토 중)

**문제:**
Prefect `@task` 데코레이터에 retries 설정이 없어, AWS API 일시 장애나 Rate Limit 발생 시 즉시 실패 처리.

```python
# 문제 코드
@task
def extract_ec2_instances(credential): ...
# 실패하면 재시도 없이 바로 flow 실패
```

Cost Explorer는 ~10 TPS 제한이 있어 유저 수 증가 시 Rate Limit 가능성.

**해결 방향:**
```python
@task(retries=3, retry_delay_seconds=60)
def extract_ec2_instances(credential): ...

@task(retries=3, retry_delay_seconds=60)
def extract_monthly_cost(credential, instance_id): ...
```

**현재 상태:** ✅ 완료 — extract/aws.py, gcp.py, azure.py 모두 `@task(retries=3, retry_delay_seconds=60)` 적용

**배운 점:**
외부 API 호출은 항상 일시 장애 가능성을 전제해야 함. retries는 선택이 아닌 기본값.

---

## #006: sync 엔드포인트 남용 시 유저 AWS 계정 비용 발생 위험

**발견 시점:** 2026-03 (베타 배포 보안 검토 중)

**문제:**
`POST /api/inventories/sync/`는 인증된 유저라면 횟수 제한 없이 호출 가능.
봇이 이 엔드포인트를 반복 호출하면:
- 유저 AWS 계정에서 Cost Explorer API 비용 발생 (서버 비용이 아닌 고객 비용)
- django-q2 큐 폭발
- Gemini API 비용 선형 증가 (audit까지 연쇄 실행 시)

단순 서버 보호가 아니라 고객 보호 문제.

**해결 방향:**
DRF Custom Throttle로 엔드포인트별 호출 제한.

```python
# sync: 유저별 1회/10분
# audit: 유저별 1회/5분
# 가격 sync: 전역 1회/1시간
```

**현재 상태:** ✅ 완료 — SyncThrottle(1회/10분) / AuditThrottle(1회/5분) / PriceSyncThrottle(1회/1시간) 적용

**배운 점:**
API Rate Limit은 서버 보호만이 목적이 아님. 유저 AWS 계정 비용과 연결되는 엔드포인트는 고객 보호 차원에서도 반드시 제한 필요.

---

## #007: GCP 머신 타입 매핑 누락

**발견 시점:** 2026-03 (3사 비교 API 테스트 중)

**문제:**
`cloud_price_adapter.py`의 `GCP_MACHINE_SPECS`가 n1/n2/e2 일부만 정의되어 있음.
c2, m1, a2, t2d 등 미지원 → 해당 스펙 비교 결과 누락.

**단기 해결:**
매핑 테이블 확장 (c2-standard-4/8, n2-standard-8/16, e2-standard-4/16 추가)

**중기 해결:**
DB(CloudService)로 이관 → 어드민 관리

**현재 상태:** 단기 해결 진행 중

---

## #009: 파이프라인 대용량 부하 — 예상 병목 지점 (더미 데이터 테스트 전 분석)

**분석 시점:** 2026-03 (베타 배포 전 사전 검토)

---

### 파이프라인 병목 지도

```
extract_ec2_instances()          ← [1] 스케줄 정각 집중 시 큐 폭발
  └─ extract_monthly_cost()      ← [2] Cost Explorer — 가장 먼저 터짐
  └─ extract_rightsizing()       ← [3] Compute Optimizer 순차 호출
  └─ extract_instance_specs()    ← [4] 7일 캐시로 대부분 안전

save_raw_ec2()                   ← [5] 개별 INSERT 누적 시 DB 커넥션 고갈
normalize_inventory()            ← [6] 대량 리스트 메모리 적재 시 OOM
validate_inventory()             ← 상대적으로 안전
load_inventory()                 ← [7] 개별 update_or_create 쿼리 폭증
_run_audit_for_inventories()     ← [8] Gemini 동시 트리거 — 가장 치명적
```

---

### 지점별 상세 분석

**[1] 스케줄 정각 집중**
- 유저 30명+부터 체감
- 24h 스케줄이 정각에 모두 시작 → django-q2 큐 적체
- 대비: 유저별 jitter(무작위 지연) 추가로 분산

**[2] Cost Explorer 순차 호출 — 가장 먼저 터지는 곳**
- 인스턴스 50개+ 유저부터 체감
- 현재 구조: 인스턴스 ID별 개별 호출 → 인스턴스 50개 = 50번 순차 API 호출
- Cost Explorer ~10 TPS 제한 → 유저 100명 × 인스턴스 50개 = 5,000번 호출 집중 시 Rate Limit
- 금전 피해: 유저 AWS 계정에서 Cost Explorer API 비용 발생
- 대비: 인스턴스 ID 배열을 한 번에 넘기는 GroupBy 방식으로 1회 호출 통합

**[3] Compute Optimizer 순차 호출**
- 인스턴스 100개+ 부터 체감
- ARN 배열로 한 번에 조회 가능한데 현재 1개씩 호출
- 12시간 캐시 덕분에 두 번째 수집부터는 캐시 히트 → Cost Explorer보다 덜 심각

**[4] describe_instance_types**
- 7일 캐시로 첫 수집 때만 호출 → 실질적 문제 없음

**[5] RawEC2Snapshot 개별 INSERT — DB 커넥션 고갈**
- 유저 50명+ × 인스턴스 평균 20개 = 1,000건 동시 INSERT
- Django ORM 기본 커넥션 풀 초과 시 대기 발생
- t2.micro PostgreSQL이면 더 빨리 한계 도달
- 대비: `bulk_create()`로 전환 → 1,000건 → 1번의 INSERT

**[6] normalize_inventory() 메모리**
- 인스턴스 1,000건+ 한 번에 리스트로 올릴 때
- t2.micro 1GB 메모리에서 수천 건이면 OOM 가능
- 대비: 청크 단위 처리 (100건씩 끊어서)

**[7] load_inventory() 개별 쿼리 — 슬로우 쿼리 발생 지점**
- 인스턴스 200개+ 부터 체감
- 현재: 건당 1 SELECT + 1 UPDATE/INSERT → 인스턴스 100건 = DB 쿼리 최소 200번
- 유저 100명이면 20,000번 쿼리
- 대비: `bulk_create` + `bulk_update` 분리

**[8] Gemini audit 동시 트리거 — 가장 치명적**
- 유저 10명+ 수집 완료 시 동시 audit 자동 트리거
- Gemini API RPM(분당 요청 수) 제한 + 호출당 비용
- 봇 공격 1회로 Gemini 비용 폭발 가능 (금전 피해)
- 대비: audit를 수집 직후 자동 실행 말고 큐에 넣어 순차 처리 + DRF Throttle

---

### 터지는 순서와 심각도 요약

| 순위 | 지점 | 언제 터지나 | 심각도 | 금전 피해 |
|---|---|---|---|---|
| 1 | Gemini audit 동시 트리거 | 유저 10명+ | 치명적 | 있음 |
| 2 | Cost Explorer 순차 호출 | 인스턴스 50개+ | 높음 | 유저 AWS 비용 |
| 3 | load_inventory 개별 쿼리 | 인스턴스 200개+ | 높음 | 없음 (느려짐) |
| 4 | RawSnapshot 개별 INSERT | 유저 50명+ | 중간 | 없음 (느려짐) |
| 5 | normalize 메모리 OOM | 인스턴스 1,000개+ | 중간 | 없음 |
| 6 | 스케줄 정각 집중 | 유저 30명+ | 낮음 | 없음 |
| 7 | Compute Optimizer 순차 | 인스턴스 100개+ | 낮음 | 없음 |

---

### 더미 데이터 테스트 시나리오

```
시나리오 1: 인스턴스 100개짜리 유저 1명
→ Cost Explorer 순차 호출 총 소요 시간 측정
→ load_inventory 실행 쿼리 수 확인 (pg_stat_statements)

시나리오 2: 인스턴스 10개짜리 유저 10명 동시 수집
→ DB 커넥션 수 확인 (pg_stat_activity)
→ Gemini audit 동시 트리거 여부 + 비용 발생 확인

시나리오 3: 유저 50명 스케줄 정각 동시 시작
→ django-q2 큐 적체 시간 측정
→ 첫 번째 유저와 마지막 유저의 완료 시간 차이 측정
```

### 테스트 시 확인할 지표

| 지표 | 확인 방법 |
|---|---|
| DB 커넥션 수 | `SELECT count(*) FROM pg_stat_activity` |
| 슬로우 쿼리 | `pg_stat_statements` 확장 활성화 후 확인 |
| 단계별 소요 시간 | Prefect UI (localhost:4200) 태스크별 duration |
| 메모리 사용량 | `htop` or `free -m` |
| Gemini 호출 횟수 | Google AI Studio 콘솔 → 사용량 대시보드 |

---

## #010: Cost Explorer RESOURCE_ID GroupBy 미지원 — ValidationException

**발견 시점:** 2026-03 (실제 AWS 계정 연동 테스트 중)

**문제:**
`get_monthly_costs_bulk()`에서 GroupBy `RESOURCE_ID`로 Cost Explorer 호출 시 일부 계정에서 `ValidationException` 발생 → 파이프라인 전체 실패.

```
ValidationException: Group Definition dimension is invalid.
Valid values are AZ, INSTANCE_TYPE, LINKED_ACCOUNT, ...
```

`RESOURCE_ID`는 Cost Explorer에서 **리소스 수준 데이터**가 활성화된 계정에서만 GroupBy로 사용 가능. 기본 계정은 미지원.

**해결:**
`ValidationException`도 graceful 처리 — 0.0 반환 + warning 로그.

```python
except ClientError as e:
    code = e.response["Error"]["Code"]
    if code in ("AccessDeniedException", "UnauthorizedException", "ValidationException"):
        logger.warning("Cost Explorer GroupBy 불가 (%s) — 전체 0.0 반환", code)
        return {iid: 0.0 for iid in instance_ids}
```

**배운 점:**
AWS API 기능은 계정 설정에 따라 다르게 동작함. 테스트 계정 외에 일반 계정에서도 반드시 검증 필요.

---

## #011: save_raw_ec2 datetime 직렬화 오류

**발견 시점:** 2026-03 (실제 AWS 계정 연동 테스트 중)

**문제:**
EC2 API 응답의 `LaunchTime`, `timezone.now()` 등 datetime 객체가 payload dict에 포함된 채로 PostgreSQL JSONField에 저장 시도 → `TypeError: Object of type datetime is not JSON serializable` 발생.

```
payload_hash = hashlib.sha256(json.dumps(payload, default=str, ...))  # 해시 계산은 성공
RawEC2Snapshot.objects.create(payload=payload, ...)  # psycopg 직렬화 시 실패
```

해시 계산 시 `default=str` 옵션으로 통과하지만, ORM이 JSONField를 직접 직렬화할 때 datetime 처리 불가.

**해결:**
`save_raw_ec2` 진입 시점에 payload를 JSON 왕복 변환으로 정제.

```python
payload = json.loads(json.dumps(raw_data, default=str))
```

**배운 점:**
Django JSONField는 Python 기본 json 모듈을 사용해 직렬화. datetime 포함 dict는 저장 전 반드시 정제 필요.

---

## #012: validate_inventory cost<=0 조건으로 인스턴스 전체 제거

**발견 시점:** 2026-03 (실제 AWS 계정 연동 테스트 중)

**문제:**
Cost Explorer RESOURCE_ID GroupBy 미지원 계정에서 모든 인스턴스의 `current_monthly_cost=0.0`으로 반환됨. `validate_inventory`의 `cost <= 0` 필터가 전체 인스턴스를 제거 → 대시보드에 인스턴스 미노출.

**해결:**
`cost <= 0` 조건 제거. 비용 데이터가 0이어도 인스턴스 자체는 유효한 데이터.

**배운 점:**
데이터 검증 기준은 "비즈니스적으로 불가능한 값"에만 적용해야 함. 0.0 비용은 API 권한 부족으로 충분히 발생 가능한 정상 케이스.

---

## #013: Compute Optimizer 미활성화 시 근거 없는 과스펙 추천

**발견 시점:** 2026-03 (AI 추천 정확성 검토 중)

**문제:**
Compute Optimizer가 비활성화된 유저 또는 활성화 후 14일 미만인 유저의 경우 `get_rightsizing_recommendations()`가 `{}` 반환. 이 상태에서 audit이 실행되면 CPU/메모리 사용률 근거 없이 Gemini가 "과스펙"이라고 추천할 수 있음.

- Compute Optimizer 활성화: 3사 가격 비교 ✅ + 과스펙 감지 ✅
- Compute Optimizer 비활성화: 3사 가격 비교 ✅ + 과스펙 감지 ❌ (근거 없음)

핵심 가치("과스펙 감지")가 데이터 없이 실행되는 구조적 문제.

**해결 방향:**

1. Gemini 프롬프트를 Compute Optimizer 데이터 유무에 따라 분기
```python
if rightsizing_data:
    prompt = f"CPU {cpu_util}%, 메모리 {mem_util}% 기준 과스펙 분석..."
else:
    prompt = f"사용률 데이터 없음. {instance_type} 스펙 기준 3사 가격 비교만 제공..."
```

2. `/credentials/test/` 응답에 Compute Optimizer 활성화 상태 포함
3. 대시보드에서 비활성화 시 "가격 비교만 제공" 배너 표시

**현재 상태:** 미적용 — 구현 예정

**배운 점:**
서비스 핵심 기능의 정확성은 LLM이 아니라 입력 데이터 품질에서 결정됨. 데이터가 없을 때의 동작을 명시적으로 처리해야 함.

---

## #008: Azure Retry 로직 부재

**발견 시점:** 2026-03 (Azure 가격 sync 테스트 중)

**문제:**
Azure Retail Prices API 호출 시 `requests.get()` 직접 호출, 타임아웃/재시도 없음.
429(Rate Limit) 발생 시 전체 sync 실패.

**해결 방향:**
```python
def _get_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            raise
    raise Exception("Azure API 최대 재시도 초과")
```

**현재 상태:** 미적용
