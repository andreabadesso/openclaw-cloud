import pytest

from tests.conftest import TEST_CUSTOMER_ID


@pytest.mark.anyio
async def test_get_my_usage(client, seed_usage):
    resp = await client.get("/me/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tokens_used"] == 500_000
    assert data["tokens_limit"] == 1_000_000
    assert data["pct_used"] == 50.0


@pytest.mark.anyio
async def test_get_my_usage_not_found(client, seed_customer):
    resp = await client.get("/me/usage")
    assert resp.status_code == 404
