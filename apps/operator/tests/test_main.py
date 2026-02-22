"""Tests for openclaw_operator.main."""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis as redis_lib

from openclaw_operator.main import (
    JOB_HANDLERS,
    get_redis,
    get_session_factory,
    health,
    log_job,
    process_job,
)


class TestJobHandlers:
    def test_all_job_types_registered(self):
        expected = {
            "provision",
            "destroy",
            "suspend",
            "reactivate",
            "update",
            "resize",
            "update_connections",
        }
        assert set(JOB_HANDLERS.keys()) == expected


class TestLogJob:
    @pytest.mark.asyncio
    async def test_log_job_inserts_and_commits(self, mock_db):
        started = datetime.now(timezone.utc)
        await log_job(
            mock_db,
            customer_id="cust1",
            box_id="box-1",
            job_type="provision",
            status="running",
            payload={"tier": "starter"},
            started_at=started,
        )
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

        # Verify the payload was JSON-serialized
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        assert params["customer_id"] == "cust1"
        assert params["box_id"] == "box-1"
        assert params["job_type"] == "provision"
        assert params["status"] == "running"
        assert json.loads(params["payload"]) == {"tier": "starter"}

    @pytest.mark.asyncio
    async def test_log_job_with_error_log(self, mock_db):
        started = datetime.now(timezone.utc)
        await log_job(
            mock_db,
            customer_id="cust1",
            box_id="box-1",
            job_type="provision",
            status="failed",
            payload={},
            error_log="Traceback ...",
            started_at=started,
        )
        params = mock_db.execute.call_args[0][1]
        assert params["error_log"] == "Traceback ..."

    @pytest.mark.asyncio
    async def test_log_job_without_box_id(self, mock_db):
        started = datetime.now(timezone.utc)
        await log_job(
            mock_db,
            customer_id="cust1",
            box_id=None,
            job_type="update_connections",
            status="complete",
            payload={},
            started_at=started,
        )
        params = mock_db.execute.call_args[0][1]
        assert params["box_id"] is None


class TestProcessJob:
    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1", "tier": "starter"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[1] == "cust1"  # customer_id

    @pytest.mark.asyncio
    async def test_unknown_job_type_returns_early(self, mock_redis):
        job = json.dumps({
            "job_type": "nonexistent",
            "customer_id": "cust1",
        })

        with patch("openclaw_operator.main.get_redis", return_value=mock_redis):
            await process_job(job)
        # Should not raise, just log and return

    @pytest.mark.asyncio
    async def test_uses_type_field_as_fallback(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "type": "destroy",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"destroy": mock_handler}),
        ):
            await process_job(job)

        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_returns_early(self, mock_redis):
        mock_handler = AsyncMock()
        lock = mock_redis.lock.return_value
        lock.acquire.return_value = False

        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_failure_logs_error(self, mock_redis):
        mock_handler = AsyncMock(side_effect=Exception("handler boom"))
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            # Should not raise — errors are caught and logged
            await process_job(job)

    @pytest.mark.asyncio
    async def test_lock_released_after_success(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        mock_redis.lock.return_value.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_released_after_failure(self, mock_redis):
        mock_handler = AsyncMock(side_effect=Exception("fail"))
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        mock_redis.lock.return_value.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_not_owned_error_suppressed(self, mock_redis):
        mock_handler = AsyncMock()
        lock = mock_redis.lock.return_value
        lock.release.side_effect = redis_lib.exceptions.LockNotOwnedError("not owned")

        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": {"box_id": "box-1"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            # Should not raise
            await process_job(job)

    @pytest.mark.asyncio
    async def test_payload_string_is_json_parsed(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "payload": '{"box_id": "box-1", "tier": "starter"}',
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        call_args = mock_handler.call_args[0]
        assert call_args[0] == {"box_id": "box-1", "tier": "starter"}

    @pytest.mark.asyncio
    async def test_box_id_from_top_level(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "job_type": "provision",
            "customer_id": "cust1",
            "box_id": "box-top",
            "payload": {"tier": "starter"},
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"provision": mock_handler}),
        ):
            await process_job(job)

        call_args = mock_handler.call_args[0]
        # box_id should be injected into payload
        assert call_args[0]["box_id"] == "box-top"

    @pytest.mark.asyncio
    async def test_empty_payload_string(self, mock_redis):
        mock_handler = AsyncMock()
        job = json.dumps({
            "job_type": "update_connections",
            "customer_id": "cust1",
            "payload": "",
        })

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        with (
            patch("openclaw_operator.main.get_redis", return_value=mock_redis),
            patch("openclaw_operator.main.get_session_factory", return_value=mock_session_factory),
            patch.dict("openclaw_operator.main.JOB_HANDLERS", {"update_connections": mock_handler}),
        ):
            await process_job(job)

        call_args = mock_handler.call_args[0]
        assert call_args[0] == {}


class TestHealth:
    @pytest.mark.asyncio
    async def test_healthy(self):
        import openclaw_operator.main as m

        original = m._healthy
        m._healthy = True
        try:
            request = MagicMock()
            resp = await health(request)
            assert resp.status_code == 200
        finally:
            m._healthy = original

    @pytest.mark.asyncio
    async def test_not_healthy(self):
        import openclaw_operator.main as m

        original = m._healthy
        m._healthy = False
        try:
            request = MagicMock()
            resp = await health(request)
            assert resp.status_code == 503
        finally:
            m._healthy = original


class TestGetRedis:
    def test_creates_redis_client(self):
        import openclaw_operator.main as m

        original = m._redis
        m._redis = None
        try:
            with patch("openclaw_operator.main.redis.from_url") as mock_from_url:
                mock_from_url.return_value = MagicMock()
                r = get_redis()
                mock_from_url.assert_called_once()
                assert r is not None
        finally:
            m._redis = original

    def test_returns_cached_client(self):
        import openclaw_operator.main as m

        cached = MagicMock()
        original = m._redis
        m._redis = cached
        try:
            assert get_redis() is cached
        finally:
            m._redis = original


class TestGetSessionFactory:
    def test_creates_session_factory(self):
        import openclaw_operator.main as m

        original = m._session_factory
        m._session_factory = None
        try:
            with (
                patch("openclaw_operator.main.create_async_engine") as mock_engine,
                patch("openclaw_operator.main.async_sessionmaker") as mock_sm,
            ):
                result = get_session_factory()
                mock_engine.assert_called_once()
                mock_sm.assert_called_once()
                assert result is not None
        finally:
            m._session_factory = original

    def test_returns_cached_factory(self):
        import openclaw_operator.main as m

        cached = MagicMock()
        original = m._session_factory
        m._session_factory = cached
        try:
            assert get_session_factory() is cached
        finally:
            m._session_factory = original
