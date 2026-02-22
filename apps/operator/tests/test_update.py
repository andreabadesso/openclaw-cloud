"""Tests for openclaw_operator.jobs.update."""

from unittest.mock import patch

import pytest

from openclaw_operator.jobs.update import handle_update


@pytest.fixture
def _patch_k8s():
    with (
        patch("openclaw_operator.jobs.update.patch_config_secret") as pcs,
        patch("openclaw_operator.jobs.update.rollout_restart") as rr,
        patch("openclaw_operator.jobs.update.wait_for_rollout") as wfr,
    ):
        wfr.return_value = True
        yield {
            "patch_config_secret": pcs,
            "rollout_restart": rr,
            "wait_for_rollout": wfr,
        }


class TestHandleUpdate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_db, _patch_k8s):
        payload = {"box_id": "box-1", "secret_data": {"OPENCLAW_MODEL": "new-model"}}

        await handle_update(payload, "cust1", mock_db)

        _patch_k8s["patch_config_secret"].assert_called_once_with(
            "cust1", {"OPENCLAW_MODEL": "new-model"}
        )
        _patch_k8s["rollout_restart"].assert_called_once_with("cust1")
        _patch_k8s["wait_for_rollout"].assert_called_once_with("cust1", timeout=60)
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollout_timeout_raises(self, mock_db):
        payload = {"box_id": "box-1", "secret_data": {"FOO": "bar"}}

        with (
            patch("openclaw_operator.jobs.update.patch_config_secret"),
            patch("openclaw_operator.jobs.update.rollout_restart"),
            patch("openclaw_operator.jobs.update.wait_for_rollout", return_value=False),
        ):
            with pytest.raises(TimeoutError, match="Rollout not complete"):
                await handle_update(payload, "cust1", mock_db)

    @pytest.mark.asyncio
    async def test_patch_secret_failure_propagates(self, mock_db):
        payload = {"box_id": "box-1", "secret_data": {"FOO": "bar"}}

        with patch(
            "openclaw_operator.jobs.update.patch_config_secret",
            side_effect=Exception("patch fail"),
        ):
            with pytest.raises(Exception, match="patch fail"):
                await handle_update(payload, "cust1", mock_db)
