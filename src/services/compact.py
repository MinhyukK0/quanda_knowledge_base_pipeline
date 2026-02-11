"""Compact 서비스 - 문서 정리 및 최적화"""

import json
import logging

from src.conf.settings import settings
from src.external_service.agent import AgentService
from src.external_service.bedrock import BedrockKBService
from src.external_service.s3 import S3Service

logger = logging.getLogger(__name__)


class CompactService:
    """문서 정리 및 최적화 서비스"""

    def __init__(
        self,
        s3_service: S3Service,
        bedrock_kb_service: BedrockKBService,
        agent_service: AgentService,
    ):
        self._s3 = s3_service
        self._bedrock = bedrock_kb_service
        self._agent = agent_service

    def _load_documents(self, prefix: str) -> list[dict]:
        """S3에서 문서 및 메타데이터 로드

        Returns:
            [{key, content, metadata}, ...]
        """
        all_objects = self._s3.list_documents(prefix)

        # 메타데이터 파일을 제외한 문서만 필터링
        doc_keys = [obj["key"] for obj in all_objects if not obj["key"].endswith(".metadata.json")]

        documents = []
        for key in doc_keys:
            try:
                content = self._s3.get_document(key)
                metadata_key = f"{key}.metadata.json"

                # 메타데이터 파일 조회
                try:
                    metadata_content = self._s3.get_document(metadata_key)
                    metadata_json = json.loads(metadata_content.decode("utf-8"))
                    # Bedrock 메타데이터 형식에서 attributes 추출
                    metadata = metadata_json.get("metadataAttributes", metadata_json)
                except Exception:
                    metadata = {}

                documents.append(
                    {
                        "key": key,
                        "content": content,
                        "metadata": metadata,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to load document {key}: {e}")
                continue

        return documents

    async def run(self) -> dict:
        """Compact 실행"""
        prefix = settings.s3_base_prefix

        # 1. S3에서 문서 로드
        logger.info(f"Loading documents from s3://{settings.s3_bucket}/{prefix}")
        documents = self._load_documents(prefix)

        if not documents:
            logger.info("No documents found")
            return {"status": "completed", "merged": 0, "deleted": 0}

        logger.info(f"Found {len(documents)} documents")

        # 2. Claude로 유사 문서 그룹 분석
        logger.info("Analyzing document similarity...")
        groups = await self._agent.find_similar_documents(documents)

        # key -> document 매핑
        doc_map = {doc["key"]: doc for doc in documents}

        merged_count = 0
        deleted_count = 0
        deleted_keys = []

        # 3. 각 그룹 처리
        for group in groups:
            if len(group) <= 1:
                continue

            group_docs = [doc_map[key] for key in group if key in doc_map]
            if len(group_docs) <= 1:
                continue

            logger.info(f"Merging {len(group_docs)} documents: {group}")

            # 4. Claude로 문서 병합
            merged = await self._agent.merge_documents(group_docs)

            # 5. 병합된 문서를 compact prefix에 업로드
            output_directory = f"{settings.s3_compact_prefix}/{merged['directory']}"

            content = merged["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")

            upload_result = await self._s3.upload_file_with_metadata(
                file_content=content,
                directory=output_directory,
                filename=merged["filename"],
                metadata=merged["metadata"],
            )

            if not upload_result.get("success"):
                logger.error(f"Failed to upload merged document: {upload_result}")
                continue

            merged_count += 1

            # 6. 기존 문서들 삭제
            keys_to_delete = []
            for key in group:
                keys_to_delete.append(key)
                keys_to_delete.append(f"{key}.metadata.json")

            if keys_to_delete:
                delete_result = self._s3.delete_objects(keys_to_delete)
                deleted_count += len(delete_result.get("deleted", []))
                deleted_keys.extend(delete_result.get("deleted", []))

        # 7. Bedrock KB 동기화
        if merged_count > 0:
            logger.info("Starting Bedrock KB sync...")
            sync_result = await self._bedrock.start_sync()
            if sync_result.get("success"):
                logger.info(f"KB sync started: job_id={sync_result.get('ingestion_job_id')}")
            else:
                logger.error(f"KB sync failed: {sync_result.get('error')}")

        return {
            "status": "completed",
            "merged": merged_count,
            "deleted": deleted_count,
            "deleted_keys": deleted_keys,
        }
