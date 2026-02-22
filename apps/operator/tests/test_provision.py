"""Tests for openclaw_operator.jobs.provision."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openclaw_operator.jobs.provision import handle_provision


@pytest.fixture
def provision_payload():
    return {
        "box_id": "box-1",
        "tier": "starter",
        "telegram_bot_token": "bot-tok",
        "telegram_allow_from": "user1",
        "model": "kimi-coding/k2p5",
        "thinking": "medium",
    }


@pytest.fixture
def _patch_k8s():
    with (
        patch("openclaw_operator.jobs.provision.create_namespace") as ns,
        patch("openclaw_operator.jobs.provision.create_config_secret") as sec,
        patch("openclaw_operator.jobs.provision.create_resource_quota") as rq,
        patch("openclaw_operator.jobs.provision.create_network_policy") as np,
        patch("openclaw_operator.jobs.provision.create_deployment") as dep,
        patch("openclaw_operator.jobs.provision.wait_for_pod_ready") as wait,
    ):
        wait.return_value = True
        yield {
            "create_namespace": ns,
            "create_config_secret": sec,
            "create_resource_quota": rq,
            "create_network_policy": np,
            "create_deployment": dep,
            "wait_for_pod_ready": wait,
        }


class TestHandleProvision:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_db, provision_payload, _patch_k8s, _patch_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "proxy-tok-123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.provision.httpx.AsyncClient", return_value=mock_client):
            await handle_provision(provision_payload, "cust1", mock_db)

        # Verify token-proxy was called
        mock_client.post.assert_called_once()
        post_kwargs = mock_client.post.call_args
        assert "internal/tokens" in post_kwargs[0][0]

        # Verify K8s calls
        _patch_k8s["create_namespace"].assert_called_once_with("cust1", "starter")
        _patch_k8s["create_config_secret"].assert_called_once()
        _patch_k8s["create_resource_quota"].assert_called_once_with("cust1", "starter")
        _patch_k8s["create_network_policy"].assert_called_once_with("cust1")
        _patch_k8s["create_deployment"].assert_called_once()
        _patch_k8s["wait_for_pod_ready"].assert_called_once()

        # Verify DB update
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_pod_not_ready_raises_timeout(self, mock_db, provision_payload, _patch_settings):
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "proxy-tok-123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("openclaw_operator.jobs.provision.httpx.AsyncClient", return_value=mock_client),
            patch("openclaw_operator.jobs.provision.create_namespace"),
            patch("openclaw_operator.jobs.provision.create_config_secret"),
            patch("openclaw_operator.jobs.provision.create_resource_quota"),
            patch("openclaw_operator.jobs.provision.create_network_policy"),
            patch("openclaw_operator.jobs.provision.create_deployment"),
            patch("openclaw_operator.jobs.provision.wait_for_pod_ready", return_value=False),
        ):
            with pytest.raises(TimeoutError, match="Pod not ready"):
                await handle_provision(provision_payload, "cust1", mock_db)

    @pytest.mark.asyncio
    async def test_uses_telegram_user_id_fallback(self, mock_db, _patch_k8s, _patch_settings):
        payload = {
            "box_id": "box-1",
            "tier": "starter",
            "telegram_bot_token": "tok",
            "telegram_user_id": "fallback-user",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "tok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.provision.httpx.AsyncClient", return_value=mock_client):
            await handle_provision(payload, "cust1", mock_db)

        secret_call = _patch_k8s["create_config_secret"].call_args
        assert secret_call[1]["telegram_allow_from"] == "fallback-user"

    @pytest.mark.asyncio
    async def test_default_model_and_thinking(self, mock_db, _patch_k8s, _patch_settings):
        payload = {
            "box_id": "box-1",
            "tier": "starter",
            "telegram_bot_token": "tok",
            "telegram_allow_from": "user1",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "tok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.provision.httpx.AsyncClient", return_value=mock_client):
            await handle_provision(payload, "cust1", mock_db)

        secret_call = _patch_k8s["create_config_secret"].call_args
        assert secret_call[1]["model"] == "kimi-coding/k2p5"
        assert secret_call[1]["thinking"] == "medium"

    @pytest.mark.asyncio
    async def test_token_proxy_http_error_propagates(self, mock_db, provision_payload, _patch_settings):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.provision.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await handle_provision(provision_payload, "cust1", mock_db)
