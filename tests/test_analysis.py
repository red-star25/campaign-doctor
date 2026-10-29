import itertools

import pytest

from campaign_doctor.analysis import (
    DELAYED_REPLY_SUMMARY,
    STOPPED_SUMMARY,
    STOPPED_WITH_OPEN_WINDOW_SUMMARY,
    analyze,
    build_report,
)
from campaign_doctor.models import EventType, LogValidationError, SequenceState, load_scenario
from tests.support import DELAYED_REPLY, make_event, utc


def test_delayed_reply_is_suspicious():
    events = load_scenario(DELAYED_REPLY).events
    diagnosis = analyze(events)

    assert diagnosis.pattern_matched is True
    assert diagnosis.summary == DELAYED_REPLY_SUMMARY
    assert "consistent with delayed event delivery" in diagnosis.summary
    assert len(diagnosis.findings) == 1
    finding = diagnosis.findings[0]
    assert finding.followup.event_id == "evt_followup_sent"
    assert finding.reply.event_id == "evt_prospect_reply"
    assert finding.known_state_at_send is SequenceState.ACTIVE
    assert diagnosis.sends_after_known_stop == ()
    assert diagnosis.certainty.startswith("Treat this as a suspicion")
    assert "confirmed root cause" in diagnosis.certainty


def test_reply_after_followup_is_not_flagged():
    # The prospect replied at 10:30. The 10:00 follow-up was earlier, so
    # this is a normal follow-up from the point of view of this check.
    events = (
        make_event(
            event_id="initial",
            type=EventType.INITIAL_EMAIL_SENT,
            occurred_at=utc(9, 0),
            observed_at=utc(9, 0),
        ),
        make_event(
            event_id="followup",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
        make_event(
            event_id="reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(10, 30),
            observed_at=utc(10, 31),
        ),
    )

    diagnosis = analyze(events)

    assert diagnosis.pattern_matched is False
    assert diagnosis.findings == ()


def test_reply_already_processed_before_the_send_is_not_delayed_delivery():
    events = (
        make_event(
            event_id="reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(9, 50),
            observed_at=utc(9, 55),
        ),
        make_event(
            event_id="followup",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
    )

    diagnosis = analyze(events)
    steps = {step.event.event_id: step for step in build_report(events).steps}

    assert diagnosis.pattern_matched is False
    assert diagnosis.findings == ()
    assert diagnosis.summary == STOPPED_SUMMARY
    assert len(diagnosis.sends_after_known_stop) == 1
    stopped = diagnosis.sends_after_known_stop[0]
    assert stopped.followup.event_id == "followup"
    assert stopped.known_state_at_send is SequenceState.STOPPED
    assert [reply.event_id for reply in stopped.processed_replies] == ["reply"]
    assert stopped.unprocessed_replies == ()
    assert steps["followup"].known_state_before is SequenceState.STOPPED


def test_file_order_does_not_change_the_diagnosis():
    events = load_scenario(DELAYED_REPLY).events
    baseline = build_report(events)

    for shuffled in itertools.permutations(events):
        assert build_report(shuffled) == baseline
        assert analyze(shuffled) == baseline.diagnosis


def test_send_at_the_reply_observation_instant_is_not_flagged():
    events = (
        make_event(
            event_id="reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(9, 58),
            observed_at=utc(10, 0),
        ),
        make_event(
            event_id="followup",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
    )

    assert analyze(events).pattern_matched is False


def test_simultaneous_reply_and_send_are_not_flagged():
    events = (
        make_event(
            event_id="reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 5),
        ),
        make_event(
            event_id="followup",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
    )

    assert analyze(events).pattern_matched is False


def test_another_leads_reply_does_not_flag_this_followup():
    events = (
        make_event(
            event_id="reply",
            lead_id="lead_other",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(9, 58),
            observed_at=utc(10, 2),
        ),
        make_event(
            event_id="followup",
            lead_id="lead_synthetic",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
    )

    assert analyze(events).pattern_matched is False


def test_open_reply_window_does_not_explain_a_send_after_a_known_stop():
    # 09:51 the first reply is processed and the sequence stops.
    # 10:00 the follow-up goes out anyway.
    # 09:58/10:02 the second reply overlaps that send, and that overlap
    # stays in the report without becoming the delayed-reply diagnosis.
    events = (
        make_event(
            event_id="initial",
            type=EventType.INITIAL_EMAIL_SENT,
            occurred_at=utc(9, 0),
            observed_at=utc(9, 0),
        ),
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
    )

    diagnosis = analyze(events)

    assert diagnosis.pattern_matched is False
    assert diagnosis.findings == ()
    assert diagnosis.summary == STOPPED_WITH_OPEN_WINDOW_SUMMARY
    assert diagnosis.summary != DELAYED_REPLY_SUMMARY
    assert all(
        finding.known_state_at_send is SequenceState.ACTIVE for finding in diagnosis.findings
    )
    assert len(diagnosis.sends_after_known_stop) == 1
    send = diagnosis.sends_after_known_stop[0]
    assert send.followup.event_id == "followup"
    assert send.known_state_at_send is SequenceState.STOPPED
    assert [reply.event_id for reply in send.processed_replies] == ["early_reply"]
    assert [reply.event_id for reply in send.unprocessed_replies] == ["later_reply"]
    assert build_report(events).diagnosis == diagnosis


def test_active_delay_and_later_stopped_send_are_both_kept():
    events = (
        make_event(
            event_id="reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(9, 40),
            observed_at=utc(9, 55),
        ),
        make_event(
            event_id="followup_while_active",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(9, 45),
            observed_at=utc(9, 45),
        ),
        make_event(
            event_id="followup_after_stop",
            type=EventType.FOLLOWUP_SENT,
            occurred_at=utc(10, 0),
            observed_at=utc(10, 0),
        ),
    )

    diagnosis = analyze(events)

    assert diagnosis.pattern_matched is True
    assert [finding.followup.event_id for finding in diagnosis.findings] == ["followup_while_active"]
    assert diagnosis.findings[0].known_state_at_send is SequenceState.ACTIVE
    assert [send.followup.event_id for send in diagnosis.sends_after_known_stop] == [
        "followup_after_stop"
    ]
    assert diagnosis.sends_after_known_stop[0].unprocessed_replies == ()
    assert DELAYED_REPLY_SUMMARY in diagnosis.summary
    assert "STOPPED" in diagnosis.summary


def test_duplicate_event_ids_are_rejected_by_the_report():
    followup = make_event(
        event_id="followup",
        type=EventType.FOLLOWUP_SENT,
        occurred_at=utc(10, 0),
        observed_at=utc(10, 0),
    )
    reply = make_event(
        event_id="reply",
        type=EventType.PROSPECT_REPLIED,
        occurred_at=utc(9, 58),
        observed_at=utc(10, 2),
    )
    # The same follow-up object twice would otherwise match the reply twice.
    duplicated = (reply, followup, followup)

    with pytest.raises(LogValidationError, match="duplicate event_id: followup"):
        build_report(duplicated)
    with pytest.raises(LogValidationError, match="duplicate event_id: followup"):
        analyze(duplicated)
