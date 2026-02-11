"""파일 업로드 API 테스트"""

import io
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


class TestUploadSuccess:
    """파일 업로드 성공 케이스"""

    async def test_upload_md_file(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """MD 파일 업로드 성공"""
        file_content = b"# Test Document\n\nThis is a test."
        files = {"file": ("test.md", io.BytesIO(file_content), "text/markdown")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "file" in data
        assert "metadata" in data
        assert "sync" in data
        assert data["sync"]["success"] is True

        # 서비스 호출 확인
        mock_agent_service.analyze_file.assert_called_once()
        mock_s3_service.upload_file_with_metadata.assert_called_once()
        mock_bedrock_kb_service.start_sync.assert_called_once()

    async def test_upload_txt_file(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """TXT 파일 업로드 성공"""
        file_content = b"Plain text content for testing."
        files = {"file": ("document.txt", io.BytesIO(file_content), "text/plain")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_upload_pdf_file(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """PDF 파일 업로드 성공"""
        file_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_upload_csv_file(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """CSV 파일 업로드 성공"""
        file_content = b"name,value\ntest,123"
        files = {"file": ("data.csv", io.BytesIO(file_content), "text/csv")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_upload_docx_file(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """DOCX 파일 업로드 성공"""
        file_content = b"PK fake docx content"
        files = {
            "file": (
                "document.docx",
                io.BytesIO(file_content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestUploadFailure:
    """파일 업로드 실패 케이스"""

    async def test_unsupported_extension(self, client: AsyncClient):
        """지원하지 않는 확장자"""
        file_content = b"console.log('hello');"
        files = {"file": ("script.js", io.BytesIO(file_content), "application/javascript")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "지원하지 않는 파일 형식" in data["error"]

    async def test_no_extension(self, client: AsyncClient):
        """확장자 없는 파일"""
        file_content = b"some content"
        files = {"file": ("noextension", io.BytesIO(file_content), "application/octet-stream")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    async def test_s3_upload_failure(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """S3 업로드 실패"""
        mock_s3_service.upload_file_with_metadata = AsyncMock(
            return_value={
                "success": False,
                "error": "S3 connection failed",
            }
        )

        file_content = b"# Test"
        files = {"file": ("test.md", io.BytesIO(file_content), "text/markdown")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "S3 connection failed" in data["error"]

        # Bedrock sync는 호출되지 않아야 함
        mock_bedrock_kb_service.start_sync.assert_not_called()

    async def test_without_file(self, client: AsyncClient):
        """파일 없이 요청"""
        response = await client.post("/api/v1/upload")

        assert response.status_code == 422  # Validation Error


class TestUploadBehavior:
    """파일 업로드 동작 검증"""

    async def test_metadata_extraction(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """메타데이터 추출 확인"""
        file_content = b"# API Documentation\n\nThis is the API docs."
        files = {"file": ("api-docs.md", io.BytesIO(file_content), "text/markdown")}

        response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200

        # analyze_file 호출 인자 확인
        call_args = mock_agent_service.analyze_file.call_args
        assert call_args.kwargs["filename"] == "api-docs.md"
        assert "API Documentation" in call_args.kwargs["file_content"]

    async def test_directory_structure(
        self,
        client: AsyncClient,
        mock_agent_service,
        mock_s3_service,
        mock_bedrock_kb_service,
    ):
        """S3 디렉토리 구조 확인"""
        file_content = b"test content"
        files = {"file": ("my-document.md", io.BytesIO(file_content), "text/markdown")}

        with patch("src.api.v1.upload.uuid.uuid4", return_value="test-uuid-1234"):
            response = await client.post("/api/v1/upload", files=files)

        assert response.status_code == 200

        # upload_file_with_metadata 호출 인자 확인
        call_args = mock_s3_service.upload_file_with_metadata.call_args
        assert "my-document" in call_args.kwargs["directory"]
        assert "test-uuid-1234" in call_args.kwargs["directory"]
        assert call_args.kwargs["filename"] == "my-document.md"
