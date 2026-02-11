"""S3Service 테스트"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


class TestS3ServiceListDocuments:
    """list_documents 메서드 테스트"""

    def test_list_documents_success(self):
        """문서 목록 조회 성공"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            # paginator 설정
            mock_paginator = MagicMock()
            mock_s3.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "kb/doc1.md",
                            "Size": 100,
                            "LastModified": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z"),
                        },
                        {
                            "Key": "kb/doc2.md",
                            "Size": 200,
                            "LastModified": MagicMock(isoformat=lambda: "2024-01-02T00:00:00Z"),
                        },
                    ]
                }
            ]

            service = S3Service(bucket="test-bucket")
            result = service.list_documents("kb")

            assert len(result) == 2
            assert result[0]["key"] == "kb/doc1.md"
            assert result[0]["size"] == 100
            assert result[1]["key"] == "kb/doc2.md"

    def test_list_documents_empty(self):
        """문서 없음"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_paginator = MagicMock()
            mock_s3.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.return_value = [{"Contents": []}]

            service = S3Service(bucket="test-bucket")
            result = service.list_documents("kb")

            assert result == []

    def test_list_documents_error(self):
        """조회 실패 시 빈 리스트 반환"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_paginator = MagicMock()
            mock_s3.get_paginator.return_value = mock_paginator
            mock_paginator.paginate.side_effect = ClientError(
                {"Error": {"Code": "403", "Message": "Forbidden"}}, "ListObjects"
            )

            service = S3Service(bucket="test-bucket")
            result = service.list_documents("kb")

            assert result == []


class TestS3ServiceGetDocument:
    """get_document 메서드 테스트"""

    def test_get_document_success(self):
        """문서 조회 성공"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_body = MagicMock()
            mock_body.read.return_value = b"document content"
            mock_s3.get_object.return_value = {"Body": mock_body}

            service = S3Service(bucket="test-bucket")
            result = service.get_document("kb/doc1.md")

            assert result == b"document content"
            mock_s3.get_object.assert_called_once_with(Bucket="test-bucket", Key="kb/doc1.md")

    def test_get_document_not_found(self):
        """문서 없음"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_s3.get_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
            )

            service = S3Service(bucket="test-bucket")

            with pytest.raises(ClientError):
                service.get_document("kb/notfound.md")


class TestS3ServiceDeleteObjects:
    """delete_objects 메서드 테스트"""

    def test_delete_objects_success(self):
        """다중 삭제 성공"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_s3.delete_objects.return_value = {
                "Deleted": [{"Key": "kb/doc1.md"}, {"Key": "kb/doc2.md"}],
                "Errors": [],
            }

            service = S3Service(bucket="test-bucket")
            result = service.delete_objects(["kb/doc1.md", "kb/doc2.md"])

            assert result["success"] is True
            assert result["deleted"] == ["kb/doc1.md", "kb/doc2.md"]
            assert result["errors"] == []

    def test_delete_objects_empty_list(self):
        """빈 리스트"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            service = S3Service(bucket="test-bucket")
            result = service.delete_objects([])

            assert result["success"] is True
            assert result["deleted"] == []
            mock_s3.delete_objects.assert_not_called()

    def test_delete_objects_partial_failure(self):
        """부분 삭제 실패"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_s3.delete_objects.return_value = {
                "Deleted": [{"Key": "kb/doc1.md"}],
                "Errors": [{"Key": "kb/doc2.md", "Code": "AccessDenied"}],
            }

            service = S3Service(bucket="test-bucket")
            result = service.delete_objects(["kb/doc1.md", "kb/doc2.md"])

            assert result["success"] is True
            assert result["deleted"] == ["kb/doc1.md"]
            assert len(result["errors"]) == 1

    def test_delete_objects_error(self):
        """삭제 API 실패"""
        from src.external_service.s3 import S3Service

        with patch("boto3.client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            mock_s3.delete_objects.side_effect = ClientError(
                {"Error": {"Code": "403", "Message": "Forbidden"}}, "DeleteObjects"
            )

            service = S3Service(bucket="test-bucket")
            result = service.delete_objects(["kb/doc1.md"])

            assert result["success"] is False
            assert result["deleted"] == []
            assert len(result["errors"]) > 0
