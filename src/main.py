from fastapi import FastAPI

from src.api import api_router
from src.conf.container import create_container

container = create_container()

app = FastAPI(
    title="Quanda Knowledge Base Pipeline",
    description="파일 업로드, Claude Agent 메타데이터 생성, S3 업로드 및 Bedrock KB 동기화",
    version="0.1.0",
)

app.container = container
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
