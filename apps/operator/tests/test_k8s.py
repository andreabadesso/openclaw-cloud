"""Tests for openclaw_operator.k8s."""

import time
from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client import V1Deployment, V1DeploymentSpec, V1DeploymentStatus

from openclaw_operator import k8s


@pytest.fixture(autouse=True)
def _patch_k8s_clients(mock_core_v1, mock_apps_v1, mock_networking_v1):
    """Inject mock K8s clients into the k8s module."""
    with (
        patch.object(k8s, "_core_v1", mock_core_v1),
        patch.object(k8s, "_apps_v1", mock_apps_v1),
        patch.object(k8s, "_networking_v1", mock_networking_v1),
    ):
        yield


class TestInitK8s:
    @patch("openclaw_operator.k8s.config")
    def test_in_cluster_config(self, mock_config):
        mock_config.load_incluster_config.return_value = None
        k8s.init_k8s()
        mock_config.load_incluster_config.assert_called_once()

    @patch("openclaw_operator.k8s.config")
    def test_fallback_to_local_config(self, mock_config):
        from kubernetes.config import ConfigException

        mock_config.ConfigException = ConfigException
        mock_config.load_incluster_config.side_effect = ConfigException("not in cluster")
        mock_config.load_kube_config.return_value = None
        k8s.init_k8s()
        mock_config.load_kube_config.assert_called_once()

    @patch("openclaw_operator.k8s.config")
    def test_no_config_available(self, mock_config):
        from kubernetes.config import ConfigException

        mock_config.ConfigException = ConfigException
        mock_config.load_incluster_config.side_effect = ConfigException("no")
        mock_config.load_kube_config.side_effect = Exception("no kubeconfig")
        k8s.init_k8s()
        # Should not crash, just warn


class TestNamespaceHelpers:
    def test_namespace_name(self):
        assert k8s.namespace_name("abc123") == "customer-abc123"

    def test_create_namespace(self, mock_core_v1):
        k8s.create_namespace("cust1", "starter")
        mock_core_v1.create_namespace.assert_called_once()
        ns_arg = mock_core_v1.create_namespace.call_args[0][0]
        assert ns_arg.metadata.name == "customer-cust1"
        assert ns_arg.metadata.labels["openclaw/customer"] == "cust1"
        assert ns_arg.metadata.labels["openclaw/tier"] == "starter"

    def test_delete_namespace(self, mock_core_v1):
        k8s.delete_namespace("cust1")
        mock_core_v1.delete_namespace.assert_called_once_with("customer-cust1")


class TestSecretHelpers:
    def test_create_config_secret(self, mock_core_v1):
        k8s.create_config_secret(
            "cust1",
            telegram_bot_token="tok123",
            telegram_allow_from="user1",
            proxy_token="proxy-tok",
            model="gpt-4",
            thinking="high",
        )
        mock_core_v1.create_namespaced_secret.assert_called_once()
        call_kwargs = mock_core_v1.create_namespaced_secret.call_args[1]
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        assert body.string_data["TELEGRAM_BOT_TOKEN"] == "tok123"
        assert body.string_data["TELEGRAM_ALLOW_FROM"] == "user1"
        assert body.string_data["KIMI_API_KEY"] == "proxy-tok"
        assert body.string_data["OPENCLAW_MODEL"] == "gpt-4"
        assert body.string_data["OPENCLAW_THINKING"] == "high"
        assert body.string_data["NODE_OPTIONS"] == "--max-old-space-size=896"
        assert "token-proxy" in body.string_data["KIMI_BASE_URL"]

    def test_patch_config_secret(self, mock_core_v1):
        k8s.patch_config_secret("cust1", {"FOO": "bar"})
        mock_core_v1.patch_namespaced_secret.assert_called_once()
        call_kwargs = mock_core_v1.patch_namespaced_secret.call_args[1]
        assert call_kwargs["name"] == "openclaw-config"
        assert call_kwargs["namespace"] == "customer-cust1"
        assert call_kwargs["body"].string_data == {"FOO": "bar"}


class TestResourceQuotaHelpers:
    def test_create_resource_quota(self, mock_core_v1):
        k8s.create_resource_quota("cust1", "starter")
        mock_core_v1.create_namespaced_resource_quota.assert_called_once()
        call_kwargs = mock_core_v1.create_namespaced_resource_quota.call_args[1]
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        assert body.metadata.name == "tier-limits"
        assert body.spec.hard["requests.cpu"] == "250m"

    def test_patch_resource_quota(self, mock_core_v1):
        k8s.patch_resource_quota("cust1", "pro")
        mock_core_v1.patch_namespaced_resource_quota.assert_called_once()
        call_kwargs = mock_core_v1.patch_namespaced_resource_quota.call_args[1]
        assert call_kwargs["name"] == "tier-limits"
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        assert body.spec.hard["requests.cpu"] == "500m"


class TestNetworkPolicyHelpers:
    def test_create_network_policy(self, mock_networking_v1):
        k8s.create_network_policy("cust1")
        mock_networking_v1.create_namespaced_network_policy.assert_called_once()
        call_kwargs = mock_networking_v1.create_namespaced_network_policy.call_args[1]
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        assert body.metadata.name == "customer-isolation"
        assert body.spec.policy_types == ["Ingress", "Egress"]
        # 6 egress rules: token-proxy, nango, browser-proxy, api, public 443, dns
        assert len(body.spec.egress) == 6


class TestDeploymentHelpers:
    def test_create_deployment(self, mock_apps_v1):
        k8s.create_deployment("cust1", "starter", "myimage:latest")
        mock_apps_v1.create_namespaced_deployment.assert_called_once()
        call_kwargs = mock_apps_v1.create_namespaced_deployment.call_args[1]
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        assert body.metadata.name == "openclaw-gateway"
        container = body.spec.template.spec.containers[0]
        assert container.image == "myimage:latest"
        assert container.image_pull_policy == "IfNotPresent"
        assert container.resources.requests["cpu"] == "250m"

    def test_patch_deployment_resources(self, mock_apps_v1):
        k8s.patch_deployment_resources("cust1", "pro")
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args[1]
        assert call_kwargs["name"] == "openclaw-gateway"
        assert call_kwargs["namespace"] == "customer-cust1"
        body = call_kwargs["body"]
        resources = body["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert resources["requests"]["cpu"] == "500m"

    def test_scale_deployment(self, mock_apps_v1):
        k8s.scale_deployment("cust1", 0)
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args[1]
        assert call_kwargs["body"] == {"spec": {"replicas": 0}}

    def test_rollout_restart(self, mock_apps_v1):
        k8s.rollout_restart("cust1")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args[1]
        annotations = call_kwargs["body"]["spec"]["template"]["metadata"]["annotations"]
        assert "kubectl.kubernetes.io/restartedAt" in annotations


class TestWaitForPodReady:
    def test_pod_ready_immediately(self, mock_apps_v1):
        dep = MagicMock()
        dep.status.ready_replicas = 1
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"):
            assert k8s.wait_for_pod_ready("cust1", timeout=10) is True

    def test_pod_not_ready_timeout(self, mock_apps_v1):
        dep = MagicMock()
        dep.status.ready_replicas = 0
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            # First call returns 0 (start), second returns 0.5 (loop), third returns 999 (past deadline)
            mock_time.side_effect = [0, 0.5, 999]
            assert k8s.wait_for_pod_ready("cust1", timeout=5) is False

    def test_pod_ready_after_retry(self, mock_apps_v1):
        dep_not_ready = MagicMock()
        dep_not_ready.status.ready_replicas = 0
        dep_ready = MagicMock()
        dep_ready.status.ready_replicas = 1
        mock_apps_v1.read_namespaced_deployment.side_effect = [dep_not_ready, dep_ready]

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            mock_time.side_effect = [0, 0.5, 1.0, 1.5]
            assert k8s.wait_for_pod_ready("cust1", timeout=10) is True

    def test_pod_ready_none_replicas(self, mock_apps_v1):
        dep = MagicMock()
        dep.status.ready_replicas = None
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            mock_time.side_effect = [0, 0.5, 999]
            assert k8s.wait_for_pod_ready("cust1", timeout=5) is False

    def test_pod_ready_survives_api_error(self, mock_apps_v1):
        dep_ready = MagicMock()
        dep_ready.status.ready_replicas = 1
        mock_apps_v1.read_namespaced_deployment.side_effect = [Exception("API error"), dep_ready]

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            mock_time.side_effect = [0, 0.5, 1.0, 1.5]
            assert k8s.wait_for_pod_ready("cust1", timeout=10) is True


class TestWaitForRollout:
    def test_rollout_complete_immediately(self, mock_apps_v1):
        dep = MagicMock()
        dep.spec.replicas = 1
        dep.status.updated_replicas = 1
        dep.status.ready_replicas = 1
        dep.status.unavailable_replicas = 0
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"):
            assert k8s.wait_for_rollout("cust1", timeout=10) is True

    def test_rollout_timeout(self, mock_apps_v1):
        dep = MagicMock()
        dep.spec.replicas = 1
        dep.status.updated_replicas = 0
        dep.status.ready_replicas = 0
        dep.status.unavailable_replicas = 1
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            mock_time.side_effect = [0, 0.5, 999]
            assert k8s.wait_for_rollout("cust1", timeout=5) is False

    def test_rollout_unavailable_none_treated_as_zero(self, mock_apps_v1):
        dep = MagicMock()
        dep.spec.replicas = 1
        dep.status.updated_replicas = 1
        dep.status.ready_replicas = 1
        dep.status.unavailable_replicas = None
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        with patch("time.sleep"):
            assert k8s.wait_for_rollout("cust1", timeout=10) is True

    def test_rollout_survives_api_error(self, mock_apps_v1):
        dep = MagicMock()
        dep.spec.replicas = 1
        dep.status.updated_replicas = 1
        dep.status.ready_replicas = 1
        dep.status.unavailable_replicas = None
        mock_apps_v1.read_namespaced_deployment.side_effect = [Exception("boom"), dep]

        with patch("time.sleep"), patch("time.monotonic") as mock_time:
            mock_time.side_effect = [0, 0.5, 1.0, 1.5]
            assert k8s.wait_for_rollout("cust1", timeout=10) is True


class TestAccessorAssertions:
    def test_core_v1_without_init_raises(self):
        with patch.object(k8s, "_core_v1", None):
            with pytest.raises(AssertionError, match="Call init_k8s"):
                k8s.core_v1()

    def test_apps_v1_without_init_raises(self):
        with patch.object(k8s, "_apps_v1", None):
            with pytest.raises(AssertionError, match="Call init_k8s"):
                k8s.apps_v1()

    def test_networking_v1_without_init_raises(self):
        with patch.object(k8s, "_networking_v1", None):
            with pytest.raises(AssertionError, match="Call init_k8s"):
                k8s.networking_v1()
