# Quanda Knowledge Base Pipeline

FastAPI 기반 파이프라인 서버 - 파일 업로드, Claude Agent 메타데이터 생성, S3 업로드 및 Bedrock KB 동기화

## 프로젝트 구조

```
src/
├── main.py                 # FastAPI 앱 엔트리포인트
├── api/
│   └── v1/
│       └── upload.py       # 파일 업로드 API
├── conf/
│   ├── settings.py         # AppSettings (pydantic-settings)
│   └── container.py        # DI 컨테이너 (dependency-injector)
└── services/
    ├── agent.py            # Claude Agent 서비스 (Bedrock 지원)
    ├── s3.py               # S3 업로드 서비스
    └── bedrock.py          # Bedrock KB 동기화 서비스

.agent_config/              # Claude Agent 설정
├── AGENT.md                # 에이전트 역할 정의
├── rules/
│   └── metadata-extraction.md  # 메타데이터 추출 규칙
└── skills/
    └── extract-metadata.md     # 메타데이터 추출 스킬
```

## 기술 스택

- Python 3.13+
- FastAPI
- dependency-injector (DI 컨테이너)
- pydantic-settings (환경변수 관리)
- claude-agent-sdk (Claude Agent)
- boto3 (AWS S3, Bedrock)

## 환경변수

```bash
# 앱 설정
DEBUG=false

# Agent 설정
AGENT_MAX_TURNS=10
AGENT_CWD=/app/.agent_config
CLAUDE_CODE_USE_BEDROCK=true
ANTHROPIC_MODEL=apac.anthropic.claude-sonnet-4-20250514-v1:0

# S3 설정
S3_BUCKET=quanda-knowledge-base
S3_BASE_PREFIX=knowledge-base

# Bedrock Knowledge Base
BEDROCK_KB_ID=XQF4PRTCI6
BEDROCK_DATA_SOURCE_ID=ANASKNOJSA

# AWS (로컬: 환경변수 또는 기본 credentials chain, 원격: IRSA)
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

## Bedrock 모델 ID

| 리전 | 모델 ID |
|------|---------|
| APAC (서울) | `apac.anthropic.claude-sonnet-4-20250514-v1:0` |
| US | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| Global | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |

## 주요 플로우

1. **파일 업로드** (`POST /api/v1/upload`)
2. **Claude Agent로 메타데이터 추출** (summary, categories, tags)
   - Bedrock을 통한 Claude API 호출 (`CLAUDE_CODE_USE_BEDROCK=true`)
3. **S3 업로드** (파일 + 메타데이터)
   - 경로: `{base_prefix}/{filename}/{uuid}/{filename}`
   - 메타데이터: `{filename}.metadata.json` (Bedrock KB 형식)
4. **Bedrock KB 동기화** (start_ingestion_job)

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

# 서버 실행
make run

# 코드 포맷팅
make format

# CI 체크 (린트 + 테스트)
make check

# 테스트만
make test

# 린트만
make lint
```

## API 테스트

```bash
# 헬스체크
curl http://localhost:8000/health

# 파일 업로드
curl -X POST http://localhost:8000/api/v1/upload -F "file=@README.md"
```

## Docker

```bash
# 이미지 빌드
make docker-build

# 컨테이너 실행 (환경변수 설정 필요)
make docker-run \
  S3_BUCKET=quanda-knowledge-base \
  BEDROCK_KB_ID=XQF4PRTCI6 \
  BEDROCK_DATA_SOURCE_ID=ANASKNOJSA

# 로그 확인
docker logs quanda-kb
```

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

## 카테고리 목록

- 기술문서: API 문서, 기술 스펙, 아키텍처
- 가이드: 사용법, 튜토리얼
- 정책/규정: 사내 정책, 프로세스
- 보고서: 분석, 리서치, 성과
- 회의록: 미팅 노트, 의사결정
- 제안서: 프로젝트 제안, 기획
- 데이터: 데이터셋, 스키마
- 기타: 미분류
