import pytest

from tests.conftest import TEST_BUNDLE_ID


# --- GET /bundles (public) ---


@pytest.mark.anyio
async def test_list_bundles_empty(client):
    resp = await client.get("/bundles")
    assert resp.status_code == 200
    assert resp.json()["bundles"] == []


@pytest.mark.anyio
async def test_list_bundles_published_only(client, seed_bundle, db):
    """Only published bundles appear in the public listing."""
    from openclaw_api.models import Bundle

    draft_bundle = Bundle(
        slug="draft-bundle",
        name="Draft Bundle",
        status="draft",
        prompts={},
        providers=[],
        mcp_servers={},
        skills=[],
    )
    db.add(draft_bundle)
    await db.commit()

    resp = await client.get("/bundles")
    assert resp.status_code == 200
    bundles = resp.json()["bundles"]
    assert len(bundles) == 1
    assert bundles[0]["slug"] == "general-assistant"


@pytest.mark.anyio
async def test_list_bundles_fields(client, seed_bundle):
    resp = await client.get("/bundles")
    bundle = resp.json()["bundles"][0]
    assert bundle["id"] == TEST_BUNDLE_ID
    assert bundle["name"] == "General Assistant"
    assert bundle["icon"] == "🤖"
    assert bundle["color"] == "#10B981"
    assert isinstance(bundle["providers"], list)
    assert isinstance(bundle["skills"], list)


# --- GET /bundles/{slug} ---


@pytest.mark.anyio
async def test_get_bundle_by_slug(client, seed_bundle):
    resp = await client.get("/bundles/general-assistant")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "general-assistant"
    assert data["default_model"] == "kimi-coding/k2p5"
    assert "prompts" in data


@pytest.mark.anyio
async def test_get_bundle_not_found(client):
    resp = await client.get("/bundles/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_draft_bundle_returns_404(client, db):
    from openclaw_api.models import Bundle

    draft = Bundle(
        slug="secret-draft",
        name="Secret",
        status="draft",
        prompts={},
        providers=[],
        mcp_servers={},
        skills=[],
    )
    db.add(draft)
    await db.commit()

    resp = await client.get("/bundles/secret-draft")
    assert resp.status_code == 404


# --- POST /internal/bundles (admin) ---


@pytest.mark.anyio
async def test_create_bundle(client):
    resp = await client.post(
        "/internal/bundles",
        json={
            "slug": "pharmacy",
            "name": "Pharmacy Assistant",
            "description": "Helps with pharmacy tasks",
            "status": "published",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "pharmacy"
    assert data["name"] == "Pharmacy Assistant"
    assert "id" in data


@pytest.mark.anyio
async def test_create_bundle_duplicate_slug(client, seed_bundle):
    resp = await client.post(
        "/internal/bundles",
        json={
            "slug": "general-assistant",
            "name": "Duplicate",
        },
    )
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_create_bundle_with_providers(client):
    resp = await client.post(
        "/internal/bundles",
        json={
            "slug": "dev-tools",
            "name": "Developer Tools",
            "providers": [
                {"provider": "github", "required": True},
                {"provider": "slack", "required": False},
            ],
            "skills": ["code-review", "deploy"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["providers"]) == 2
    assert data["providers"][0]["provider"] == "github"
    assert data["providers"][0]["required"] is True
    assert data["skills"] == ["code-review", "deploy"]


# --- GET /internal/bundles (admin list all) ---


@pytest.mark.anyio
async def test_list_all_bundles_admin(client, seed_bundle, db):
    """Admin endpoint includes draft and archived bundles."""
    from openclaw_api.models import Bundle

    draft = Bundle(
        slug="draft-one",
        name="Draft One",
        status="draft",
        prompts={},
        providers=[],
        mcp_servers={},
        skills=[],
    )
    db.add(draft)
    await db.commit()

    resp = await client.get("/internal/bundles")
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # published + draft


# --- PATCH /internal/bundles/{id} ---


@pytest.mark.anyio
async def test_update_bundle(client, seed_bundle):
    resp = await client.patch(
        f"/internal/bundles/{TEST_BUNDLE_ID}",
        json={"name": "Updated Name", "status": "draft"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert resp.json()["status"] == "draft"


@pytest.mark.anyio
async def test_update_bundle_not_found(client):
    resp = await client.patch(
        "/internal/bundles/00000000-0000-0000-0000-nonexistent00",
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


# --- DELETE /internal/bundles/{id} (archive) ---


@pytest.mark.anyio
async def test_archive_bundle(client, seed_bundle):
    resp = await client.delete(f"/internal/bundles/{TEST_BUNDLE_ID}")
    assert resp.status_code == 204

    # Should no longer appear in public listing
    list_resp = await client.get("/bundles")
    assert list_resp.json()["bundles"] == []

    # But still in admin listing (as archived)
    admin_resp = await client.get("/internal/bundles")
    bundles = admin_resp.json()
    assert len(bundles) == 1
    assert bundles[0]["status"] == "archived"


@pytest.mark.anyio
async def test_archive_bundle_not_found(client):
    resp = await client.delete("/internal/bundles/00000000-0000-0000-0000-nonexistent00")
    assert resp.status_code == 404
