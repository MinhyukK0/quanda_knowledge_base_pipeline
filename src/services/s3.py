import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


class S3Service:
    """S3 업로드 서비스"""

    def __init__(
        self,
        bucket: str,
        region: str = "ap-northeast-2",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        self.bucket = bucket
        self.region = region
        # 빈 문자열은 None으로 처리 (기본 credentials chain 사용)
        self.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=aws_access_key_id or None,
            aws_secret_access_key=aws_secret_access_key or None,
        )

    async def upload_file(
        self,
        file_content: bytes,
        directory: str,
        filename: str,
        content_type: str | None = None,
    ) -> dict:
        """파일을 S3에 업로드"""
        key = f"{directory.strip('/')}/{filename}"

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_content,
                **extra_args,
            )
            return {
                "success": True,
                "bucket": self.bucket,
                "key": key,
                "url": f"s3://{self.bucket}/{key}",
            }
        except ClientError as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _to_bedrock_metadata(self, metadata: dict, source_type: str) -> dict:
        """메타데이터를 Bedrock KB 형식으로 변환"""
        attributes = {}

        for key, value in metadata.items():
            if isinstance(value, list):
                # 배열은 쉼표로 구분된 문자열로 변환
                attributes[key] = {
                    "value": {"type": "STRING", "stringValue": ",".join(str(v) for v in value)},
                    "includeForEmbedding": True,
                }
            elif isinstance(value, bool):
                attributes[key] = {
                    "value": {"type": "BOOLEAN", "booleanValue": value},
                    "includeForEmbedding": True,
                }
            elif isinstance(value, (int, float)):
                attributes[key] = {
                    "value": {"type": "NUMBER", "numberValue": value},
                    "includeForEmbedding": True,
                }
            else:
                attributes[key] = {
                    "value": {"type": "STRING", "stringValue": str(value)},
                    "includeForEmbedding": True,
                }

        # source_type, created_at 추가
        attributes["source_type"] = {
            "value": {"type": "STRING", "stringValue": source_type},
            "includeForEmbedding": False,
        }
        attributes["created_at"] = {
            "value": {"type": "STRING", "stringValue": datetime.now(timezone.utc).isoformat()},
            "includeForEmbedding": False,
        }

        return {"metadataAttributes": attributes}

    async def upload_metadata(
        self,
        directory: str,
        filename: str,
        metadata: dict,
        source_type: str,
    ) -> dict:
        """메타데이터를 {filename}.metadata.json 파일로 S3에 업로드"""
        key = f"{directory.strip('/')}/{filename}.metadata.json"

        bedrock_metadata = self._to_bedrock_metadata(metadata, source_type)

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(bedrock_metadata, ensure_ascii=False, indent=2),
                ContentType="application/json",
            )
            return {
                "success": True,
                "bucket": self.bucket,
                "key": key,
                "url": f"s3://{self.bucket}/{key}",
            }
        except ClientError as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def upload_file_with_metadata(
        self,
        file_content: bytes,
        directory: str,
        filename: str,
        metadata: dict,
        content_type: str | None = None,
    ) -> dict:
        """파일과 메타데이터를 함께 S3에 업로드"""
        source_type = filename.split(".")[-1].lower() if "." in filename else "unknown"

        file_result = await self.upload_file(
            file_content=file_content,
            directory=directory,
            filename=filename,
            content_type=content_type,
        )

        if not file_result["success"]:
            return file_result

        metadata_result = await self.upload_metadata(
            directory=directory,
            filename=filename,
            metadata=metadata,
            source_type=source_type,
        )

        return {
            "success": metadata_result["success"],
            "file": file_result,
            "metadata": metadata_result,
        }
