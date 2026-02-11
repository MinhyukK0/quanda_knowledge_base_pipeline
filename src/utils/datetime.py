"""날짜/시간 유틸리티"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """현재 UTC 시간 반환"""
    return datetime.now(UTC)
