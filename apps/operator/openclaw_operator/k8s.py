import json
import logging

from kubernetes import client, config
from kubernetes.client import (
    AppsV1Api,
    CoreV1Api,
    NetworkingV1Api,
    V1Container,
    V1Deployment,
    V1DeploymentSpec,
    V1EnvFromSource,
    V1LabelSelector,
    V1Namespace,
    V1NetworkPolicy,
    V1NetworkPolicyEgressRule,
    V1NetworkPolicyPeer,
    V1NetworkPolicyPort,
    V1NetworkPolicySpec,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
    V1ResourceQuota,
    V1ResourceQuotaSpec,
    V1ResourceRequirements,
    V1Secret,
    V1SecretEnvSource,
)

from .config import settings
from .tiers import TIER_RESOURCES, get_quota_hard

logger = logging.getLogger(__name__)

_core_v1: CoreV1Api | None = None
_apps_v1: AppsV1Api | None = None
_networking_v1: NetworkingV1Api | None = None


def init_k8s() -> None:
    """Load kubeconfig — in-cluster first, then local fallback."""
    global _core_v1, _apps_v1, _networking_v1
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster K8s config")
    except config.ConfigException:
        try:
            config.load_kube_config()
            logger.info("Loaded local kubeconfig")
        except Exception:
            logger.warning("No K8s config found — operator will fail on K8s operations")
            return
    _core_v1 = CoreV1Api()
    _apps_v1 = AppsV1Api()
    _networking_v1 = NetworkingV1Api()


def core_v1() -> CoreV1Api:
    assert _core_v1 is not None, "Call init_k8s() first"
    return _core_v1


def apps_v1() -> AppsV1Api:
    assert _apps_v1 is not None, "Call init_k8s() first"
    return _apps_v1


def networking_v1() -> NetworkingV1Api:
    assert _networking_v1 is not None, "Call init_k8s() first"
    return _networking_v1


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

def namespace_name(customer_id: str) -> str:
    return f"customer-{customer_id}"


def create_namespace(customer_id: str, tier: str) -> None:
    from kubernetes.client.exceptions import ApiException
    ns = namespace_name(customer_id)
    try:
        core_v1().create_namespace(
            V1Namespace(
                metadata=V1ObjectMeta(
                    name=ns,
                    labels={
                        "openclaw/customer": customer_id,
                        "openclaw/tier": tier,
                    },
                )
            )
        )
        logger.info("Created namespace %s", ns)
    except ApiException as e:
        if e.status == 409:
            logger.info("Namespace %s already exists, skipping", ns)
        else:
            raise


def delete_namespace(customer_id: str) -> None:
    ns = namespace_name(customer_id)
    core_v1().delete_namespace(ns)
    logger.info("Deleted namespace %s", ns)


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

def create_config_secret(
    customer_id: str,
    *,
    telegram_bot_token: str,
    telegram_allow_from: str,
    proxy_token: str,
    model: str,
    thinking: str,
    system_prompt: str | None = None,
) -> None:
    ns = namespace_name(customer_id)
    data = {
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_ALLOW_FROM": telegram_allow_from,
        "KIMI_API_KEY": proxy_token,
        "KIMI_BASE_URL": f"{settings.token_proxy_url}/v1",
        "OPENCLAW_MODEL": model,
        "OPENCLAW_THINKING": thinking,
        "NODE_OPTIONS": "--max-old-space-size=896",
        "OPENCLAW_BROWSER_PROXY_URL": settings.browser_proxy_url,
        "OPENCLAW_CONNECTIONS": json.dumps({
            "nango_proxy_url": settings.nango_server_url,
            "nango_secret_key": settings.nango_secret_key,
            "api_url": settings.api_url,
            "api_secret": settings.agent_api_secret,
            "customer_id": customer_id,
            "web_url": settings.web_url,
            "connections": [],
        }),
    }
    if system_prompt:
        data["OPENCLAW_SYSTEM_PROMPT"] = system_prompt
    from kubernetes.client.exceptions import ApiException
    try:
        core_v1().create_namespaced_secret(
            namespace=ns,
            body=V1Secret(
                metadata=V1ObjectMeta(name="openclaw-config"),
                string_data=data,
            ),
        )
        logger.info("Created secret openclaw-config in %s", ns)
    except ApiException as e:
        if e.status == 409:
            patch_config_secret(customer_id, data)
            logger.info("Patched existing secret openclaw-config in %s", ns)
        else:
            raise


def patch_config_secret(customer_id: str, data: dict[str, str]) -> None:
    ns = namespace_name(customer_id)
    core_v1().patch_namespaced_secret(
        name="openclaw-config",
        namespace=ns,
        body=V1Secret(string_data=data),
    )
    logger.info("Patched secret openclaw-config in %s", ns)


# ---------------------------------------------------------------------------
# ResourceQuota helpers
# ---------------------------------------------------------------------------

def create_resource_quota(customer_id: str, tier: str) -> None:
    from kubernetes.client.exceptions import ApiException
    ns = namespace_name(customer_id)
    try:
        core_v1().create_namespaced_resource_quota(
            namespace=ns,
            body=V1ResourceQuota(
                metadata=V1ObjectMeta(name="tier-limits"),
                spec=V1ResourceQuotaSpec(hard=get_quota_hard(tier)),
            ),
        )
        logger.info("Created resource quota tier-limits (%s) in %s", tier, ns)
    except ApiException as e:
        if e.status == 409:
            logger.info("Resource quota already exists in %s, skipping", ns)
        else:
            raise


def patch_resource_quota(customer_id: str, tier: str) -> None:
    ns = namespace_name(customer_id)
    core_v1().patch_namespaced_resource_quota(
        name="tier-limits",
        namespace=ns,
        body=V1ResourceQuota(
            spec=V1ResourceQuotaSpec(hard=get_quota_hard(tier)),
        ),
    )
    logger.info("Patched resource quota to tier %s in %s", tier, ns)


# ---------------------------------------------------------------------------
# NetworkPolicy helpers
# ---------------------------------------------------------------------------

def create_network_policy(customer_id: str) -> None:
    from kubernetes.client.exceptions import ApiException
    ns = namespace_name(customer_id)
    try:
        _do_create_network_policy(customer_id, ns)
    except ApiException as e:
        if e.status == 409:
            logger.info("Network policy already exists in %s, skipping", ns)
        else:
            raise


def _do_create_network_policy(customer_id: str, ns: str) -> None:
    networking_v1().create_namespaced_network_policy(
        namespace=ns,
        body=V1NetworkPolicy(
            metadata=V1ObjectMeta(name="customer-isolation"),
            spec=V1NetworkPolicySpec(
                pod_selector=V1LabelSelector(),
                policy_types=["Ingress", "Egress"],
                ingress=[],
                egress=[
                    # Rule 1: Allow egress to token-proxy in platform namespace
                    V1NetworkPolicyEgressRule(
                        to=[
                            V1NetworkPolicyPeer(
                                namespace_selector=V1LabelSelector(
                                    match_labels={"kubernetes.io/metadata.name": "platform"},
                                ),
                                pod_selector=V1LabelSelector(
                                    match_labels={"app": "token-proxy"},
                                ),
                            ),
                        ],
                        ports=[V1NetworkPolicyPort(port=8080)],
                    ),
                    # Rule 2: Allow egress to Nango proxy in platform namespace
                    V1NetworkPolicyEgressRule(
                        to=[
                            V1NetworkPolicyPeer(
                                namespace_selector=V1LabelSelector(
                                    match_labels={"kubernetes.io/metadata.name": "platform"},
                                ),
                                pod_selector=V1LabelSelector(
                                    match_labels={"app": "nango-server"},
                                ),
                            ),
                        ],
                        ports=[V1NetworkPolicyPort(port=8080)],
                    ),
                    # Rule 3: Allow egress to browser-proxy in platform namespace
                    V1NetworkPolicyEgressRule(
                        to=[
                            V1NetworkPolicyPeer(
                                namespace_selector=V1LabelSelector(
                                    match_labels={"kubernetes.io/metadata.name": "platform"},
                                ),
                                pod_selector=V1LabelSelector(
                                    match_labels={"app": "browser-proxy"},
                                ),
                            ),
                        ],
                        ports=[V1NetworkPolicyPort(port=9223)],
                    ),
                    # Rule 4: Allow egress to API service in platform namespace
                    V1NetworkPolicyEgressRule(
                        to=[
                            V1NetworkPolicyPeer(
                                namespace_selector=V1LabelSelector(
                                    match_labels={"kubernetes.io/metadata.name": "platform"},
                                ),
                                pod_selector=V1LabelSelector(
                                    match_labels={"app": "api"},
                                ),
                            ),
                        ],
                        ports=[V1NetworkPolicyPort(port=8000)],
                    ),
                    # Rule 4: Allow egress to Telegram (public IPs, port 443)
                    V1NetworkPolicyEgressRule(
                        to=[
                            V1NetworkPolicyPeer(
                                ip_block=client.V1IPBlock(
                                    cidr="0.0.0.0/0",
                                    _except=[
                                        "10.0.0.0/8",
                                        "172.16.0.0/12",
                                        "192.168.0.0/16",
                                    ],
                                ),
                            ),
                        ],
                        ports=[V1NetworkPolicyPort(port=443)],
                    ),
                    # Rule 5: Allow CoreDNS (UDP 53)
                    V1NetworkPolicyEgressRule(
                        ports=[V1NetworkPolicyPort(port=53, protocol="UDP")],
                    ),
                ],
            ),
        ),
    )
    logger.info("Created network policy customer-isolation in %s", ns)


# ---------------------------------------------------------------------------
# Deployment helpers
# ---------------------------------------------------------------------------

def _build_deployment(customer_id: str, tier: str, image: str) -> V1Deployment:
    res = TIER_RESOURCES[tier]
    labels = {"app": "openclaw-gateway", "openclaw/customer": customer_id}
    return V1Deployment(
        metadata=V1ObjectMeta(name="openclaw-gateway", labels=labels),
        spec=V1DeploymentSpec(
            replicas=1,
            selector=V1LabelSelector(match_labels={"app": "openclaw-gateway"}),
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(labels=labels),
                spec=V1PodSpec(
                    automount_service_account_token=False,
                    containers=[
                        V1Container(
                            name="openclaw-gateway",
                            image=image,
                            image_pull_policy="IfNotPresent",
                            env_from=[
                                V1EnvFromSource(
                                    secret_ref=V1SecretEnvSource(name="openclaw-config"),
                                ),
                            ],
                            resources=V1ResourceRequirements(
                                requests={"cpu": res.cpu_request, "memory": res.memory_request},
                                limits={"cpu": res.cpu_limit, "memory": res.memory_limit},
                            ),
                        ),
                    ],
                    restart_policy="Always",
                ),
            ),
        ),
    )


def create_deployment(customer_id: str, tier: str, image: str) -> None:
    from kubernetes.client.exceptions import ApiException
    ns = namespace_name(customer_id)
    try:
        apps_v1().create_namespaced_deployment(
            namespace=ns,
            body=_build_deployment(customer_id, tier, image),
        )
        logger.info("Created deployment openclaw-gateway in %s", ns)
    except ApiException as e:
        if e.status == 409:
            logger.info("Deployment already exists in %s, skipping", ns)
        else:
            raise


def patch_deployment_resources(customer_id: str, tier: str) -> None:
    ns = namespace_name(customer_id)
    res = TIER_RESOURCES[tier]
    apps_v1().patch_namespaced_deployment(
        name="openclaw-gateway",
        namespace=ns,
        body={
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "openclaw-gateway",
                                "resources": {
                                    "requests": {"cpu": res.cpu_request, "memory": res.memory_request},
                                    "limits": {"cpu": res.cpu_limit, "memory": res.memory_limit},
                                },
                            }
                        ]
                    }
                }
            }
        },
    )
    logger.info("Patched deployment resources to tier %s in %s", tier, ns)


def scale_deployment(customer_id: str, replicas: int) -> None:
    ns = namespace_name(customer_id)
    apps_v1().patch_namespaced_deployment(
        name="openclaw-gateway",
        namespace=ns,
        body={"spec": {"replicas": replicas}},
    )
    logger.info("Scaled deployment in %s to %d replicas", ns, replicas)


def rollout_restart(customer_id: str) -> None:
    """Trigger a rolling restart by patching a restart annotation."""
    from datetime import datetime, timezone

    ns = namespace_name(customer_id)
    apps_v1().patch_namespaced_deployment(
        name="openclaw-gateway",
        namespace=ns,
        body={
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                }
            }
        },
    )
    logger.info("Triggered rollout restart in %s", ns)


# ---------------------------------------------------------------------------
# Pod status helpers
# ---------------------------------------------------------------------------

def wait_for_pod_ready(customer_id: str, timeout: int = 60) -> bool:
    """Poll until the deployment's pod is ready or timeout is reached."""
    import time

    ns = namespace_name(customer_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            dep = apps_v1().read_namespaced_deployment("openclaw-gateway", ns)
            ready = dep.status.ready_replicas or 0
            if ready >= 1:
                logger.info("Pod ready in %s", ns)
                return True
        except Exception:
            pass
        time.sleep(2)
    logger.error("Pod not ready within %ds in %s", timeout, ns)
    return False


def wait_for_rollout(customer_id: str, timeout: int = 60) -> bool:
    """Wait for a rolling update to complete."""
    import time

    ns = namespace_name(customer_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            dep = apps_v1().read_namespaced_deployment("openclaw-gateway", ns)
            status = dep.status
            if (
                status.updated_replicas == dep.spec.replicas
                and (status.ready_replicas or 0) >= dep.spec.replicas
                and (status.unavailable_replicas or 0) == 0
            ):
                logger.info("Rollout complete in %s", ns)
                return True
        except Exception:
            pass
        time.sleep(2)
    logger.error("Rollout not complete within %ds in %s", timeout, ns)
    return False
