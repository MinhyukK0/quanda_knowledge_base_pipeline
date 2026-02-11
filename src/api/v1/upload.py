import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, UploadFile

from src.conf.container import Container
from src.conf.settings import settings
from src.external_service.agent import AgentService
from src.external_service.bedrock import BedrockKBService
from src.external_service.s3 import S3Service

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


@router.post("/upload")
@inject
async def upload_file(
    file: UploadFile = File(...),
    agent_service: AgentService = Depends(Provide[Container.agent_service]),
    s3_service: S3Service = Depends(Provide[Container.s3_service]),
    bedrock_kb_service: BedrockKBService = Depends(Provide[Container.bedrock_kb_service]),
):
    """
    파일 업로드 엔드포인트

    - file: 업로드할 파일 (PDF, DOCX, TXT, MD, CSV)
    """
    # 파일 확장자 검증
    file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        return {
            "success": False,
            "error": f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(ALLOWED_EXTENSIONS)}",
        }

    # 디렉토리 자동 생성: {base_prefix}/{filename}/{uuid}/
    file_base_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
    directory = f"{settings.s3_base_prefix}/{file_base_name}/{uuid.uuid4()}"

    # 파일 읽기
    file_content = await file.read()

    # Agent 호출하여 메타데이터 생성
    metadata = await agent_service.analyze_file(
        file_content=file_content.decode("utf-8", errors="ignore"),
        filename=file.filename,
    )

    # S3 업로드
    upload_result = await s3_service.upload_file_with_metadata(
        file_content=file_content,
        directory=directory,
        filename=file.filename,
        metadata=metadata,
        content_type=file.content_type,
    )

    if not upload_result["success"]:
        return upload_result

    # Bedrock Knowledge Base 동기화
    sync_result = await bedrock_kb_service.start_sync()

    return {
        **upload_result,
        "sync": sync_result,
    }
