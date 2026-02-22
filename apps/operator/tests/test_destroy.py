"""Tests for openclaw_operator.jobs.destroy."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openclaw_operator.jobs.destroy import handle_destroy


@pytest.fixture
def _patch_k8s():
    with patch("openclaw_operator.jobs.destroy.delete_namespace") as dns:
        yield {"delete_namespace": dns}


class TestHandleDestroy:
    @pytest.mark.asyncio
    async def test_happy_path_with_proxy_token(self, mock_db, _patch_k8s, _patch_settings):
        payload = {"box_id": "box-1", "proxy_token_id": "ptok-1"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.destroy.httpx.AsyncClient", return_value=mock_client):
            await handle_destroy(payload, "cust1", mock_db)

        _patch_k8s["delete_namespace"].assert_called_once_with("cust1")
        mock_client.delete.assert_called_once()
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_proxy_token(self, mock_db, _patch_k8s, _patch_settings):
        payload = {"box_id": "box-1"}

        await handle_destroy(payload, "cust1", mock_db)

        _patch_k8s["delete_namespace"].assert_called_once_with("cust1")
        # No httpx call should have been made
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_proxy_token_none_skips_revoke(self, mock_db, _patch_k8s, _patch_settings):
        payload = {"box_id": "box-1", "proxy_token_id": None}

        await handle_destroy(payload, "cust1", mock_db)

        _patch_k8s["delete_namespace"].assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_k8s_delete_failure_propagates(self, mock_db, _patch_settings):
        payload = {"box_id": "box-1"}

        with patch("openclaw_operator.jobs.destroy.delete_namespace", side_effect=Exception("k8s fail")):
            with pytest.raises(Exception, match="k8s fail"):
                await handle_destroy(payload, "cust1", mock_db)

    @pytest.mark.asyncio
    async def test_proxy_revoke_failure_propagates(self, mock_db, _patch_k8s, _patch_settings):
        payload = {"box_id": "box-1", "proxy_token_id": "ptok-1"}

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("openclaw_operator.jobs.destroy.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await handle_destroy(payload, "cust1", mock_db)
