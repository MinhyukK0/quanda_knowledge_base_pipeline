from dependency_injector import containers, providers

from src.conf.settings import settings
from src.external_service.agent import AgentService
from src.external_service.bedrock import BedrockKBService
from src.external_service.s3 import S3Service
from src.services.compact import CompactService


class Container(containers.DeclarativeContainer):
    """DI 컨테이너 - 애플리케이션 서비스 관리"""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.api.v1.upload",
        ]
    )

    # External Services
    agent_service = providers.Singleton(
        AgentService,
        system_prompt="You are a document analysis assistant. Analyze files and extract metadata.",
        max_turns=10,
        cwd=settings.agent_cwd,
        use_bedrock=settings.claude_code_use_bedrock,
        model=settings.anthropic_model,
    )

    s3_service = providers.Singleton(
        S3Service,
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    bedrock_kb_service = providers.Singleton(
        BedrockKBService,
        knowledge_base_id=settings.bedrock_kb_id,
        data_source_id=settings.bedrock_data_source_id,
        region=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    # Services
    compact_service = providers.Singleton(
        CompactService,
        s3_service=s3_service,
        bedrock_kb_service=bedrock_kb_service,
        agent_service=agent_service,
    )


def create_container() -> Container:
    """컨테이너 생성"""
    return Container()
