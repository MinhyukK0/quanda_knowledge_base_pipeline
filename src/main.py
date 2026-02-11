import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.events  # noqa: F401 - 핸들러 등록
from src.api import api_router
from src.conf.container import create_container
from src.conf.kafka import broker, ensure_topics
from src.conf.settings import settings

logger = logging.getLogger(__name__)

container = create_container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 라이프사이클 관리"""
    await ensure_topics(settings.kafka_topics)
    await broker.start()
    yield
    await broker.stop()


app = FastAPI(
    title="Quanda Knowledge Base Pipeline",
    description="파일 업로드, Claude Agent 메타데이터 생성, S3 업로드 및 Bedrock KB 동기화",
    version="0.1.4",
    lifespan=lifespan,
)

app.container = container
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": app.version}
