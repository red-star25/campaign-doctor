from campaign_doctor.analysis import DELAYED_REPLY_SUMMARY
from campaign_doctor.cli import main, render
from campaign_doctor.models import EventType, Scenario, load_scenario
from tests.support import DELAYED_REPLY, make_event, utc


def test_cli_prints_both_timelines_and_the_diagnosis(capsys):
    exit_code = main([str(DELAYED_REPLY)])
    out = capsys.readouterr().out

    occurrence, observation = _sections(out)
    assert exit_code == 0
    assert occurrence.index("evt_prospect_reply") < occurrence.index("evt_followup_sent")
    assert observation.index("evt_followup_sent") < observation.index("evt_prospect_reply")
    assert "ACTIVE -> ACTIVE" in observation
    assert "ACTIVE -> STOPPED" in observation
    assert DELAYED_REPLY_SUMMARY in out
    assert "known state at send time: ACTIVE" in out
    assert "synthetic" in out.lower()


def test_render_matches_the_cli_story():
    text = render(load_scenario(DELAYED_REPLY))
    occurrence, observation = _sections(text)

    assert "Occurrence order" in text
    assert "Observation order" in text
    assert occurrence.index("evt_prospect_reply") < occurrence.index("evt_followup_sent")
    assert observation.index("evt_followup_sent") < observation.index("evt_prospect_reply")


def test_cli_rejects_a_malformed_timestamp(tmp_path, capsys):
    scenario = tmp_path / "broken.json"
    scenario.write_text(
        """
        {
          "scenario_id": "broken",
          "events": [
            {
              "event_id": "evt_followup_sent",
              "campaign_id": "camp_synthetic",
              "lead_id": "lead_synthetic",
              "type": "FOLLOWUP_SENT",
              "occurred_at": "yesterday",
              "observed_at": "2026-10-27T10:00:00Z"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    exit_code = main([str(scenario)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "ISO-8601" in captured.err


def test_render_keeps_a_late_reply_separate_from_a_send_after_stop():
    scenario = Scenario(
        scenario_id="already_stopped",
        description="",
        events=(
            make_event(
                event_id="early_reply",
                type=EventType.PROSPECT_REPLIED,
                occurred_at=utc(9, 50),
                observed_at=utc(9, 51),
            ),
            make_event(
                event_id="later_reply",
                type=EventType.PROSPECT_REPLIED,
                occurred_at=utc(9, 58),
                observed_at=utc(10, 2),
            ),
            make_event(
                event_id="followup",
                type=EventType.FOLLOWUP_SENT,
                occurred_at=utc(10, 0),
                observed_at=utc(10, 0),
            ),
        ),
    )

    text = render(scenario)

    assert DELAYED_REPLY_SUMMARY not in text
    assert "known state at send time: STOPPED" in text
    assert "early_reply" in text
    assert "later_reply" in text
    assert "replies already processed" in text
    assert "replies still unprocessed at send time" in text


def test_cli_compares_unguarded_send_with_guarded_cancel():
    text = render(load_scenario(DELAYED_REPLY))
    safeguard = text.split("Safeguard simulation:", 1)[1]
    unguarded = safeguard.split("Unguarded:", 1)[1].split("Guarded:", 1)[0]
    guarded = safeguard.split("Guarded:", 1)[1].split("Limits of the safeguard:", 1)[0]

    assert "outcome: SENT" in unguarded
    assert "provider_check: not run" in unguarded
    assert "decision: CANCEL" in guarded
    assert "provider_check: REPLY_CONFIRMED" in guarded
    assert "known_state: ACTIVE" in guarded
    assert "No email was sent" in guarded
    assert "outcome: SENT" not in guarded
    assert "does not guarantee" in safeguard


def test_cli_usage_without_a_path(capsys):
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "usage:" in captured.err


def _sections(text: str) -> tuple[str, str]:
    occurrence = text.split("Observation order", 1)[0]
    observation = text.split("Observation order", 1)[1].split("Known state after replay:", 1)[0]
    return occurrence, observation
