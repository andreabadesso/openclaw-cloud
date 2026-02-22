from unittest.mock import AsyncMock, patch

import pytest

from openclaw_api.main import app
from openclaw_api.nango_client import get_nango_client
from tests.conftest import TEST_BOX_ID, TEST_CUSTOMER_ID, mock_redis


# --- helpers ---

def _override_nango(mock_nango):
    """Register a nango client dependency override; returns a cleanup callable."""
    app.dependency_overrides[get_nango_client] = lambda: mock_nango


def _clear_nango():
    app.dependency_overrides.pop(get_nango_client, None)


# --- Customer connection routes ---


async def test_list_connections(client, seed_connection):
    resp = await client.get("/me/connections")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["connections"]) == 1
    assert data["connections"][0]["provider"] == "github"


async def test_list_connections_empty(client, seed_customer):
    resp = await client.get("/me/connections")
    assert resp.status_code == 200
    assert resp.json()["connections"] == []


async def test_authorize_connection(client, seed_customer):
    mock_nango = AsyncMock()
    mock_nango.create_connect_session.return_value = {
        "data": {"token": "nango_tok_123"}
    }
    _override_nango(mock_nango)
    try:
        resp = await client.post("/me/connections/github/authorize")
    finally:
        _clear_nango()

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_token"] == "nango_tok_123"
    assert "connect_url" in data


async def test_authorize_connection_nango_error(client, seed_customer):
    mock_nango = AsyncMock()
    mock_nango.create_connect_session.side_effect = Exception("Nango down")
    _override_nango(mock_nango)
    try:
        resp = await client.post("/me/connections/github/authorize")
    finally:
        _clear_nango()

    assert resp.status_code == 502


async def test_confirm_connection(client, seed_box):
    mock_nango = AsyncMock()
    mock_nango.list_connections.return_value = [
        {
            "provider_config_key": "github",
            "connection_id": f"{TEST_CUSTOMER_ID}_github",
            "end_user": {"id": TEST_CUSTOMER_ID},
        }
    ]
    _override_nango(mock_nango)
    try:
        resp = await client.post("/me/connections/github/confirm")
    finally:
        _clear_nango()

    assert resp.status_code == 200
    assert resp.json()["provider"] == "github"


async def test_confirm_connection_not_in_nango(client, seed_box):
    mock_nango = AsyncMock()
    mock_nango.list_connections.return_value = []
    _override_nango(mock_nango)
    try:
        resp = await client.post("/me/connections/github/confirm")
    finally:
        _clear_nango()

    assert resp.status_code == 404


async def test_delete_connection(client, seed_box, seed_connection):
    mock_nango = AsyncMock()
    conn_id = f"{TEST_CUSTOMER_ID}_github"
    _override_nango(mock_nango)
    try:
        resp = await client.delete(f"/me/connections/{conn_id}")
    finally:
        _clear_nango()

    assert resp.status_code == 204


async def test_delete_connection_nango_error(client, seed_box, seed_connection):
    mock_nango = AsyncMock()
    mock_nango.delete_connection.side_effect = Exception("Nango down")
    conn_id = f"{TEST_CUSTOMER_ID}_github"
    _override_nango(mock_nango)
    try:
        resp = await client.delete(f"/me/connections/{conn_id}")
    finally:
        _clear_nango()

    assert resp.status_code == 502


async def test_reconnect_connection(client, seed_connection):
    mock_nango = AsyncMock()
    mock_nango.create_connect_session.return_value = {
        "data": {"token": "new_tok_456"}
    }
    conn_id = f"{TEST_CUSTOMER_ID}_github"
    _override_nango(mock_nango)
    try:
        resp = await client.post(f"/me/connections/{conn_id}/reconnect")
    finally:
        _clear_nango()

    assert resp.status_code == 200
    assert resp.json()["session_token"] == "new_tok_456"


async def test_reconnect_connection_not_found(client, seed_customer):
    mock_nango = AsyncMock()
    _override_nango(mock_nango)
    try:
        resp = await client.post("/me/connections/nonexistent/reconnect")
    finally:
        _clear_nango()

    assert resp.status_code == 404


# --- Agent connection routes ---


async def test_agent_get_connections(client, seed_connection):
    with patch("openclaw_api.routes.connections.agent.settings") as mock_settings:
        mock_settings.agent_api_secret = "test-secret"
        mock_settings.nango_server_url = "http://nango:8080"
        mock_settings.nango_secret_key = "nango-key"
        resp = await client.get(
            "/internal/agent/connections",
            headers={
                "Authorization": "Bearer test-secret",
                "X-Customer-Id": TEST_CUSTOMER_ID,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "connections" in data
    assert "available_providers" in data


async def test_agent_get_connections_no_auth(client, seed_connection):
    with patch("openclaw_api.routes.connections.agent.settings") as mock_settings:
        mock_settings.agent_api_secret = "test-secret"
        resp = await client.get(
            "/internal/agent/connections",
            headers={
                "Authorization": "Bearer wrong-secret",
                "X-Customer-Id": TEST_CUSTOMER_ID,
            },
        )

    assert resp.status_code == 401


async def test_agent_create_connect_link(client):
    mock_redis.set = AsyncMock()
    with patch("openclaw_api.routes.connections.agent.settings") as mock_settings:
        mock_settings.agent_api_secret = "test-secret"
        mock_settings.cors_origins = "http://localhost:3000"
        resp = await client.post(
            "/internal/agent/connect-link",
            json={"customer_id": TEST_CUSTOMER_ID, "provider": "github"},
            headers={"Authorization": "Bearer test-secret"},
        )

    assert resp.status_code == 200
    assert "/connect/github?token=" in resp.json()["url"]


async def test_validate_connect_token(client):
    mock_redis.get = AsyncMock(return_value=TEST_CUSTOMER_ID)
    resp = await client.get("/connect/github/validate?token=tok123")
    assert resp.status_code == 200
    assert resp.json()["customer_id"] == TEST_CUSTOMER_ID


async def test_validate_connect_token_expired(client):
    mock_redis.get = AsyncMock(return_value=None)
    resp = await client.get("/connect/github/validate?token=expired")
    assert resp.status_code == 401


async def test_create_connect_link_customer(client, seed_customer):
    mock_redis.set = AsyncMock()
    with patch("openclaw_api.routes.connections.customer.settings") as mock_settings:
        mock_settings.cors_origins = "http://localhost:3000"
        resp = await client.post("/internal/connect-link", json={"provider": "slack"})
    assert resp.status_code == 200
    assert "/connect/slack?token=" in resp.json()["url"]
