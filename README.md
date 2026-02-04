# Quanda Knowledge Base Pipeline

FastAPI 기반 파이프라인 서버 - 파일 업로드, Claude Agent 메타데이터 생성, S3 업로드 및 Bedrock KB 동기화

## 설치

```bash
uv sync
```

## 실행

```bash
uv run uvicorn src.main:app --reload --port 8000
```

## Docker

```bash
docker build -t quanda-kb-pipeline .
docker run -p 8000:8000 --env-file .env quanda-kb-pipeline
```

## API

### POST /api/v1/upload

파일 업로드 및 메타데이터 생성

```bash
curl -X POST "http://localhost:8000/api/v1/upload" -F "file=@document.pdf"
```

## 환경변수

`.env.example` 참고
