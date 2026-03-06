# AWS IAM 설정 가이드

CostCutter를 사용하기 위해 AWS IAM에서 최소 권한 설정이 필요합니다.
이 가이드를 따라 IAM 사용자를 생성하고 Access Key를 발급하세요.

---

## 1단계: IAM 사용자 생성

1. AWS 콘솔 → IAM → 사용자 → 사용자 생성
2. 사용자 이름 입력 (예: `costcutter-readonly`)
3. **"직접 정책 연결"** 선택

---

## 2단계: 최소 권한 정책 연결

아래 JSON을 사용해 인라인 정책을 생성하거나, 기존 정책 중 동일한 Action을 포함하는 정책을 연결하세요.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "compute-optimizer:GetEC2InstanceRecommendations"
      ],
      "Resource": "*"
    }
  ]
}
```

### 각 권한이 필요한 이유

| 권한 | 용도 |
|---|---|
| `ec2:DescribeInstances` | 실행 중인 EC2 인스턴스 목록 조회 |
| `ec2:DescribeInstanceTypes` | 인스턴스 스펙(vCPU, 메모리) 조회 |
| `ce:GetCostAndUsage` | 인스턴스별 실제 월 청구 비용 조회 |
| `compute-optimizer:GetEC2InstanceRecommendations` | 과스펙 감지 + 라이트사이징 추천 |

CostCutter는 읽기 전용 권한만 사용합니다. 인스턴스 중지/삭제 등 쓰기 권한은 요구하지 않습니다.

---

## 3단계: Access Key 발급

1. 생성한 IAM 사용자 클릭 → 보안 자격 증명 탭
2. 액세스 키 만들기 → **"서드 파티 서비스"** 선택
3. Access Key ID / Secret Access Key 복사 (또는 CSV 다운로드)

> Secret Access Key는 이 시점에만 확인 가능합니다. 반드시 저장해두세요.

---

## 4단계: Compute Optimizer 활성화 (선택, 강력 권장)

Compute Optimizer를 활성화해야 과스펙 감지 및 라이트사이징 추천 기능을 사용할 수 있습니다.

1. AWS 콘솔 → Compute Optimizer
2. **"시작하기"** 클릭
3. 계정 수준에서 활성화 (무료)

활성화 후 약 12~24시간이 지나면 인스턴스 추천 데이터가 생성됩니다.
활성화하지 않아도 EC2 목록 조회 및 비용 분석은 정상 동작합니다.

---

## 5단계: CostCutter에 등록

### 방법 A: 직접 입력

`POST /api/users/credentials/`

```json
{
  "provider": "AWS",
  "credential_type": "ACCESS_KEY",
  "nickname": "my-aws-account",
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "...",
  "aws_default_region": "ap-northeast-2"
}
```

### 방법 B: CSV 파일 업로드

IAM에서 다운로드한 CSV 파일을 그대로 업로드할 수 있습니다.

`POST /api/users/credentials/csv/` (multipart/form-data)

---

## 6단계: 권한 검증

키 등록 후 권한이 올바르게 설정되었는지 확인하세요.

`POST /api/users/credentials/<id>/test/`

응답 예시:
```json
{
  "ec2": "OK",
  "cost_explorer": "OK",
  "compute_optimizer": "미활성화 또는 권한 없음 (선택사항)"
}
```

`cost_explorer`가 "권한 없음"으로 나오면 2단계의 `ce:GetCostAndUsage` 권한을 다시 확인하세요.

---

## 자주 묻는 질문

**Q. 루트 계정 키를 써도 되나요?**
안 됩니다. 보안상 루트 계정 Access Key 사용은 AWS가 금지 권장합니다. 반드시 IAM 사용자를 별도 생성하세요.

**Q. 기존 IAM 사용자의 키를 써도 되나요?**
가능하지만, 위 정책을 추가로 연결해야 합니다. 기존 정책이 이미 위 Action을 포함하면 별도 연결 불필요.

**Q. 비용이 발생하나요?**
CostCutter가 호출하는 AWS API 자체는 무료입니다.
- `ec2:Describe*`: 무료
- `ce:GetCostAndUsage`: 무료 (월 사용 한도 내)
- Compute Optimizer: 무료

**Q. 키를 삭제하면 어떻게 되나요?**
CostCutter에서 해당 Credential을 비활성화하고 자동 수집이 중단됩니다. 기존에 수집된 데이터는 유지됩니다.
