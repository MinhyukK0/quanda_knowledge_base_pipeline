"""테스트 공통 설정 및 모킹"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# =============================================================================
# 설정 모킹
# =============================================================================
@pytest.fixture
def mock_settings():
    """AppSettings 모킹"""
    with patch("src.conf.settings.settings") as mock:
        mock.debug = False
        mock.s3_bucket = "test-bucket"
        mock.s3_base_prefix = "knowledge-base"
        mock.s3_compact_prefix = "compacted-knowledge-base"
        mock.aws_region = "ap-northeast-2"
        mock.aws_access_key_id = "test-key"
        mock.aws_secret_access_key = "test-secret"
        mock.bedrock_kb_id = "test-kb-id"
        mock.bedrock_data_source_id = "test-ds-id"
        mock.agent_cwd = None
        mock.claude_code_use_bedrock = False
        mock.anthropic_model = None
        # Kafka 설정
        mock.kafka_bootstrap_servers = "localhost:9092"
        mock.kafka_use_iam = False
        mock.kafka_topic_compact = "knowledge-base.compact"
        mock.kafka_consumer_group = "quanda-kb-pipeline-test"
        yield mock


# =============================================================================
# 서비스 모킹
# =============================================================================
@pytest.fixture
def mock_agent_service():
    """AgentService 모킹"""
    mock = MagicMock()
    mock.analyze_file = AsyncMock(
        return_value={
            "summary": "테스트 문서 요약입니다.",
            "categories": ["기술문서"],
            "tags": ["테스트", "API"],
        }
    )
    # Compact 기능 관련 메서드
    mock.find_similar_documents = AsyncMock(return_value=[])
    mock.merge_documents = AsyncMock(
        return_value={
            "content": "병합된 내용",
            "metadata": {
                "summary": "병합된 요약",
                "categories": ["기술문서"],
                "tags": ["병합"],
            },
            "directory": "test-category",
            "filename": "merged.md",
        }
    )
    return mock


@pytest.fixture
def mock_s3_service():
    """S3Service 모킹"""
    mock = MagicMock()
    mock.upload_file = AsyncMock(
        return_value={
            "success": True,
            "bucket": "test-bucket",
            "key": "knowledge-base/test/uuid/test.md",
            "url": "s3://test-bucket/knowledge-base/test/uuid/test.md",
        }
    )
    mock.upload_metadata = AsyncMock(
        return_value={
            "success": True,
            "bucket": "test-bucket",
            "key": "knowledge-base/test/uuid/test.md.metadata.json",
            "url": "s3://test-bucket/knowledge-base/test/uuid/test.md.metadata.json",
        }
    )
    mock.upload_file_with_metadata = AsyncMock(
        return_value={
            "success": True,
            "file": {
                "success": True,
                "bucket": "test-bucket",
                "key": "knowledge-base/test/uuid/test.md",
                "url": "s3://test-bucket/knowledge-base/test/uuid/test.md",
            },
            "metadata": {
                "success": True,
                "bucket": "test-bucket",
                "key": "knowledge-base/test/uuid/test.md.metadata.json",
                "url": "s3://test-bucket/knowledge-base/test/uuid/test.md.metadata.json",
            },
        }
    )
    # Compact 기능 관련 메서드
    mock.list_documents = MagicMock(return_value=[])
    mock.get_document = MagicMock(return_value=b"test content")
    mock.delete_objects = MagicMock(return_value={"success": True, "deleted": [], "errors": []})
    return mock


@pytest.fixture
def mock_bedrock_kb_service():
    """BedrockKBService 모킹"""
    mock = MagicMock()
    mock.start_sync = AsyncMock(
        return_value={
            "success": True,
            "ingestion_job_id": "test-job-id",
            "status": "STARTING",
        }
    )
    mock.get_sync_status = AsyncMock(
        return_value={
            "success": True,
            "ingestion_job_id": "test-job-id",
            "status": "COMPLETE",
            "statistics": {},
        }
    )
    return mock


# =============================================================================
# boto3 클라이언트 모킹
# =============================================================================
@pytest.fixture
def mock_boto3_s3_client():
    """boto3 S3 클라이언트 모킹"""
    with patch("boto3.client") as mock_client:
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {}
        mock_client.return_value = mock_s3
        yield mock_s3


@pytest.fixture
def mock_boto3_bedrock_client():
    """boto3 Bedrock Agent 클라이언트 모킹"""
    with patch("boto3.client") as mock_client:
        mock_bedrock = MagicMock()
        mock_bedrock.start_ingestion_job.return_value = {
            "ingestionJob": {
                "ingestionJobId": "test-job-id",
                "status": "STARTING",
            }
        }
        mock_bedrock.get_ingestion_job.return_value = {
            "ingestionJob": {
                "ingestionJobId": "test-job-id",
                "status": "COMPLETE",
                "statistics": {},
            }
        }
        mock_client.return_value = mock_bedrock
        yield mock_bedrock


# =============================================================================
# Kafka 브로커 모킹
# =============================================================================
@pytest.fixture
def mock_broker():
    """Kafka 브로커 모킹"""
    mock = MagicMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.publish = AsyncMock()
    return mock


# =============================================================================
# API 테스트 클라이언트
# =============================================================================
@pytest.fixture
async def client(mock_agent_service, mock_s3_service, mock_bedrock_kb_service):
    """테스트 클라이언트 (서비스 모킹 적용)"""
    with patch("src.main.broker") as mock_broker:
        mock_broker.start = AsyncMock()
        mock_broker.stop = AsyncMock()

        from src.main import app

        # 컨테이너 서비스 오버라이드
        app.container.agent_service.override(mock_agent_service)
        app.container.s3_service.override(mock_s3_service)
        app.container.bedrock_kb_service.override(mock_bedrock_kb_service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

        # 오버라이드 해제
        app.container.agent_service.reset_override()
        app.container.s3_service.reset_override()
        app.container.bedrock_kb_service.reset_override()


@pytest.fixture
async def client_no_mock():
    """테스트 클라이언트 (모킹 없음, 브로커만 모킹)"""
    with patch("src.main.broker") as mock_broker:
        mock_broker.start = AsyncMock()
        mock_broker.stop = AsyncMock()

        from src.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
