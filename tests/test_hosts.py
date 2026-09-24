"""Host adapters are exercised with a fake HTTP transport. No live provider is called."""

import json

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from information_hunters.ops import set_http_client_factory


def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def _install(handler):
    def factory():
        return httpx.Client(transport=httpx.MockTransport(handler))

    set_http_client_factory(factory)


def test_catalog_lists_free_hosts_and_states_what_cannot_be_started(client, auth_header):
    body = client.get("/hosts", headers=auth_header).json()
    providers = {item["provider"] for item in body["hosts"]}
    assert {"github_actions", "gcp_cloud_run", "oracle_cloud", "apify", "koyeb", "render", "scrapingbee", "libraries"} <= providers
    libraries = next(item for item in body["hosts"] if item["provider"] == "libraries")
    assert libraries["controllable"] is False
    assert "library" in libraries["uncontrolled_reason"].lower() or "Python library" in libraries["uncontrolled_reason"]
    excluded = {item["id"] for item in body["excluded"]}
    assert {"fly", "huggingface", "expandi"} <= excluded
    blocked = client.post("/hosts/libraries/start", headers=auth_header)
    assert blocked.status_code == 400
    assert "start" in blocked.text.lower() or "library" in blocked.text.lower()


def test_github_start_stop_and_token_is_not_returned(client, auth_header):
    token = "ghp_supersecretvalue"
    calls = []
    state = {"dispatched": False}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert token not in str(request.url)
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "owner"})
        if request.url.path == "/repos/owner/hunters":
            return httpx.Response(200, json={"private": False, "name": "hunters"})
        if request.url.path.endswith("/dispatches"):
            state["dispatched"] = True
            return httpx.Response(204)
        if request.url.path.endswith("/runs"):
            runs = [{"id": 42, "status": "in_progress"}] if state["dispatched"] else []
            return httpx.Response(200, json={"workflow_runs": runs})
        if request.url.path.endswith("/runs/42/cancel"):
            return httpx.Response(202, json={})
        return httpx.Response(404, json={"message": "missing"})

    _install(handler)
    saved = client.post(
        "/hosts/github_actions",
        headers=auth_header,
        json={"values": {"GITHUB_TOKEN": token, "GITHUB_OWNER": "owner", "GITHUB_REPO": "hunters"}},
    )
    assert saved.status_code == 200
    assert token not in saved.text
    field = next(item for item in saved.json()["fields"] if item["name"] == "GITHUB_TOKEN")
    assert field["last4"] == "alue"
    assert field["value"] == ""

    started = client.post("/hosts/github_actions/start", headers=auth_header)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert started.json()["remote_id"] == "42"
    assert token not in started.text
    assert any(path.endswith("/dispatches") for _, path in calls)

    stopped = client.post("/hosts/github_actions/stop", headers=auth_header)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert any(path.endswith("/cancel") for _, path in calls)


def test_github_private_minutes_mark_quota_without_dispatch(client, auth_header):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "owner"})
        if request.url.path == "/repos/owner/private":
            return httpx.Response(200, json={"private": True})
        if request.url.path == "/users/owner/settings/billing/actions":
            return httpx.Response(200, json={"total_minutes_used": 2000, "included_minutes": 2000})
        return httpx.Response(500, json={"message": "should not be called"})

    _install(handler)
    client.post(
        "/hosts/github_actions",
        headers=auth_header,
        json={"values": {"GITHUB_TOKEN": "ghp_minutesexhausted1", "GITHUB_OWNER": "owner", "GITHUB_REPO": "private"}},
    )
    started = client.post("/hosts/github_actions/start", headers=auth_header)
    assert started.status_code == 200
    assert started.json()["status"] == "quota_exhausted"
    assert not any(path.endswith("/dispatches") for path in calls)


def test_gcp_quota_stops_the_host(client, auth_header):
    pem = _pem()
    service_account = json.dumps({"client_email": "hunter@example.iam.gserviceaccount.com", "private_key": pem})

    def handler(request: httpx.Request) -> httpx.Response:
        assert "BEGIN PRIVATE KEY" not in request.content.decode()
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.test"})
        if request.url.path.endswith("/information-hunters:run"):
            return httpx.Response(429, json={"error": {"message": "Quota exceeded for quota metric."}})
        if request.url.path.endswith(":resume"):
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"name": "scheduler"})

    _install(handler)
    saved = client.post(
        "/hosts/gcp_cloud_run",
        headers=auth_header,
        json={"values": {"GCP_SERVICE_ACCOUNT_JSON": service_account, "GCP_PROJECT_ID": "demo-project", "GCP_REGION": "us-central1"}},
    )
    assert saved.status_code == 200
    assert pem not in saved.text
    assert "ya29" not in saved.text
    started = client.post("/hosts/gcp_cloud_run/start", headers=auth_header)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "quota_exhausted"
    assert pem not in started.text


def test_oracle_start_stop_and_capacity(client, auth_header):
    pem = _pem()
    mode = {"capacity": False}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Signature version")
        assert "BEGIN PRIVATE KEY" not in request.content.decode()
        if mode["capacity"]:
            return httpx.Response(409, json={"code": "LimitExceeded", "message": "Out of host capacity."})
        if "action=STOP" in str(request.url):
            return httpx.Response(200, json={"lifecycleState": "STOPPING", "id": "ocid1.instance.oc1.uk-london-1.example"})
        return httpx.Response(200, json={"lifecycleState": "STARTING", "id": "ocid1.instance.oc1.uk-london-1.example"})

    _install(handler)
    values = {
        "OCI_TENANCY_OCID": "ocid1.tenancy.oc1..example",
        "OCI_USER_OCID": "ocid1.user.oc1..example",
        "OCI_FINGERPRINT": "aa:bb:cc",
        "OCI_PRIVATE_KEY": pem,
        "OCI_REGION": "uk-london-1",
        "OCI_INSTANCE_OCID": "ocid1.instance.oc1.uk-london-1.example",
    }
    assert client.post("/hosts/oracle_cloud", headers=auth_header, json={"values": values}).status_code == 200
    started = client.post("/hosts/oracle_cloud/start", headers=auth_header)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert pem not in started.text
    stopped = client.post("/hosts/oracle_cloud/stop", headers=auth_header)
    assert stopped.json()["status"] == "stopped"
    mode["capacity"] = True
    exhausted = client.post("/hosts/oracle_cloud/start", headers=auth_header)
    assert exhausted.json()["status"] == "quota_exhausted"


def test_apify_blocks_start_when_free_credit_is_gone(client, auth_header):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert "token=" not in str(request.url)
        if request.url.path == "/v2/users/me":
            return httpx.Response(200, json={"data": {"plan": {"monthlyUsageCreditsUsd": 5}, "monthlyUsageUsd": 5}})
        return httpx.Response(404, json={"error": {"message": "unused"}})

    _install(handler)
    client.post(
        "/hosts/apify",
        headers=auth_header,
        json={"values": {"APIFY_TOKEN": "apify_api_secretvalue", "APIFY_ACTOR_ID": "owner~information-hunters"}},
    )
    started = client.post("/hosts/apify/start", headers=auth_header)
    assert started.json()["status"] == "quota_exhausted"
    assert "apify_api_secretvalue" not in started.text
    assert not any(path.endswith("/runs") for path in calls)


def test_apify_koyeb_and_render_start_and_stop(client, auth_header):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v2/users/me":
            return httpx.Response(200, json={"data": {"plan": {"monthlyUsageCreditsUsd": 5}, "monthlyUsageUsd": 1.25}})
        if path.endswith("/runs") and request.method == "POST":
            return httpx.Response(201, json={"data": {"id": "run1", "status": "RUNNING"}})
        if path.startswith("/v2/acts/"):
            return httpx.Response(200, json={"data": {"id": "actor1"}})
        if path == "/v2/schedules" and request.method == "GET":
            return httpx.Response(200, json={"data": {"items": []}})
        if path == "/v2/schedules" and request.method == "POST":
            return httpx.Response(201, json={"data": {"id": "sched1", "name": "information-hunters"}})
        if path.endswith("/abort"):
            return httpx.Response(200, json={"data": {"status": "ABORTING"}})
        if path.endswith("/schedules/sched1"):
            return httpx.Response(200, json={"data": {"id": "sched1"}})
        if "koyeb" in request.url.host and path.endswith("/resume"):
            return httpx.Response(200, json={"service": {"id": "svc1", "status": "HEALTHY"}})
        if "koyeb" in request.url.host and path.endswith("/pause"):
            return httpx.Response(200, json={"service": {"id": "svc1", "status": "PAUSED"}})
        if "render.com" in request.url.host and path.endswith("/resume"):
            return httpx.Response(202, json={})
        if "render.com" in request.url.host and path.endswith("/suspend"):
            return httpx.Response(202, json={})
        if "render.com" in request.url.host:
            return httpx.Response(200, json={"id": "srv-1", "suspended": "not_suspended"})
        return httpx.Response(404, json={"message": path})

    _install(handler)
    client.post("/hosts/apify", headers=auth_header, json={"values": {"APIFY_TOKEN": "apify_api_tokentest1", "APIFY_ACTOR_ID": "owner~information-hunters"}})
    started = client.post("/hosts/apify/start", headers=auth_header)
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert started.json()["remote_id"] == "run1"
    # Stop looks up schedules again; the fake list is empty, and abort still runs.
    stopped = client.post("/hosts/apify/stop", headers=auth_header)
    assert stopped.json()["status"] == "stopped"

    client.post("/hosts/koyeb", headers=auth_header, json={"values": {"KOYEB_API_TOKEN": "koyeb_secret_token", "KOYEB_SERVICE_ID": "svc1"}})
    koyeb = client.post("/hosts/koyeb/start", headers=auth_header)
    assert koyeb.json()["status"] == "running"
    assert "sleeps" in koyeb.json()["status_detail"]
    assert "koyeb_secret_token" not in koyeb.text
    assert client.post("/hosts/koyeb/stop", headers=auth_header).json()["status"] == "stopped"

    client.post("/hosts/render", headers=auth_header, json={"values": {"RENDER_API_KEY": "rnd_secret_key", "RENDER_SERVICE_ID": "srv-1"}})
    render = client.post("/hosts/render/start", headers=auth_header)
    assert render.json()["status"] == "running"
    assert "750" in render.json()["status_detail"] or "sleeps" in render.json()["status_detail"]
    assert client.post("/hosts/render/stop", headers=auth_header).json()["status"] == "stopped"


def test_scrapingbee_usage_and_settings_test_hide_the_key(client, auth_header):
    key = "scrapingbee_secret_key_99"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == key
        return httpx.Response(200, json={"max_api_credit": 1000, "used_api_credit": 1000})

    _install(handler)
    client.post("/settings/secrets", headers=auth_header, json={"name": "SCRAPINGBEE_API_KEY", "value": key})
    tested = client.post("/settings/test", headers=auth_header, json={"provider": "scrapingbee"})
    assert tested.status_code == 200
    assert tested.json()["status"] == "quota_exhausted"
    assert key not in tested.text
    assert tested.json()["usage"]["limit"] == 1000
    listed = client.get("/hosts", headers=auth_header).json()
    card = next(item for item in listed["hosts"] if item["provider"] == "scrapingbee")
    assert card["controllable"] is False
    assert card["status"] == "quota_exhausted"
