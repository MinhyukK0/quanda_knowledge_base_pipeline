# Quanda Knowledge Base Pipeline

FastAPI 기반 파이프라인 서버 - 파일 업로드, Claude Agent 메타데이터 생성, S3 업로드 및 Bedrock KB 동기화

## 프로젝트 구조

```
src/
├── main.py                 # FastAPI 앱 엔트리포인트 + FastStream 통합
├── api/
│   └── v1/
│       ├── upload.py       # 파일 업로드 API
│       └── compact.py      # Compact 이벤트 발행 API
├── conf/
│   ├── settings.py         # AppSettings (pydantic-settings)
│   ├── container.py        # DI 컨테이너 (dependency-injector)
│   └── kafka.py            # Kafka 브로커 설정
├── events/                 # 이벤트 핸들러 (Kafka subscriber)
│   └── v1/
│       └── compact.py      # Compact 이벤트 핸들러
├── schema/                 # Pydantic 이벤트 스키마
│   └── v1/
│       └── compact_event.py # CompactEvent, CompactResult
├── services/               # 비즈니스 로직
│   └── compact.py          # CompactService (문서 정리/병합)
├── external_service/       # 외부 서비스 클라이언트
│   ├── agent.py            # Claude Agent 서비스 (Bedrock 지원)
│   ├── s3.py               # S3 업로드 서비스
│   └── bedrock.py          # Bedrock KB 동기화 서비스
└── utils/
    └── datetime.py         # datetime 유틸리티

.agent_config/              # Claude Agent 설정
├── AGENT.md                # 에이전트 역할 정의
├── rules/
│   └── metadata-extraction.md  # 메타데이터 추출 규칙
└── skills/
    └── extract-metadata.md     # 메타데이터 추출 스킬

tests/                      # 테스트 (src 구조와 동일)
├── conftest.py             # 공통 fixture 및 모킹 설정
├── test_main.py            # 메인 앱 테스트
├── api/
│   └── v1/
│       └── test_upload.py  # 업로드 API E2E 테스트
├── events/
│   └── test_handlers.py    # CompactService 및 이벤트 핸들러 테스트
└── services/
    └── test_s3.py          # S3Service 테스트
```

## 테스트

### 테스트 실행

```bash
# 전체 테스트
make test

# 상세 출력
uv run pytest -v

# 특정 파일
uv run pytest tests/api/v1/test_upload.py -v

# 특정 테스트
uv run pytest tests/api/v1/test_upload.py::TestUploadSuccess::test_upload_md_file -v
```

### 공통 Fixture (conftest.py)

| Fixture | 설명 |
|---------|------|
| `mock_settings` | AppSettings 모킹 |
| `mock_agent_service` | AgentService 모킹 |
| `mock_s3_service` | S3Service 모킹 |
| `mock_bedrock_kb_service` | BedrockKBService 모킹 |
| `mock_boto3_s3_client` | boto3 S3 클라이언트 모킹 |
| `mock_boto3_bedrock_client` | boto3 Bedrock 클라이언트 모킹 |
| `mock_broker` | Kafka 브로커 모킹 |
| `client` | 테스트 클라이언트 (서비스 모킹 적용) |
| `client_no_mock` | 테스트 클라이언트 (모킹 없음) |

### 테스트 작성 규칙

- 외부 서비스 호출은 모두 모킹 (AWS, Claude Agent, Kafka 등)
- 테스트 파일 구조는 src와 동일하게 유지
- E2E 테스트는 DI 컨테이너 오버라이드 사용

## 기술 스택

- Python 3.13+
- FastAPI
- FastStream + Kafka/MSK (이벤트 스트리밍)
- dependency-injector (DI 컨테이너)
- pydantic-settings (환경변수 관리)
- claude-agent-sdk (Claude Agent)
- boto3 (AWS S3, Bedrock)
- aws-msk-iam-sasl-signer-python (MSK IAM 인증)

## 환경변수

```bash
# 앱 설정
DEBUG=false

# Agent 설정
AGENT_CWD=/app/.agent_config
CLAUDE_CODE_USE_BEDROCK=true
ANTHROPIC_MODEL=apac.anthropic.claude-sonnet-4-20250514-v1:0

# S3 설정
S3_BUCKET=quanda-knowledge-base
S3_BASE_PREFIX=knowledge-base
S3_COMPACT_PREFIX=compacted-knowledge-base

# Bedrock Knowledge Base
BEDROCK_KB_ID=XQF4PRTCI6
BEDROCK_DATA_SOURCE_ID=ANASKNOJSA

# AWS (로컬: 환경변수 또는 기본 credentials chain, 원격: IRSA)
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Kafka/MSK 설정
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_USE_IAM=false  # true for MSK Serverless

# Topic 설정
KAFKA_TOPIC_COMPACT=knowledge-base.compact
KAFKA_CONSUMER_GROUP=quanda-kb-pipeline
```

## Bedrock 모델 ID

| 리전 | 모델 ID |
|------|---------|
| APAC (서울) | `apac.anthropic.claude-sonnet-4-20250514-v1:0` |
| US | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| Global | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |

## 주요 플로우

### 파일 업로드

1. **파일 업로드** (`POST /api/v1/upload`)
2. **Claude Agent로 메타데이터 추출** (summary, categories, tags)
   - Bedrock을 통한 Claude API 호출 (`CLAUDE_CODE_USE_BEDROCK=true`)
3. **S3 업로드** (파일 + 메타데이터)
   - 경로: `{base_prefix}/{filename}/{uuid}/{filename}`
   - 메타데이터: `{filename}.metadata.json` (Bedrock KB 형식)
4. **Bedrock KB 동기화** (start_ingestion_job)

### Compact (문서 정리/병합)

1. **이벤트 발행** (`POST /api/v1/compact` 또는 외부 Kafka producer)
2. **Kafka 토픽 수신** (`knowledge-base.compact`)
3. **S3에서 문서 로드** → Claude로 유사 문서 그룹 분석 → 문서 병합
4. **병합된 문서 S3 업로드** (`{compact_prefix}/` 하위)
5. **기존 문서 삭제** → **Bedrock KB 동기화**

## 아키텍처

```
┌──────────────────────────┐        ┌─────────┐
│ FastAPI + FastStream     │◀──────▶│   MSK   │
│ (API + Event Consumer)   │        │ (Kafka) │
└──────────────────────────┘        └─────────┘
```

- 앱 하나로 API 서빙 + Kafka 이벤트 컨슈밍 동시 처리
- FastAPI lifespan에서 broker 시작/종료 관리
- DI 컨테이너로 외부 서비스 → 비즈니스 서비스 → 이벤트 핸들러 주입

## S3 메타데이터 형식 (Bedrock KB)

```json
{
  "metadataAttributes": {
    "summary": "문서 요약 (2-3문장)",
    "categories": "카테고리1,카테고리2",
    "tags": "태그1,태그2,태그3",
    "source_type": "md",
    "created_at": "2026-02-05T00:00:00Z"
  }
}
```

## 개발 명령어

```bash
# 의존성 설치
make install

# 전체 실행 (API + Kafka)
make run

# API 서버만 실행
make run-api

# 코드 포맷팅
make format

# CI 체크 (린트 + 테스트)
make check

# 테스트만
make test

# 린트만
make lint

# Kafka 로컬 실행
make kafka-up

# 수동 compact 이벤트 발행
make compact

# 종료
make compose-down
```

## API

```bash
# 헬스체크
curl http://localhost:8000/health

# 파일 업로드
curl -X POST http://localhost:8000/api/v1/upload -F "file=@README.md"

# Compact 이벤트 발행
curl -X POST http://localhost:8000/api/v1/compact
```

## Docker

```bash
# 이미지 빌드
make docker-build

# 컨테이너 실행 (환경변수 설정 필요)
make docker-run \
  S3_BUCKET=quanda-knowledge-base \
  BEDROCK_KB_ID=XQF4PRTCI6 \
  BEDROCK_DATA_SOURCE_ID=ANASKNOJSA \
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# 로그 확인
docker logs quanda-kb
```

## MSK 연결 (프로덕션)

```bash
# MSK Serverless with IAM 인증 (IRSA 사용)
KAFKA_BOOTSTRAP_SERVERS=boot-xxx.c3.kafka-serverless.ap-northeast-2.amazonaws.com:9098
KAFKA_USE_IAM=true
```

- MSK Serverless는 VPC 내부에서만 접근 가능 (프라이빗 엔드포인트)
- 로컬 개발은 docker-compose의 로컬 Kafka 사용 (`KAFKA_USE_IAM=false`)
- IAM 인증: `aiokafka.abc.AbstractTokenProvider` + `aws-msk-iam-sasl-signer` 사용

## Git 컨벤션

### 브랜치
- 형식: `{username}/{feature}`
- 예시: `mko/add-upload-api`, `wogus/fix-metadata-parsing`

### 릴리즈/태그
- 형식: `x.x.x` (SemVer, `v` prefix 없음)
- 예시: `0.1.0`, `1.0.0`, `1.2.3`
- GitHub Release 타이틀도 동일하게 `x.x.x` 형식
- CD 트리거: 태그 푸시 시 자동 배포

## 배포 (IRSA)

Kubernetes 환경에서 IRSA(IAM Roles for Service Accounts)를 사용하면 AWS credentials 환경변수 없이 자동으로 인증됨:
- S3 접근
- Bedrock Knowledge Base 동기화
- Bedrock Claude API 호출
- MSK Kafka 접근 (IAM 인증)

## 카테고리 목록

- 기술문서: API 문서, 기술 스펙, 아키텍처
- 가이드: 사용법, 튜토리얼
- 정책/규정: 사내 정책, 프로세스
- 보고서: 분석, 리서치, 성과
- 회의록: 미팅 노트, 의사결정
- 제안서: 프로젝트 제안, 기획
- 데이터: 데이터셋, 스키마
- 기타: 미분류
