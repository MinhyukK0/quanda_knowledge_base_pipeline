from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 앱 설정
    debug: bool = False

    # Agent 설정
    agent_max_turns: int = 10
    agent_cwd: str | None = None
    claude_code_use_bedrock: bool = False
    anthropic_model: str | None = None

    # S3 설정
    s3_bucket: str = ""
    s3_base_prefix: str = "knowledge-base"

    # Bedrock Knowledge Base 설정
    bedrock_kb_id: str = ""
    bedrock_data_source_id: str = ""

    # AWS 설정 (로컬: 환경변수로 키 입력, 원격: IRSA)
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None


settings = AppSettings()
