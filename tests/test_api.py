from campaign_doctor.analysis import DELAYED_REPLY_SUMMARY
from campaign_doctor.api.app import create_app
from fastapi.testclient import TestClient

client = TestClient(create_app())


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_scenarios_are_labeled_synthetic():
    response = client.get("/api/scenarios")
    body = response.json()

    assert response.status_code == 200
    assert body["scenarios"][0]["scenario_id"] == "delayed_reply"
    assert body["scenarios"][0]["name"] == "Delayed reply notification"
    assert body["scenarios"][0]["problem_category"] == "delayed_reply"
    assert body["scenarios"][0]["synthetic"] is True
    assert "09:58" in body["scenarios"][0]["description"]
    assert "scenarios/" not in response.text
    assert _no_local_path(response.text)


def test_report_reconstructs_the_delayed_reply():
    response = client.get("/api/scenarios/delayed_reply/report")
    body = response.json()

    assert response.status_code == 200
    assert body["synthetic"] is True
    assert body["confirmed_production_bug"] is False
    assert body["diagnosis"]["confirmed_production_bug"] is False
    occurred = [event["event_id"] for event in body["occurrence_order"]]
    observed = [step["event"]["event_id"] for step in body["observation_order"]]
    assert occurred == ["evt_initial_email", "evt_prospect_reply", "evt_followup_sent"]
    assert observed == ["evt_initial_email", "evt_followup_sent", "evt_prospect_reply"]
    finding = body["diagnosis"]["findings"][0]
    assert body["diagnosis"]["pattern_matched"] is True
    assert body["diagnosis"]["summary"] == DELAYED_REPLY_SUMMARY
    assert finding["known_state_at_decision"] == "ACTIVE"
    assert finding["reply_occurred_at"] == "2026-10-27T09:58:00Z"
    assert finding["reply_observed_at"] == "2026-10-27T10:02:00Z"
    assert body["diagnosis"]["sends_after_known_stop"] == []
    assert body["final_states"] == [
        {"campaign_id": "camp_synthetic", "lead_id": "lead_synthetic", "state": "STOPPED"}
    ]
    followup = body["observation_order"][1]
    assert followup["known_state_before"] == "ACTIVE"
    assert followup["known_state_after"] == "ACTIVE"


def test_unknown_scenario_is_a_plain_404():
    response = client.get("/api/scenarios/not-a-scenario/report")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown scenario."}
    assert _no_local_path(response.text)


def test_filename_is_not_accepted_as_a_scenario_id():
    response = client.get("/api/scenarios/delayed_reply.json/report")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown scenario."
    assert _no_local_path(response.text)


def test_compare_reply_visible_cancels_without_sending():
    before = client.get("/api/scenarios/delayed_reply/report").json()
    response = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "reply_visible"},
    )
    after = client.get("/api/scenarios/delayed_reply/report").json()
    body = response.json()
    row = body["comparisons"][0]

    assert response.status_code == 200
    assert after["occurrence_order"] == before["occurrence_order"]
    assert body["synthetic"] is True
    assert body["confirmed_production_bug"] is False
    assert body["ledger"]["durable_across_requests"] is False
    assert body["ledger"]["scope"] == "single_request"
    assert "not durable" in body["ledger"]["explanation"]
    assert row["unguarded"]["outcome"] == "SENT"
    assert row["unguarded"]["provider_check"] == "not run"
    assert row["unguarded"]["matched_event_id"] == "evt_followup_sent"
    assert row["guarded"]["decision"] == "CANCEL"
    assert row["guarded"]["known_state"] == "ACTIVE"
    assert row["guarded"]["provider_check"] == "REPLY_CONFIRMED"
    assert row["guarded"]["simulated_send_recorded"] is False
    assert row["guarded"]["records_consulted"] is True
    assert row["guarded"]["replies"][0]["visible_to_provider_at_decision"] is True
    assert "No email was sent" in row["guarded"]["explanation"]
    assert any("does not guarantee" in item for item in body["limitations"])


def test_compare_stale_provider_allows_without_changing_the_log():
    response = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "reply_not_yet_visible"},
    )
    row = response.json()["comparisons"][0]
    reply = row["guarded"]["replies"][0]

    assert response.status_code == 200
    assert row["guarded"]["decision"] == "ALLOW"
    assert row["guarded"]["provider_check"] == "NO_REPLY_FOUND"
    assert row["guarded"]["simulated_send_recorded"] is True
    assert reply["occurred_at"] == "2026-10-27T09:58:00Z"
    assert reply["visible_at"] == "2026-10-27T10:01:00Z"
    assert reply["visible_to_provider_at_decision"] is False
    assert "No message left this program" in row["guarded"]["explanation"]


def test_compare_provider_unavailable_defers():
    response = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "provider_unavailable"},
    )
    row = response.json()["comparisons"][0]

    assert response.status_code == 200
    assert row["guarded"]["decision"] == "DEFER"
    assert row["guarded"]["provider_check"] == "UNAVAILABLE"
    assert row["guarded"]["failure_kind"] == "TIMEOUT"
    assert row["guarded"]["records_consulted"] is False
    assert row["guarded"]["replies"] == []
    assert row["guarded"]["simulated_send_recorded"] is False
    assert "No email was sent" in row["guarded"]["explanation"]


def test_compare_rejects_an_unknown_condition():
    response = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "send_anyway"},
    )

    assert response.status_code == 422
    assert _no_local_path(response.text)


def test_compare_rejects_a_missing_body_and_extra_fields():
    missing = client.post("/api/scenarios/delayed_reply/compare", json={})
    extra = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "reply_visible", "send_email": True},
    )
    garbage = client.post(
        "/api/scenarios/delayed_reply/compare",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )

    assert missing.status_code == 422
    assert extra.status_code == 422
    assert garbage.status_code == 422


def test_compare_unknown_followup_and_unknown_scenario():
    missing_followup = client.post(
        "/api/scenarios/delayed_reply/compare",
        json={"provider_condition": "reply_visible", "followup_event_id": "evt_prospect_reply"},
    )
    missing_scenario = client.post(
        "/api/scenarios/missing/compare",
        json={"provider_condition": "reply_visible"},
    )

    assert missing_followup.status_code == 422
    assert missing_followup.json()["detail"] == "Unknown follow-up event."
    assert missing_scenario.status_code == 404
    assert missing_scenario.json()["detail"] == "Unknown scenario."


def test_cors_allows_the_local_next_app_only():
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    other = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in other.headers


def test_cors_origins_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://doctor.example, https://www.doctor.example/")
    configured = TestClient(create_app())
    allowed = configured.get("/api/health", headers={"Origin": "https://doctor.example"})
    trimmed = configured.get("/api/health", headers={"Origin": "https://www.doctor.example"})
    local = configured.get("/api/health", headers={"Origin": "http://localhost:3000"})

    assert allowed.headers["access-control-allow-origin"] == "https://doctor.example"
    assert trimmed.headers["access-control-allow-origin"] == "https://www.doctor.example"
    assert "access-control-allow-origin" not in local.headers


def test_unexpected_errors_do_not_leak_paths_or_traces(monkeypatch):
    def boom():
        raise RuntimeError("failed at /Users/secret/scenarios/delayed_reply.json")

    monkeypatch.setattr("campaign_doctor.api.app.list_scenarios", boom)
    response = TestClient(create_app(), raise_server_exceptions=False).get("/api/scenarios")

    assert response.status_code == 500
    assert response.json()["detail"] == "The request could not be completed."
    assert _no_local_path(response.text)
    assert "delayed_reply.json" not in response.text
    assert "RuntimeError" not in response.text


def _no_local_path(text: str) -> bool:
    return "Users/" not in text and "scenarios/" not in text and "Traceback" not in text
