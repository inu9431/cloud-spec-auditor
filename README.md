# cloud-spec-auditor
AWS 빌링 데이터와 CloudWatch 지표를 Gemini AI로 분석하여 오버스펙을 찾아내는 비용 최적화 솔루션



🚀 CostCutter

AI 기반 클라우드 비용 절감(FinOps) 솔루션

📌 소개

CostCutter는 사용자의 클라우드 리소스 사용 현황과
공식 가격 데이터를 결합하여
AI(Gemini)를 통해 실질적인 비용 절감 대안을 제시하는 서비스입니다.

✨ 핵심 기능

AWS / GCP / Azure 공식 가격 API 연동

리전 정규화를 통한 멀티 클라우드 비교

사용자 인벤토리 기반 과금 낭비 진단

AI 기반 절감 시나리오 생성

🏗 아키텍처 요약
Client
  ↓
View / Serializer
  ↓
Service Layer
  ↓
Adapter (Cloud / AI)
  ↓
Model (PostgreSQL)

🌍 Region Normalization

각 클라우드의 서로 다른 리전 체계를
NormalizedRegion으로 통합하여 정확한 가격 비교를 가능하게 합니다.

🔧 기술 스택

Backend: Django, DRF

Database: PostgreSQL, Redis

AI: Gemini API

Cloud SDK: Boto3

Infra: Docker, AWS EC2, Nginx

📄 문서

아키텍처 설계 문서

🚧 현재 상태

아키텍처 설계 완료

MVP 개발 진행 중
