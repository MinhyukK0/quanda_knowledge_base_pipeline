"""이벤트 핸들러 등록

도메인별 핸들러 모듈을 import하여 broker에 subscriber를 등록합니다.
새 도메인 추가 시 여기에 import를 추가하세요.
"""

from src.events import v1  # noqa: F401
