import pytest

from tests.conftest import TEST_BOX_ID, TEST_CUSTOMER_ID, mock_redis


@pytest.mark.anyio
async def test_get_my_box(client, seed_box):
    resp = await client.get("/me/box", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == TEST_BOX_ID
    assert data["status"] == "active"
    assert data["model"] == "kimi-coding/k2p5"


@pytest.mark.anyio
async def test_get_my_box_not_found(client, seed_customer):
    resp = await client.get("/me/box", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_my_box(client, seed_box):
    resp = await client.post("/me/box/update", json={"model": "gpt-4o"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data


@pytest.mark.anyio
async def test_update_my_box_no_fields(client, seed_box):
    resp = await client.post("/me/box/update", json={})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_update_my_box_no_box(client, seed_customer):
    resp = await client.post("/me/box/update", json={"model": "gpt-4o"})
    assert resp.status_code == 404
