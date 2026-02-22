"""Tests for openclaw_operator.tiers."""

import pytest

from openclaw_operator.tiers import TIER_RESOURCES, TierResources, get_quota_hard


class TestTierResources:
    def test_starter_tier_values(self):
        r = TIER_RESOURCES["starter"]
        assert r.cpu_request == "250m"
        assert r.cpu_limit == "1000m"
        assert r.memory_request == "512Mi"
        assert r.memory_limit == "1Gi"

    def test_pro_tier_values(self):
        r = TIER_RESOURCES["pro"]
        assert r.cpu_request == "500m"
        assert r.cpu_limit == "2000m"
        assert r.memory_request == "512Mi"
        assert r.memory_limit == "1Gi"

    def test_team_tier_values(self):
        r = TIER_RESOURCES["team"]
        assert r.cpu_request == "1000m"
        assert r.cpu_limit == "4000m"
        assert r.memory_request == "1Gi"
        assert r.memory_limit == "2Gi"

    def test_all_tiers_present(self):
        assert set(TIER_RESOURCES.keys()) == {"starter", "pro", "team"}

    def test_tier_resources_are_frozen(self):
        r = TIER_RESOURCES["starter"]
        with pytest.raises(AttributeError):
            r.cpu_request = "999m"

    def test_tier_resources_is_dataclass(self):
        r = TierResources(
            cpu_request="1", cpu_limit="2", memory_request="3", memory_limit="4"
        )
        assert r.cpu_request == "1"


class TestGetQuotaHard:
    def test_starter_quota(self):
        q = get_quota_hard("starter")
        assert q == {
            "requests.cpu": "250m",
            "requests.memory": "512Mi",
            "limits.cpu": "1000m",
            "limits.memory": "1Gi",
        }

    def test_pro_quota(self):
        q = get_quota_hard("pro")
        assert q["requests.cpu"] == "500m"
        assert q["limits.cpu"] == "2000m"

    def test_team_quota(self):
        q = get_quota_hard("team")
        assert q["requests.cpu"] == "1000m"
        assert q["limits.memory"] == "2Gi"

    def test_unknown_tier_raises(self):
        with pytest.raises(KeyError):
            get_quota_hard("unknown")
