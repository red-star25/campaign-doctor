import pytest

from campaign_doctor.models import EventType, LogValidationError, load_scenario, parse_scenario
from tests.support import DELAYED_REPLY, make_event, utc


def test_fixture_records_the_delayed_reply_clocks():
    scenario = load_scenario(DELAYED_REPLY)

    assert scenario.scenario_id == "delayed_reply"
    assert [event.event_id for event in scenario.events] == [
        "evt_initial_email",
        "evt_prospect_reply",
        "evt_followup_sent",
    ]
    initial, reply, followup = scenario.events
    assert initial.type is EventType.INITIAL_EMAIL_SENT
    assert initial.occurred_at == utc(9, 0)
    assert initial.observed_at == utc(9, 0)
    assert reply.type is EventType.PROSPECT_REPLIED
    assert reply.occurred_at == utc(9, 58)
    assert reply.observed_at == utc(10, 2)
    assert followup.type is EventType.FOLLOWUP_SENT
    assert followup.occurred_at == utc(10, 0)
    assert followup.observed_at == utc(10, 0)


def test_missing_timestamp_is_rejected():
    raw = _raw_event()
    del raw["occurred_at"]

    with pytest.raises(LogValidationError, match="occurred_at is missing"):
        parse_scenario({"scenario_id": "bad", "events": [raw]})


def test_null_timestamp_is_rejected():
    raw = _raw_event()
    raw["observed_at"] = None

    with pytest.raises(LogValidationError, match="observed_at is missing"):
        parse_scenario({"scenario_id": "bad", "events": [raw]})


def test_malformed_timestamp_is_rejected():
    raw = _raw_event()
    raw["occurred_at"] = "not-a-timestamp"

    with pytest.raises(LogValidationError, match="not a valid ISO-8601 timestamp"):
        parse_scenario({"scenario_id": "bad", "events": [raw]})


def test_timestamp_without_timezone_is_rejected():
    raw = _raw_event()
    raw["observed_at"] = "2026-10-27T10:00:00"

    with pytest.raises(LogValidationError, match="UTC offset"):
        parse_scenario({"scenario_id": "bad", "events": [raw]})


def test_non_utc_timestamp_is_rejected():
    raw = _raw_event()
    raw["occurred_at"] = "2026-10-27T02:00:00-07:00"

    with pytest.raises(LogValidationError, match="must be UTC"):
        parse_scenario({"scenario_id": "bad", "events": [raw]})


def test_observed_before_occurred_is_rejected():
    with pytest.raises(LogValidationError, match="earlier than occurred_at"):
        make_event(occurred_at=utc(10, 0), observed_at=utc(9, 59))


def test_zulu_and_explicit_offset_are_the_same_instant():
    from_z = make_event(occurred_at="2026-10-27T10:00:00Z", observed_at="2026-10-27T10:00:00Z")
    from_offset = make_event(
        occurred_at="2026-10-27T10:00:00+00:00",
        observed_at="2026-10-27T10:00:00+00:00",
    )

    assert from_z.occurred_at == from_offset.occurred_at == utc(10, 0)


def _raw_event() -> dict[str, object]:
    return {
        "event_id": "evt_followup_sent",
        "campaign_id": "camp_synthetic",
        "lead_id": "lead_synthetic",
        "type": "FOLLOWUP_SENT",
        "occurred_at": "2026-10-27T10:00:00Z",
        "observed_at": "2026-10-27T10:00:00Z",
    }
