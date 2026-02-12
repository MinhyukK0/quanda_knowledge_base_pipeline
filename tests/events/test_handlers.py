"""CompactService 및 이벤트 핸들러 테스트"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.compact import CompactService


@pytest.fixture
def mock_compact_services():
    """compact 서비스용 외부 서비스 모킹"""
    # S3 서비스 모킹
    mock_s3 = MagicMock()
    mock_s3.list_documents = MagicMock(return_value=[])
    mock_s3.get_document = MagicMock(return_value=b"test content")
    mock_s3.delete_objects = MagicMock(return_value={"success": True, "deleted": [], "errors": []})
    mock_s3.upload_file_with_metadata = AsyncMock(return_value={"success": True, "file": {}, "metadata": {}})

    # Bedrock 서비스 모킹
    mock_bedrock = MagicMock()
    mock_bedrock.start_sync = AsyncMock(return_value={"success": True, "ingestion_job_id": "test-job"})

    # Agent 서비스 모킹
    mock_agent = MagicMock()
    mock_agent.find_similar_documents = AsyncMock(return_value={"delete": [], "groups": []})
    mock_agent.merge_documents = AsyncMock(
        return_value={
            "content": "merged content",
            "metadata": {"summary": "merged", "categories": [], "tags": []},
            "directory": "test-category",
            "filename": "merged.md",
        }
    )

    return {
        "s3": mock_s3,
        "bedrock": mock_bedrock,
        "agent": mock_agent,
    }


@pytest.fixture
def compact_service(mock_compact_services):
    """CompactService 인스턴스 (모킹된 의존성)"""
    return CompactService(
        s3_service=mock_compact_services["s3"],
        bedrock_kb_service=mock_compact_services["bedrock"],
        agent_service=mock_compact_services["agent"],
    )


class TestCompactServiceNoDocuments:
    """문서 없을 때 테스트"""

    @patch("src.services.compact.settings")
    async def test_no_documents(self, mock_settings, compact_service, mock_compact_services):
        """문서 없으면 조기 종료"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"

        result = await compact_service.run()

        assert result["status"] == "completed"
        assert result["merged"] == 0
        assert result["deleted"] == 0


class TestCompactServiceSingleDocument:
    """단일 문서 테스트"""

    @patch("src.services.compact.settings")
    async def test_single_document_no_merge(self, mock_settings, compact_service, mock_compact_services):
        """단일 문서는 병합하지 않음"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"

        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "knowledge-base/doc1/uuid1/file1.md", "size": 100, "last_modified": "2024-01-01T00:00:00Z"}
        ]
        mock_compact_services["agent"].find_similar_documents.return_value = {
            "delete": [],
            "groups": [["knowledge-base/doc1/uuid1/file1.md"]],
        }

        result = await compact_service.run()

        assert result["merged"] == 0
        mock_compact_services["agent"].merge_documents.assert_not_called()


class TestCompactServiceMerge:
    """문서 병합 테스트"""

    @patch("src.services.compact.settings")
    async def test_merge_similar_documents(self, mock_settings, compact_service, mock_compact_services):
        """유사 문서 병합"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"
        mock_settings.s3_compact_prefix = "compacted-knowledge-base"

        # 2개의 유사 문서 설정
        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "knowledge-base/doc1/uuid1/file1.md", "size": 100, "last_modified": "2024-01-01T00:00:00Z"},
            {"key": "knowledge-base/doc2/uuid2/file2.md", "size": 150, "last_modified": "2024-01-02T00:00:00Z"},
        ]

        # 메타데이터 응답
        def get_document_side_effect(key):
            if key.endswith(".metadata.json"):
                return json.dumps(
                    {
                        "metadataAttributes": {
                            "summary": "test summary",
                            "categories": "기술문서",
                            "tags": "test",
                        }
                    }
                ).encode()
            return b"# Test Document\n\nContent here"

        mock_compact_services["s3"].get_document.side_effect = get_document_side_effect

        # 유사 문서 그룹
        mock_compact_services["agent"].find_similar_documents.return_value = {
            "delete": [],
            "groups": [["knowledge-base/doc1/uuid1/file1.md", "knowledge-base/doc2/uuid2/file2.md"]],
        }

        # 병합 결과
        mock_compact_services["agent"].merge_documents.return_value = {
            "content": "# Merged Document\n\nMerged content",
            "metadata": {"summary": "merged", "categories": ["기술문서"], "tags": ["merged"]},
            "directory": "test-docs",
            "filename": "file1.md",
        }

        # 삭제 결과
        mock_compact_services["s3"].delete_objects.return_value = {
            "success": True,
            "deleted": [
                "knowledge-base/doc2/uuid2/file2.md",
                "knowledge-base/doc2/uuid2/file2.md.metadata.json",
            ],
            "errors": [],
        }

        result = await compact_service.run()

        assert result["status"] == "completed"
        assert result["merged"] == 1
        assert result["deleted"] == 2

        # 병합 호출 확인
        mock_compact_services["agent"].merge_documents.assert_called_once()

        # 업로드 호출 확인
        mock_compact_services["s3"].upload_file_with_metadata.assert_called_once()

        # 삭제 호출 확인
        mock_compact_services["s3"].delete_objects.assert_called_once()
        delete_args = mock_compact_services["s3"].delete_objects.call_args[0][0]
        assert "knowledge-base/doc2/uuid2/file2.md" in delete_args
        assert "knowledge-base/doc2/uuid2/file2.md.metadata.json" in delete_args

        # KB 동기화 호출 확인
        mock_compact_services["bedrock"].start_sync.assert_called_once()


class TestCompactServiceMultipleGroups:
    """여러 그룹 테스트"""

    @patch("src.services.compact.settings")
    async def test_multiple_groups(self, mock_settings, compact_service, mock_compact_services):
        """여러 그룹 처리"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"
        mock_settings.s3_compact_prefix = "compacted-knowledge-base"

        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "kb/g1/doc1.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/g1/doc2.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/g2/doc3.md", "size": 100, "last_modified": "2024-01-01"},
        ]

        mock_compact_services["s3"].get_document.return_value = b"content"

        # 첫 번째 그룹만 2개 이상
        mock_compact_services["agent"].find_similar_documents.return_value = {
            "delete": [],
            "groups": [["kb/g1/doc1.md", "kb/g1/doc2.md"], ["kb/g2/doc3.md"]],
        }

        mock_compact_services["s3"].delete_objects.return_value = {
            "success": True,
            "deleted": ["kb/g1/doc2.md"],
            "errors": [],
        }

        result = await compact_service.run()

        # 첫 번째 그룹만 병합
        assert result["merged"] == 1
        assert mock_compact_services["agent"].merge_documents.call_count == 1


class TestCompactServiceError:
    """에러 처리 테스트"""

    @patch("src.services.compact.settings")
    async def test_upload_failure_continues(self, mock_settings, compact_service, mock_compact_services):
        """업로드 실패해도 다른 그룹 계속 처리"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"
        mock_settings.s3_compact_prefix = "compacted-knowledge-base"

        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "kb/doc1.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/doc2.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/doc3.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/doc4.md", "size": 100, "last_modified": "2024-01-01"},
        ]
        mock_compact_services["s3"].get_document.return_value = b"content"

        mock_compact_services["agent"].find_similar_documents.return_value = {
            "delete": [],
            "groups": [["kb/doc1.md", "kb/doc2.md"], ["kb/doc3.md", "kb/doc4.md"]],
        }

        # 첫 번째 업로드 실패, 두 번째 성공
        mock_compact_services["s3"].upload_file_with_metadata.side_effect = [
            {"success": False, "error": "Upload failed"},
            {"success": True, "file": {}, "metadata": {}},
        ]

        mock_compact_services["s3"].delete_objects.return_value = {
            "success": True,
            "deleted": ["kb/doc4.md"],
            "errors": [],
        }

        result = await compact_service.run()

        # 두 번째 그룹만 병합 성공
        assert result["merged"] == 1


class TestLoadDocuments:
    """_load_documents 메서드 테스트"""

    def test_filters_metadata_files(self, compact_service, mock_compact_services):
        """메타데이터 파일 필터링"""
        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "kb/doc1.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/doc1.md.metadata.json", "size": 50, "last_modified": "2024-01-01"},
        ]
        mock_compact_services["s3"].get_document.return_value = b"content"

        docs = compact_service._load_documents("kb")

        assert len(docs) == 1
        assert docs[0]["key"] == "kb/doc1.md"

    def test_handles_missing_metadata(self, compact_service, mock_compact_services):
        """메타데이터 파일 없을 때"""
        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "kb/doc1.md", "size": 100, "last_modified": "2024-01-01"},
        ]

        # 문서는 반환하지만 메타데이터는 예외
        def get_doc(key):
            if key.endswith(".metadata.json"):
                raise Exception("Not found")
            return b"content"

        mock_compact_services["s3"].get_document.side_effect = get_doc

        docs = compact_service._load_documents("kb")

        assert len(docs) == 1
        assert docs[0]["metadata"] == {}

    def test_handles_document_load_failure(self, compact_service, mock_compact_services):
        """문서 로드 실패 시 건너뛰기"""
        mock_compact_services["s3"].list_documents.return_value = [
            {"key": "kb/doc1.md", "size": 100, "last_modified": "2024-01-01"},
            {"key": "kb/doc2.md", "size": 100, "last_modified": "2024-01-01"},
        ]

        call_count = [0]

        def get_doc(key):
            if key.endswith(".metadata.json"):
                return json.dumps({"metadataAttributes": {}}).encode()
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Load failed")
            return b"content"

        mock_compact_services["s3"].get_document.side_effect = get_doc

        docs = compact_service._load_documents("kb")

        assert len(docs) == 1
        assert docs[0]["key"] == "kb/doc2.md"


class TestHandleCompact:
    """handle_compact 핸들러 테스트"""

    @patch("src.services.compact.settings")
    async def test_handle_compact_success(self, mock_settings, compact_service):
        """서비스 실행 성공 케이스"""
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.s3_base_prefix = "knowledge-base"

        from src.schema.v1.compact_event import CompactResult

        result = await compact_service.run()

        compact_result = CompactResult(**result)
        assert compact_result.status == "completed"
        assert compact_result.merged == 0
        assert compact_result.deleted == 0
