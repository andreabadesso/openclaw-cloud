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
        rows = [_make_row("github", "gh-conn-1"), _make_row("linear", "linear-conn-1")]
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
        assert "nango_proxy_url" in config
        assert "nango_secret_key" in config
        assert "api_url" in config
        assert "api_secret" in config
        assert config["customer_id"] == "cust1"
        assert "web_url" in config
        assert len(config["connections"]) == 2

        # GitHub is a native provider — gets native_env, no mcp
        gh_conn = config["connections"][0]
        assert gh_conn["provider"] == "github"
        assert gh_conn["connection_id"] == "gh-conn-1"
        assert gh_conn["native_env"] == "GH_TOKEN"
        assert "mcp" not in gh_conn

        # Linear is an MCP provider — gets mcp config, no native_env
        linear_conn = config["connections"][1]
        assert linear_conn["provider"] == "linear"
        assert linear_conn["connection_id"] == "linear-conn-1"
        assert linear_conn["mcp"]["type"] == "http"
        assert "native_env" not in linear_conn

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
    async def test_unknown_provider_has_no_mcp_or_native(self, mock_db, _patch_k8s, _patch_settings):
        rows = [_make_row("unknown-provider", "conn-1")]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])
        conn = config["connections"][0]
        assert "mcp" not in conn
        assert "native_env" not in conn

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
    async def test_native_providers_get_native_env(self, mock_db, _patch_k8s, _patch_settings):
        """GitHub, Notion, Slack are native — they get native_env, not mcp."""
        rows = [
            _make_row("github", "c1"),
            _make_row("notion", "c2"),
            _make_row("slack", "c3"),
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])

        expected = {"github": "GH_TOKEN", "notion": "NOTION_API_KEY", "slack": "SLACK_BOT_TOKEN"}
        for conn in config["connections"]:
            assert conn["native_env"] == expected[conn["provider"]]
            assert "mcp" not in conn

    @pytest.mark.asyncio
    async def test_mcp_providers_get_mcp_config(self, mock_db, _patch_k8s, _patch_settings):
        """Linear, Jira, Google are MCP — they get mcp config, not native_env."""
        rows = [
            _make_row("linear", "c1"),
            _make_row("jira", "c2"),
            _make_row("google", "c3"),
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])

        for conn in config["connections"]:
            assert "mcp" in conn
            assert conn["mcp"] is not None
            assert "native_env" not in conn

    @pytest.mark.asyncio
    async def test_all_six_providers(self, mock_db, _patch_k8s, _patch_settings):
        """All 6 supported providers are categorized correctly."""
        rows = [
            _make_row("github", "c1"),
            _make_row("notion", "c2"),
            _make_row("slack", "c3"),
            _make_row("linear", "c4"),
            _make_row("jira", "c5"),
            _make_row("google", "c6"),
        ]
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_db.execute.return_value = result

        await handle_update_connections({}, "cust1", mock_db)

        call_args = _patch_k8s["patch_config_secret"].call_args
        config = json.loads(call_args[0][1]["OPENCLAW_CONNECTIONS"])
        assert len(config["connections"]) == 6

        native_conns = [c for c in config["connections"] if "native_env" in c]
        mcp_conns = [c for c in config["connections"] if "mcp" in c]
        assert len(native_conns) == 3  # github, notion, slack
        assert len(mcp_conns) == 3  # linear, jira, google
