"""Tests for openclaw_operator.jobs.resize."""

from unittest.mock import patch

import pytest

from openclaw_operator.jobs.resize import handle_resize


@pytest.fixture
def _patch_k8s():
    with (
        patch("openclaw_operator.jobs.resize.patch_resource_quota") as prq,
        patch("openclaw_operator.jobs.resize.patch_deployment_resources") as pdr,
        patch("openclaw_operator.jobs.resize.rollout_restart") as rr,
        patch("openclaw_operator.jobs.resize.wait_for_rollout") as wfr,
    ):
        wfr.return_value = True
        yield {
            "patch_resource_quota": prq,
            "patch_deployment_resources": pdr,
            "rollout_restart": rr,
            "wait_for_rollout": wfr,
        }


class TestHandleResize:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_db, _patch_k8s):
        payload = {"box_id": "box-1", "new_tier": "pro"}

        await handle_resize(payload, "cust1", mock_db)

        _patch_k8s["patch_resource_quota"].assert_called_once_with("cust1", "pro")
        _patch_k8s["patch_deployment_resources"].assert_called_once_with("cust1", "pro")
        _patch_k8s["rollout_restart"].assert_called_once_with("cust1")
        _patch_k8s["wait_for_rollout"].assert_called_once_with("cust1", timeout=60)
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollout_timeout_raises(self, mock_db):
        payload = {"box_id": "box-1", "new_tier": "team"}

        with (
            patch("openclaw_operator.jobs.resize.patch_resource_quota"),
            patch("openclaw_operator.jobs.resize.patch_deployment_resources"),
            patch("openclaw_operator.jobs.resize.rollout_restart"),
            patch("openclaw_operator.jobs.resize.wait_for_rollout", return_value=False),
        ):
            with pytest.raises(TimeoutError, match="Resize rollout not complete"):
                await handle_resize(payload, "cust1", mock_db)

    @pytest.mark.asyncio
    async def test_resize_to_team_tier(self, mock_db, _patch_k8s):
        payload = {"box_id": "box-1", "new_tier": "team"}

        await handle_resize(payload, "cust1", mock_db)

        _patch_k8s["patch_resource_quota"].assert_called_once_with("cust1", "team")
        _patch_k8s["patch_deployment_resources"].assert_called_once_with("cust1", "team")
