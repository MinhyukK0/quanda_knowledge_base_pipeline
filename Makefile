.PHONY: install run format lint check test clean docker-build docker-run

# 의존성 설치
install:
	uv sync --all-extras

# 서버 실행
run:
	uv run uvicorn src.main:app --reload --port 8000

# 코드 포맷팅
format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# 린트 체크
lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# CI 체크 (린트 + 테스트)
check: lint test

# 테스트
test:
	uv run pytest -v

# 캐시 정리
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Docker 빌드
docker-build:
	docker build -t quanda-kb-pipeline .

# Docker 실행
docker-run:
	docker run -d --name quanda-kb -p 8000:8000 \
		-e CLAUDE_CODE_USE_BEDROCK=true \
		-e ANTHROPIC_MODEL=apac.anthropic.claude-sonnet-4-20250514-v1:0 \
		-e S3_BUCKET=$(S3_BUCKET) \
		-e BEDROCK_KB_ID=$(BEDROCK_KB_ID) \
		-e BEDROCK_DATA_SOURCE_ID=$(BEDROCK_DATA_SOURCE_ID) \
		-e AWS_REGION=ap-northeast-2 \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) \
		quanda-kb-pipeline
