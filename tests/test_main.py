"""메인 앱 테스트 (헬스체크 등)"""

from httpx import AsyncClient


async def test_health_check(client_no_mock: AsyncClient):
    """GET /health - 정상 응답"""
    response = await client_no_mock.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
