import pytest

from tests.conftest import TEST_BOX_ID, TEST_BUNDLE_ID, TEST_CUSTOMER_ID, mock_redis


# --- GET /me/box ---


@pytest.mark.anyio
async def test_get_my_box(client, seed_box):
    resp = await client.get("/me/box", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == TEST_BOX_ID
    assert data["status"] == "active"
    assert data["model"] == "kimi-coding/k2p5"


@pytest.mark.anyio
async def test_get_my_box_by_id(client, seed_box):
    resp = await client.get(
        f"/me/box?box_id={TEST_BOX_ID}",
        headers={"X-Customer-Id": TEST_CUSTOMER_ID},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == TEST_BOX_ID


@pytest.mark.anyio
async def test_get_my_box_not_found(client, seed_customer):
    resp = await client.get("/me/box", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 404


# --- GET /me/boxes ---


@pytest.mark.anyio
async def test_get_my_boxes_empty(client, seed_customer):
    resp = await client.get("/me/boxes", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 200
    assert resp.json()["boxes"] == []


@pytest.mark.anyio
async def test_get_my_boxes(client, seed_box):
    resp = await client.get("/me/boxes", headers={"X-Customer-Id": TEST_CUSTOMER_ID})
    assert resp.status_code == 200
    boxes = resp.json()["boxes"]
    assert len(boxes) == 1
    assert boxes[0]["id"] == TEST_BOX_ID


# --- POST /me/box/update (legacy) ---


@pytest.mark.anyio
async def test_update_my_box_legacy(client, seed_box):
    resp = await client.post("/me/box/update", json={"model": "gpt-4o"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data


@pytest.mark.anyio
async def test_update_my_box_legacy_no_fields(client, seed_box):
    resp = await client.post("/me/box/update", json={})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_update_my_box_legacy_no_box(client, seed_customer):
    resp = await client.post("/me/box/update", json={"model": "gpt-4o"})
    assert resp.status_code == 404


# --- POST /me/box/{box_id}/update ---


@pytest.mark.anyio
async def test_update_box_by_id(client, seed_box):
    resp = await client.post(f"/me/box/{TEST_BOX_ID}/update", json={"model": "gpt-4o"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["box_id"] == TEST_BOX_ID
    assert "job_id" in data
    mock_redis.rpush.assert_called_once()


@pytest.mark.anyio
async def test_update_box_by_id_not_found(client, seed_customer):
    resp = await client.post(f"/me/box/{TEST_BOX_ID}/update", json={"model": "gpt-4o"})
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_update_box_by_id_no_fields(client, seed_box):
    resp = await client.post(f"/me/box/{TEST_BOX_ID}/update", json={})
    assert resp.status_code == 400


# --- POST /me/setup ---


@pytest.mark.anyio
async def test_setup_first_box(client, seed_customer, seed_bundle):
    resp = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "starter",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer_id"] == TEST_CUSTOMER_ID
    assert "box_id" in data
    assert "job_id" in data
    mock_redis.rpush.assert_called_once()


@pytest.mark.anyio
async def test_setup_applies_bundle_defaults(client, db, seed_customer, seed_bundle):
    resp = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "starter",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    assert resp.status_code == 200
    box_id = resp.json()["box_id"]

    box_resp = await client.get(f"/me/box?box_id={box_id}")
    assert box_resp.status_code == 200
    box = box_resp.json()
    assert box["model"] == "kimi-coding/k2p5"
    assert box["bundle_id"] == TEST_BUNDLE_ID


@pytest.mark.anyio
async def test_setup_overrides_bundle_defaults(client, seed_customer, seed_bundle):
    resp = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "pro",
            "bundle_id": TEST_BUNDLE_ID,
            "model": "gpt-4o",
            "thinking_level": "high",
            "language": "pt",
        },
    )
    assert resp.status_code == 200
    box_id = resp.json()["box_id"]

    box_resp = await client.get(f"/me/box?box_id={box_id}")
    box = box_resp.json()
    assert box["model"] == "gpt-4o"


@pytest.mark.anyio
async def test_setup_multiple_agents(client, seed_customer, seed_bundle):
    """Users can create multiple agents — no 409 restriction."""
    resp1 = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "starter",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    assert resp1.status_code == 200
    box1_id = resp1.json()["box_id"]

    resp2 = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "456:DEF",
            "telegram_user_id": 88888,
            "tier": "pro",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    assert resp2.status_code == 200
    box2_id = resp2.json()["box_id"]
    assert box1_id != box2_id

    # Both should appear in the list
    boxes_resp = await client.get("/me/boxes")
    assert boxes_resp.status_code == 200
    boxes = boxes_resp.json()["boxes"]
    assert len(boxes) == 2


@pytest.mark.anyio
async def test_setup_unique_namespaces(client, db, seed_customer, seed_bundle):
    """Each box gets a unique k8s namespace."""
    resp1 = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "starter",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    box1 = await client.get(f"/me/box?box_id={resp1.json()['box_id']}")
    ns1 = box1.json()["k8s_namespace"]

    resp2 = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "456:DEF",
            "telegram_user_id": 88888,
            "tier": "starter",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    box2 = await client.get(f"/me/box?box_id={resp2.json()['box_id']}")
    ns2 = box2.json()["k8s_namespace"]

    assert ns1 != ns2
    assert ns1 == f"customer-{TEST_CUSTOMER_ID}"
    assert ns2 == f"customer-{TEST_CUSTOMER_ID}-2"


@pytest.mark.anyio
async def test_setup_invalid_bundle(client, seed_customer):
    resp = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "starter",
            "bundle_id": "00000000-0000-0000-0000-nonexistent00",
        },
    )
    assert resp.status_code == 400
    assert "bundle" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_setup_invalid_tier(client, seed_customer, seed_bundle):
    resp = await client.post(
        "/me/setup",
        json={
            "telegram_bot_token": "123:ABC",
            "telegram_user_id": 99999,
            "tier": "enterprise",
            "bundle_id": TEST_BUNDLE_ID,
        },
    )
    assert resp.status_code == 422  # Pydantic validation
