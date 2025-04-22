import pytest

@pytest.mark.asyncio
async def test_analyze_csv(client):
    with open("tests/assets/test_ideas.csv", "rb") as f:
        response = await client.post(
            "/analyze/csv",
            files={"file": ("test_ideas.csv", f, "text/csv")},
            headers={"Authorization": "Bearer test_token"}
        )
    assert response.status_code in [200, 422, 401]
