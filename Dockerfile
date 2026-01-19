# python 3.12 이미지
FROM python:3.12-slim AS production

# 환경변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 \
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# pyproject.toml 과 uv.lock 복사
COPY pyproject.toml uv.lock ./

# Python 의존성 설치
RUN uv sync --frozen --no-dev

# 프로젝트 파일 복사
COPY . .

# 정적 파일 디렉토리 생성
RUN mkdir -p staticfiles media cache logs

# 포트 노출
EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# 실행 명령
CMD ["uv", "run", "gunicorn", "costcut.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]

