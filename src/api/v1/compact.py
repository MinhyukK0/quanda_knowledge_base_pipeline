from fastapi import APIRouter

from src.conf.kafka import broker
from src.conf.settings import settings
from src.schema.v1.compact_event import CompactEvent

router = APIRouter()


@router.post("/compact")
async def publish_compact(dry_run: bool = False):
    """Compact 이벤트 발행"""
    event = CompactEvent(trigger="api", dry_run=dry_run)
    await broker.publish(event, topic=settings.kafka_topic_compact)
    return {"success": True, "event": event.model_dump(mode="json")}
