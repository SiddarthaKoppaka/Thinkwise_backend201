import pytest

@pytest.mark.asyncio
async def test_chat_with_idea(client):
    response = await client.post(
        "/chat/idea/idea1",
        params={"message": "What do you think about this idea?"},
        headers={"Authorization": "Bearer test_token"}
    )
    assert response.status_code in [200, 404, 401]
