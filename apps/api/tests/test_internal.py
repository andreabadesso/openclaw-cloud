import json
from unittest.mock import AsyncMock

import pytest

from tests.conftest import TEST_BOX_ID, TEST_BUNDLE_ID, TEST_CUSTOMER_ID, mock_redis


# --- Provision ---


@pytest.mark.anyio
async def test_provision_creates_customer_and_box(client, db, seed_bundle):
    resp = await client.post("/internal/provision", json={
        "telegram_bot_token": "tok_123",
        "telegram_user_id": 99999,
        "tier": "starter",
        "customer_email": "new@example.com",
        "bundle_id": TEST_BUNDLE_ID,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "customer_id" in data
    assert "box_id" in data
    assert "job_id" in data
    mock_redis.rpush.assert_called_once()


@pytest.mark.anyio
async def test_provision_multiple_boxes_allowed(client, seed_box, seed_bundle):
    """Multi-agent: provisioning a second box for existing customer should succeed."""
    resp = await client.post("/internal/provision", json={
        "telegram_bot_token": "tok_123",
        "telegram_user_id": 99999,
        "tier": "starter",
        "customer_email": "test@example.com",
        "bundle_id": TEST_BUNDLE_ID,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer_id"] == TEST_CUSTOMER_ID


@pytest.mark.anyio
async def test_provision_invalid_tier(client, seed_bundle):
    resp = await client.post("/internal/provision", json={
        "telegram_bot_token": "tok_123",
        "telegram_user_id": 99999,
        "tier": "invalid",
        "customer_email": "new@example.com",
        "bundle_id": TEST_BUNDLE_ID,
    })
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_provision_invalid_bundle(client):
    resp = await client.post("/internal/provision", json={
        "telegram_bot_token": "tok_123",
        "telegram_user_id": 99999,
        "tier": "starter",
        "customer_email": "new@example.com",
        "bundle_id": "00000000-0000-0000-0000-nonexistent00",
    })
    assert resp.status_code == 400


# --- Destroy ---


@pytest.mark.anyio
async def test_destroy_box(client, seed_box):
    resp = await client.post(f"/internal/destroy/{TEST_BOX_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data


@pytest.mark.anyio
async def test_destroy_box_not_found(client):
    resp = await client.post("/internal/destroy/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_destroy_already_destroyed(client, seed_box, db):
    from openclaw_api.models import Box, BoxStatus
    from sqlalchemy import select

    result = await db.execute(select(Box).where(Box.id == TEST_BOX_ID))
    box = result.scalar_one()
    box.status = BoxStatus.destroyed
    await db.commit()

    resp = await client.post(f"/internal/destroy/{TEST_BOX_ID}")
    assert resp.status_code == 409


# --- Suspend ---


@pytest.mark.anyio
async def test_suspend_box(client, seed_box):
    resp = await client.post(f"/internal/suspend/{TEST_BOX_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID


@pytest.mark.anyio
async def test_suspend_box_not_found(client):
    resp = await client.post("/internal/suspend/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_suspend_non_active_box(client, seed_box, db):
    from openclaw_api.models import Box, BoxStatus
    from sqlalchemy import select

    result = await db.execute(select(Box).where(Box.id == TEST_BOX_ID))
    box = result.scalar_one()
    box.status = BoxStatus.suspended
    await db.commit()

    resp = await client.post(f"/internal/suspend/{TEST_BOX_ID}")
    assert resp.status_code == 409


# --- Reactivate ---


@pytest.mark.anyio
async def test_reactivate_box(client, seed_box, db):
    from openclaw_api.models import Box, BoxStatus
    from sqlalchemy import select

    result = await db.execute(select(Box).where(Box.id == TEST_BOX_ID))
    box = result.scalar_one()
    box.status = BoxStatus.suspended
    await db.commit()

    resp = await client.post(f"/internal/reactivate/{TEST_BOX_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID


@pytest.mark.anyio
async def test_reactivate_non_suspended_box(client, seed_box):
    resp = await client.post(f"/internal/reactivate/{TEST_BOX_ID}")
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_reactivate_box_not_found(client):
    resp = await client.post("/internal/reactivate/nonexistent")
    assert resp.status_code == 404


# --- Update (new PATCH endpoint) ---


@pytest.mark.anyio
async def test_update_box(client, seed_box):
    resp = await client.patch(f"/internal/update/{TEST_BOX_ID}", json={
        "model": "gpt-4o",
        "thinking_level": "high",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data


@pytest.mark.anyio
async def test_update_box_no_fields(client, seed_box):
    resp = await client.patch(f"/internal/update/{TEST_BOX_ID}", json={})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_update_box_not_found(client):
    resp = await client.patch("/internal/update/nonexistent", json={"model": "gpt-4o"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_box_wrong_status(client, seed_box, db):
    from openclaw_api.models import Box, BoxStatus
    from sqlalchemy import select

    result = await db.execute(select(Box).where(Box.id == TEST_BOX_ID))
    box = result.scalar_one()
    box.status = BoxStatus.suspended
    await db.commit()

    resp = await client.patch(f"/internal/update/{TEST_BOX_ID}", json={"model": "gpt-4o"})
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_update_box_telegram_user_ids(client, seed_box):
    resp = await client.patch(f"/internal/update/{TEST_BOX_ID}", json={
        "telegram_user_ids": [111, 222],
    })
    assert resp.status_code == 200


# --- Resize (new endpoint) ---


@pytest.mark.anyio
async def test_resize_box(client, seed_box):
    resp = await client.post(f"/internal/resize/{TEST_BOX_ID}", json={"new_tier": "pro"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data


@pytest.mark.anyio
async def test_resize_box_same_tier(client, seed_box):
    resp = await client.post(f"/internal/resize/{TEST_BOX_ID}", json={"new_tier": "starter"})
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_resize_box_not_found(client):
    resp = await client.post("/internal/resize/nonexistent", json={"new_tier": "pro"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_resize_box_invalid_tier(client, seed_box):
    resp = await client.post(f"/internal/resize/{TEST_BOX_ID}", json={"new_tier": "enterprise"})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_resize_box_wrong_status(client, seed_box, db):
    from openclaw_api.models import Box, BoxStatus
    from sqlalchemy import select

    result = await db.execute(select(Box).where(Box.id == TEST_BOX_ID))
    box = result.scalar_one()
    box.status = BoxStatus.suspended
    await db.commit()

    resp = await client.post(f"/internal/resize/{TEST_BOX_ID}", json={"new_tier": "pro"})
    assert resp.status_code == 409


# --- List boxes / customers ---


@pytest.mark.anyio
async def test_list_all_boxes(client, seed_box):
    resp = await client.get("/internal/boxes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["boxes"]) == 1
    assert data["boxes"][0]["id"] == TEST_BOX_ID


@pytest.mark.anyio
async def test_list_all_boxes_empty(client):
    resp = await client.get("/internal/boxes")
    assert resp.status_code == 200
    assert resp.json()["boxes"] == []


@pytest.mark.anyio
async def test_list_all_customers(client, seed_customer):
    resp = await client.get("/internal/customers")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["customers"]) == 1
    assert data["customers"][0]["id"] == TEST_CUSTOMER_ID


@pytest.mark.anyio
async def test_list_all_customers_empty(client):
    resp = await client.get("/internal/customers")
    assert resp.status_code == 200
    assert resp.json()["customers"] == []
