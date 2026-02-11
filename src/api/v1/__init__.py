from fastapi import APIRouter

from src.api.v1 import compact, upload

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(upload.router, tags=["upload"])
v1_router.include_router(compact.router, tags=["compact"])
