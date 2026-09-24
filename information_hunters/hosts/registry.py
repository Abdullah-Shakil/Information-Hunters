"""Adapter lookup."""

from information_hunters.hosts.apify_host import ApifyHost
from information_hunters.hosts.gcp import GoogleCloudRunHost
from information_hunters.hosts.github_actions import GitHubActionsHost
from information_hunters.hosts.oracle import OracleCloudHost
from information_hunters.hosts.pause_hosts import KoyebHost, RenderHost

ADAPTERS = {
    "github_actions": GitHubActionsHost(),
    "gcp_cloud_run": GoogleCloudRunHost(),
    "oracle_cloud": OracleCloudHost(),
    "apify": ApifyHost(),
    "koyeb": KoyebHost(),
    "render": RenderHost(),
}


def get_adapter(provider: str):
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        raise KeyError(provider)
    return adapter
