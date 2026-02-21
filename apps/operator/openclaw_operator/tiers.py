from dataclasses import dataclass


@dataclass(frozen=True)
class TierResources:
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str


TIER_RESOURCES: dict[str, TierResources] = {
    "starter": TierResources(
        cpu_request="250m",
        cpu_limit="500m",
        memory_request="128Mi",
        memory_limit="256Mi",
    ),
    "pro": TierResources(
        cpu_request="500m",
        cpu_limit="1000m",
        memory_request="256Mi",
        memory_limit="512Mi",
    ),
    "team": TierResources(
        cpu_request="1000m",
        cpu_limit="2000m",
        memory_request="512Mi",
        memory_limit="1Gi",
    ),
}


def get_quota_hard(tier: str) -> dict[str, str]:
    """Return the hard resource quota dict for a K8s ResourceQuota."""
    res = TIER_RESOURCES[tier]
    return {
        "requests.cpu": res.cpu_request,
        "requests.memory": res.memory_request,
        "limits.cpu": res.cpu_limit,
        "limits.memory": res.memory_limit,
    }
