"""Tests for openclaw_operator.jobs.update_connections."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openclaw_operator.jobs.update_connections import handle_update_connections


@pytest.fixture
def _patch_k8s():
    with (
        patch("openclaw_operator.jobs.update_connections.patch_config_secret") as pcs,
        patch("openclaw_operator.jobs.update_connections.rollout_restart") as rr,
        patch("openclaw_operator.jobs.update_connections.wait_for_rollout") as wfr,
    ):
        wfr.return_value = True
        yield {
            "patch_config_secret": pcs,
            "rollout_restart": rr,
            "wait_for_rollout": wfr,
        }


def _make_row(provider: str, connection_id: str):
    row = MagicMock()
    row.provider = provider
    row.nango_connection_id = connection_id
    return row


class TestHandleUpdateConnections:
    @pytest.mark.asyncio
    async def test_happy_path_with_connections(self, mock_db, _patch_k8s, _patch_settings):
        rows = [_make_row("github", "gh-conn-1"), _make_row("slack", "slack-conn-1")]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        # Verify patch_config_secret was called with OPENCLAW_CONNECTIONS
        _patch_k8s["patch_config_secret"].assert_called_once()
        call_args = _patch_k8s["patch_config_secret"].call_args
        assert call_args[0][0] == "cust1"
        secret_data = call_args[0][1]
        assert "OPENCLAW_CONNECTIONS" in secret_data

        config = json.loads(secret_data["OPENCLAW_CONNECTIONS"])
        assert config["nango_proxy_url"] == "http://nango-server:8080"
        assert config["nango_secret_key"] == "test-nango-secret"
        assert config["api_url"] == "http://api:8000"
        assert config["api_secret"] == "test-agent-secret"
        assert config["customer_id"] == "cust1"
        assert config["web_url"] == "http://localhost:3000"
        assert len(config["connections"]) == 2
        assert config["connections"][0]["provider"] == "github"
        assert config["connections"][0]["connection_id"] == "gh-conn-1"
        assert config["connections"][0]["mcp"] is not None  # github has MCP_SERVERS entry
        assert config["connections"][1]["provider"] == "slack"

        _patch_k8s["rollout_restart"].assert_called_once_with("cust1")
        _patch_k8s["wait_for_rollout"].assert_called_once()

    @pytest.mark.asyncio
    async def test_no_connections(self, mock_db, _patch_k8s, _patch_settings):
        result = MagicMock()
        result.fetchall.return_value = []
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])
        assert config["connections"] == []

    @pytest.mark.asyncio
    async def test_provider_without_mcp_server(self, mock_db, _patch_k8s, _patch_settings):
        rows = [_make_row("unknown-provider", "conn-1")]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])
        assert config["connections"][0]["mcp"] is None

    @pytest.mark.asyncio
    async def test_rollout_timeout_raises(self, mock_db, _patch_settings):
        result = MagicMock()
        result.fetchall.return_value = []
        mock_db.execute.return_value = result

        with (
            patch("openclaw_operator.jobs.update_connections.patch_config_secret"),
            patch("openclaw_operator.jobs.update_connections.rollout_restart"),
            patch("openclaw_operator.jobs.update_connections.wait_for_rollout", return_value=False),
        ):
            with pytest.raises(TimeoutError, match="Rollout not complete"):
                await handle_update_connections({}, "cust1", mock_db)

    @pytest.mark.asyncio
    async def test_mcp_config_for_known_providers(self, mock_db, _patch_k8s, _patch_settings):
        """Verify MCP server configs are included for all known providers."""
        rows = [
            _make_row("github", "c1"),
            _make_row("linear", "c2"),
            _make_row("notion", "c3"),
            _make_row("slack", "c4"),
            _make_row("jira", "c5"),
            _make_row("google", "c6"),
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])
        for conn in config["connections"]:
            assert conn["mcp"] is not None, f"Expected MCP config for {conn['provider']}"
