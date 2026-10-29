from campaign_doctor.models import EventType, SequenceState, load_scenario
from campaign_doctor.replay import occurrence_timeline, replay
from tests.support import DELAYED_REPLY, make_event, utc


def test_occurrence_order_differs_from_observation_order():
    events = load_scenario(DELAYED_REPLY).events

    occurred = [event.event_id for event in occurrence_timeline(events)]
    observed = [step.event.event_id for step in replay(events).steps]

    assert occurred == [
        "evt_initial_email",
        "evt_prospect_reply",
        "evt_followup_sent",
    ]
    assert observed == [
        "evt_initial_email",
        "evt_followup_sent",
        "evt_prospect_reply",
    ]
    assert occurred != observed


def test_reply_stops_the_sequence_only_when_it_is_observed():
    events = load_scenario(DELAYED_REPLY).events
    result = replay(events)
    steps = {step.event.event_id: step for step in result.steps}

    followup = steps["evt_followup_sent"]
    reply = steps["evt_prospect_reply"]
    initial = steps["evt_initial_email"]

    assert initial.known_state_before is SequenceState.ACTIVE
    assert initial.known_state_after is SequenceState.ACTIVE
    assert followup.known_state_before is SequenceState.ACTIVE
    assert followup.known_state_after is SequenceState.ACTIVE
    assert reply.known_state_before is SequenceState.ACTIVE
    assert reply.known_state_after is SequenceState.STOPPED
    assert result.state_by_lead[("camp_synthetic", "lead_synthetic")] is SequenceState.STOPPED


def test_send_events_do_not_change_known_state():
    events = (
        make_event(event_id="initial", type=EventType.INITIAL_EMAIL_SENT, occurred_at=utc(9, 0), observed_at=utc(9, 0)),
        make_event(event_id="followup", type=EventType.FOLLOWUP_SENT, occurred_at=utc(10, 0), observed_at=utc(10, 0)),
    )

    result = replay(events)

    assert all(step.known_state_after is SequenceState.ACTIVE for step in result.steps)
    assert result.state_by_lead[("camp_synthetic", "lead_synthetic")] is SequenceState.ACTIVE


def test_out_of_order_events_replay_in_observed_order():
    events = load_scenario(DELAYED_REPLY).events
    reversed_events = tuple(reversed(events))

    assert replay(reversed_events).steps == replay(events).steps
    assert occurrence_timeline(reversed_events) == occurrence_timeline(events)


def test_equal_observed_times_tie_break_on_event_id():
    # Same processed time. Input lists the later id first. Replay still
    # walks event_id order, so the reply is applied before the initial send.
    initial = make_event(
        event_id="b_initial",
        type=EventType.INITIAL_EMAIL_SENT,
        occurred_at=utc(9, 0),
        observed_at=utc(10, 0),
    )
    reply = make_event(
        event_id="a_reply",
        type=EventType.PROSPECT_REPLIED,
        occurred_at=utc(9, 30),
        observed_at=utc(10, 0),
    )

    forward = replay((initial, reply)).steps
    backward = replay((reply, initial)).steps

    assert [step.event.event_id for step in forward] == ["a_reply", "b_initial"]
    assert forward == backward
    assert forward[0].known_state_before is SequenceState.ACTIVE
    assert forward[0].known_state_after is SequenceState.STOPPED
    assert forward[1].known_state_before is SequenceState.STOPPED
    assert forward[1].known_state_after is SequenceState.STOPPED
