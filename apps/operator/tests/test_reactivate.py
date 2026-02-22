"""Tests for openclaw_operator.jobs.reactivate."""

from unittest.mock import patch

import pytest

from openclaw_operator.jobs.reactivate import handle_reactivate


@pytest.fixture
def _patch_k8s():
    with patch("openclaw_operator.jobs.reactivate.scale_deployment") as sd:
        yield {"scale_deployment": sd}


class TestHandleReactivate:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_db, _patch_k8s):
        payload = {"box_id": "box-1"}

        await handle_reactivate(payload, "cust1", mock_db)

        _patch_k8s["scale_deployment"].assert_called_once_with("cust1", replicas=1)
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_scale_failure_propagates(self, mock_db):
        payload = {"box_id": "box-1"}

        with patch(
            "openclaw_operator.jobs.reactivate.scale_deployment",
            side_effect=Exception("scale fail"),
        ):
            with pytest.raises(Exception, match="scale fail"):
                await handle_reactivate(payload, "cust1", mock_db)
