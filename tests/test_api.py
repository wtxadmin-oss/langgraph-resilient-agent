import pytest

from resilient_agent.api import health


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    response = await health()

    assert response == {"status": "ok"}
