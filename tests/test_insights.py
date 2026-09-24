"""Performance, errors, and live activity are stored with the hunt."""

from information_hunters.pipeline import process_job


def test_hunt_writes_activity_performance_and_hides_nothing_sensitive(client, auth_header):
    assert client.get("/activity").status_code == 401
    assert client.get("/performance").status_code == 401
    assert client.get("/errors").status_code == 401

    created = client.post(
        "/jobs",
        headers=auth_header,
        json={"name": "Leeds plumbers", "categories": ["plumbers"], "regions": ["Leeds"], "limit_per_search": 8},
    )
    job_id = created.json()["id"]
    process_job(job_id, "test-worker", step_delay=0)

    activity = client.get("/activity", headers=auth_header).json()["items"]
    messages = [item["message"] for item in activity]
    assert any(item["kind"] == "searching" and "Leeds" in item["message"] and "plumb" in item["message"].lower() for item in activity)
    found = [item for item in activity if item["kind"] == "found"]
    assert found
    assert any(item["detail"].get("email") for item in found)
    assert any("no website" in item["message"] or "email " in item["message"] for item in found)

    filtered = client.get("/activity", headers=auth_header, params={"kind": "searching", "host": "local"}).json()["items"]
    assert filtered
    assert all(item["kind"] == "searching" for item in filtered)

    performance = client.get("/performance", headers=auth_header).json()
    assert performance["totals"]["runs"] == 1
    assert performance["totals"]["companies_searched"] == 8
    assert performance["totals"]["leads_found"] == 6
    assert performance["totals"]["success_rate"] == 75
    assert performance["totals"]["leads_with_email"] >= 1
    assert performance["totals"]["leads_with_mobile"] >= 1
    assert performance["totals"]["leads_no_website"] >= 1
    run = performance["runs"][0]
    assert run["job_name"] == "Leeds plumbers"
    assert run["status"] == "completed"
    assert run["worker_id"] == "test-worker"
    assert run["duration_seconds"] >= 0

    local = client.get("/performance", headers=auth_header, params={"host": "local", "worker": "test-worker"}).json()
    assert local["totals"]["runs"] == 1
    other = client.get("/performance", headers=auth_header, params={"host": "oracle_cloud"}).json()
    assert other["totals"]["runs"] == 0

    # A failed provider call is recorded without taking the desk down.
    client.post("/hosts/github_actions/start", headers=auth_header)
    errors = client.get("/errors", headers=auth_header).json()["items"]
    assert errors
    assert any(item["provider"] == "github_actions" for item in errors)
    typed = client.get("/errors", headers=auth_header, params={"provider": "github_actions", "error_type": "error"}).json()
    assert typed["items"]
    assert all("ghp_" not in item["message"] for item in typed["items"])
