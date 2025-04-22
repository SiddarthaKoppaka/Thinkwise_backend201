import pytest

@pytest.mark.asyncio
async def test_get_all_ideas(client):
    response = await client.get("/ideas", headers={"Authorization": "Bearer test_token"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_get_analytics(client):
    response = await client.get("/ideas/analytics", headers={"Authorization": "Bearer test_token"})
    assert response.status_code in [200, 401]
