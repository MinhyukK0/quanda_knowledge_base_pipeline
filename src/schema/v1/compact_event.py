"""이벤트 스키마"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.utils.datetime import utc_now


class CompactEvent(BaseModel):
    """문서 정리 이벤트"""

    trigger: str = Field(default="scheduled", description="scheduled|manual|api")
    dry_run: bool = Field(default=False, description="True면 분석만 수행, 업로드/삭제 건너뜀")
    timestamp: datetime = Field(default_factory=utc_now)


class CompactResult(BaseModel):
    """Compact 결과"""

    status: str
    merged: int
    deleted: int
    deleted_keys: list[str] = []
