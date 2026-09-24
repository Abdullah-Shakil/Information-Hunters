from information_hunters.pipeline import process_job


def test_health_and_open_routes(client):
    assert client.get("/health").status_code == 200
    assert client.get("/leads").status_code == 200
    assert client.get("/fleet").status_code == 200


def test_hunt_writes_prioritised_leads_and_filters(client):
    created = client.post(
        "/jobs",
        json={"name": "Manchester plumbers", "categories": ["plumbers"], "regions": ["Manchester"], "limit_per_search": 8},
    )
    assert created.status_code == 200
    job_id = created.json()["id"]
    process_job(job_id, "test-worker", step_delay=0)

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["qualified_count"] == 6
    assert job["rejected_count"] == 2

    leads = client.get("/leads").json()
    scores = [item["priority_score"] for item in leads["items"]]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 100
    top = leads["items"][0]
    assert top["has_website"] is False
    assert top["mobile"]
    assert top["email"]
    assert top["location"] == "Manchester"
    assert top["category"] == "plumbers"
    assert top["synthetic"] is True

    no_site = client.get("/leads", params={"no_website": True, "has_mobile": True}).json()
    assert no_site["total"] >= 1
    assert all(item["has_website"] is False and item["mobile"] for item in no_site["items"])

    detail = client.get(f"/leads/{top['id']}").json()
    assert "Demo verifier" in detail["verification_notes"]
    assert detail["sources"]

    exported = client.get("/leads/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert "Harbour Heat Ltd" in exported.text
    assert "priority_score" in exported.text.splitlines()[0]


def test_pause_and_stop_and_secret_is_not_echoed(client):
    created = client.post(
        "/jobs",
        json={"name": "Leeds painters", "categories": ["painters"], "regions": ["Leeds"]},
    ).json()
    paused = client.post(f"/jobs/{created['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    process_job(created["id"], "test-worker", step_delay=0)
    assert client.get("/leads").json()["total"] == 0

    stopped = client.post(f"/jobs/{created['id']}/stop")
    assert stopped.json()["status"] == "stopped"
    again = client.post(f"/jobs/{created['id']}/pause")
    assert again.status_code == 409

    saved = client.post("/settings/secrets", json={"name": "COMPANIES_HOUSE_API_KEY", "value": "ch-live-key-1234"})
    assert saved.status_code == 200
    body = saved.json()
    assert body["configured"] is True
    assert body["last4"] == "1234"
    assert "ch-live-key-1234" not in saved.text
    settings = client.get("/settings").json()
    assert settings["demo_mode"] is True
    listed = next(item for item in settings["secrets"] if item["name"] == "COMPANIES_HOUSE_API_KEY")
    assert listed["last4"] == "1234"
    assert "ch-live-key-1234" not in client.get("/settings").text


def test_stats_after_a_completed_hunt(client):
    created = client.post(
        "/jobs",
        json={"name": "Bristol electricians", "categories": ["electricians"], "regions": ["Bristol"]},
    ).json()
    process_job(created["id"], "test-worker", step_delay=0)
    stats = client.get("/stats").json()
    assert stats["leads"] == 6
    assert stats["high_priority"] >= 1
    assert stats["no_website"] >= 1
