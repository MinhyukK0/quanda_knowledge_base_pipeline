import boto3
from botocore.exceptions import ClientError


class BedrockKBService:
    """Bedrock Knowledge Base 동기화 서비스"""

    def __init__(
        self,
        knowledge_base_id: str,
        data_source_id: str,
        region: str = "ap-northeast-2",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ):
        self.knowledge_base_id = knowledge_base_id
        self.data_source_id = data_source_id
        # 빈 문자열은 None으로 처리 (기본 credentials chain 사용)
        self.client = boto3.client(
            "bedrock-agent",
            region_name=region,
            aws_access_key_id=aws_access_key_id or None,
            aws_secret_access_key=aws_secret_access_key or None,
        )

    async def start_sync(self) -> dict:
        """Knowledge Base 데이터 소스 동기화 시작"""
        try:
            response = self.client.start_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
            )
            return {
                "success": True,
                "ingestion_job_id": response["ingestionJob"]["ingestionJobId"],
                "status": response["ingestionJob"]["status"],
            }
        except ClientError as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def get_sync_status(self, ingestion_job_id: str) -> dict:
        """동기화 작업 상태 조회"""
        try:
            response = self.client.get_ingestion_job(
                knowledgeBaseId=self.knowledge_base_id,
                dataSourceId=self.data_source_id,
                ingestionJobId=ingestion_job_id,
            )
            return {
                "success": True,
                "ingestion_job_id": ingestion_job_id,
                "status": response["ingestionJob"]["status"],
                "statistics": response["ingestionJob"].get("statistics", {}),
            }
        except ClientError as e:
            return {
                "success": False,
                "error": str(e),
            }
