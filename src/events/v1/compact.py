"""Compact 이벤트 핸들러"""

import logging

from dependency_injector.wiring import Provide, inject

from src.conf.container import Container
from src.conf.kafka import broker
from src.conf.settings import settings
from src.schema.v1.compact_event import CompactEvent, CompactResult
from src.services.compact import CompactService

logger = logging.getLogger(__name__)


@broker.subscriber(settings.kafka_topic_compact, group_id=settings.kafka_consumer_group)
@inject
async def handle_compact(
    event: CompactEvent,
    compact_service: CompactService = Provide[Container.compact_service],
) -> CompactResult:
    """Compact 이벤트 처리"""
    logger.info(f"Received compact event: trigger={event.trigger}")

    try:
        result = await compact_service.run()
        logger.info(f"Compact completed: {result}")
        return CompactResult(**result)
    except Exception as e:
        logger.exception(f"Compact failed: {e}")
        return CompactResult(status="failed", merged=0, deleted=0, deleted_keys=[])
