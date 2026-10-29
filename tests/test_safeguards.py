import pytest

from campaign_doctor.analysis import DELAYED_REPLY_SUMMARY, build_report
from campaign_doctor.models import EventType, LogValidationError, SequenceState, load_scenario
from campaign_doctor.safeguards import (
    BaselineOutcome,
    DecisionLedger,
    ProviderCheckStatus,
    ProviderFailure,
    ProviderFailureKind,
    ProviderReplyRecord,
    ScriptedReplyProvider,
    SendDecision,
    SendRequest,
    compare_safeguards,
    decide_followup,
    describe_unguarded,
    records_visible_at_occurrence,
    request_for_followup,
)
from tests.support import DELAYED_REPLY, make_event, utc


def test_provider_confirmed_reply_cancels_the_followup():
    provider = ScriptedReplyProvider(
        (
            ProviderReplyRecord(
                campaign_id="camp_synthetic",
                lead_id="lead_synthetic",
                reply_event_id="reply",
                occurred_at=utc(9, 58),
                visible_at=utc(9, 58),
            ),
        )
    )
    ledger = DecisionLedger()
    decision = decide_followup(_request(), (), provider, ledger)
    repeated = decide_followup(_request(), (), provider, ledger)

    assert decision.decision is SendDecision.CANCEL
    assert decision.known_state is SequenceState.ACTIVE
    assert decision.provider_result is not None
    assert decision.provider_result.status is ProviderCheckStatus.REPLY_CONFIRMED
    assert decision.simulated_send_recorded is False
    assert "No email was sent" in decision.explanation
    assert provider.calls == 1
    assert ledger.simulated_send_count == 0
    assert repeated.from_cache is True
    assert repeated.decision is SendDecision.CANCEL
    assert repeated.simulated_send_recorded is False


def test_no_visible_reply_allows_one_simulated_send():
    provider = ScriptedReplyProvider(
        (
            ProviderReplyRecord(
                campaign_id="camp_synthetic",
                lead_id="someone_else",
                reply_event_id="other_reply",
                occurred_at=utc(9, 58),
                visible_at=utc(9, 58),
            ),
        )
    )
    ledger = DecisionLedger()

    decision = decide_followup(_request(), (), provider, ledger)

    assert decision.decision is SendDecision.ALLOW
    assert decision.known_state is SequenceState.ACTIVE
    assert decision.provider_result is not None
    assert decision.provider_result.status is ProviderCheckStatus.NO_REPLY_FOUND
    assert decision.simulated_send_recorded is True
    assert ledger.simulated_send_count == 1
    assert "No message left this program" in decision.explanation


def test_stopped_sequence_cancels_before_the_provider_is_asked():
    events = (
        make_event(
            event_id="early_reply",
            type=EventType.PROSPECT_REPLIED,
            occurred_at=utc(9, 50),
            observed_at=utc(9, 51),
        ),
    )
    provider = ScriptedReplyProvider(records_visible_at_occurrence(events))
    ledger = DecisionLedger()

    decision = decide_followup(_request(decision_time=utc(10, 0)), events, provider, ledger)

    assert decision.decision is SendDecision.CANCEL
    assert decision.known_state is SequenceState.STOPPED
    assert decision.provider_result is None
    assert provider.calls == 0
    assert decision.simulated_send_recorded is False
    assert ledger.simulated_send_count == 0
    assert "No email was sent" in decision.explanation


def test_provider_timeout_defers_without_a_send():
    provider = _failing_provider(ProviderFailureKind.TIMEOUT, "timed out")
    ledger = DecisionLedger()

    decision = decide_followup(_request(), (), provider, ledger)

    assert decision.decision is SendDecision.DEFER
    assert decision.provider_result is not None
    assert decision.provider_result.status is ProviderCheckStatus.UNAVAILABLE
    assert decision.provider_result.failure_kind is ProviderFailureKind.TIMEOUT
    assert decision.simulated_send_recorded is False
    assert ledger.simulated_send_count == 0
    assert "timed out" in decision.explanation
    assert "No email was sent" in decision.explanation


def test_provider_error_defers_without_a_send():
    provider = _failing_provider(ProviderFailureKind.ERROR, "provider error")
    ledger = DecisionLedger()

    decision = decide_followup(_request(), (), provider, ledger)

    assert decision.decision is SendDecision.DEFER
    assert decision.provider_result is not None
    assert decision.provider_result.failure_kind is ProviderFailureKind.ERROR
    assert decision.simulated_send_recorded is False
    assert ledger.simulated_send_count == 0
    assert "error" in decision.explanation
    assert "No email was sent" in decision.explanation


def test_stale_provider_view_does_not_reveal_an_invisible_reply():
    record = ProviderReplyRecord(
        campaign_id="camp_synthetic",
        lead_id="lead_synthetic",
        reply_event_id="reply",
        occurred_at=utc(9, 58),
        visible_at=utc(10, 5),
    )
    provider = ScriptedReplyProvider((record,))
    request = _request(decision_time=utc(10, 0))

    decision = decide_followup(request, (), provider, DecisionLedger())

    assert record.occurred_at < request.decision_time < record.visible_at
    assert decision.provider_result is not None
    assert decision.provider_result.status is ProviderCheckStatus.NO_REPLY_FOUND
    assert decision.decision is SendDecision.ALLOW
    assert "behind" in decision.explanation


def test_reply_that_has_not_happened_yet_stays_invisible():
    record = ProviderReplyRecord(
        campaign_id="camp_synthetic",
        lead_id="lead_synthetic",
        reply_event_id="later_reply",
        occurred_at=utc(10, 30),
        visible_at=utc(10, 30),
    )
    decision = decide_followup(
        _request(decision_time=utc(10, 0)),
        (),
        ScriptedReplyProvider((record,)),
        DecisionLedger(),
    )

    assert decision.provider_result is not None
    assert decision.provider_result.status is ProviderCheckStatus.NO_REPLY_FOUND
    assert decision.decision is SendDecision.ALLOW


def test_repeated_allow_records_only_one_simulated_send():
    provider = ScriptedReplyProvider(())
    ledger = DecisionLedger()
    request = _request()

    first = decide_followup(request, (), provider, ledger)
    second = decide_followup(request, (), provider, ledger)

    assert first.decision is SendDecision.ALLOW
    assert second.decision is SendDecision.ALLOW
    assert first.simulated_send_recorded is True
    assert second.from_cache is True
    assert second.simulated_send_recorded is False
    assert provider.calls == 1
    assert ledger.simulated_send_count == 1
    assert "no additional simulated send" in second.explanation


def test_delayed_reply_scenario_unguarded_sends_and_guarded_cancels():
    events = load_scenario(DELAYED_REPLY).events
    followup = next(event for event in events if event.type is EventType.FOLLOWUP_SENT)
    reply = next(event for event in events if event.type is EventType.PROSPECT_REPLIED)
    records = records_visible_at_occurrence(events)
    provider = ScriptedReplyProvider(records)
    ledger = DecisionLedger()

    comparison = compare_safeguards(events, request_for_followup(followup), provider, ledger)

    assert records[0].visible_at == reply.occurred_at
    assert reply.observed_at > followup.occurred_at
    assert comparison.unguarded.outcome is BaselineOutcome.SENT
    assert comparison.unguarded.known_state is SequenceState.ACTIVE
    assert comparison.guarded.decision_time == followup.occurred_at
    assert comparison.guarded.known_state is SequenceState.ACTIVE
    assert comparison.guarded.provider_result is not None
    assert comparison.guarded.provider_result.status is ProviderCheckStatus.REPLY_CONFIRMED
    assert comparison.guarded.decision is SendDecision.CANCEL
    assert comparison.guarded.simulated_send_recorded is False
    assert "No email was sent" in comparison.guarded.explanation
    assert ledger.simulated_send_count == 0
    assert any("does not guarantee" in limit for limit in comparison.limits)


def test_defer_retry_allows_once_and_then_stays_fixed():
    ledger = DecisionLedger()
    timed_out = ScriptedReplyProvider(failure=ProviderFailure(ProviderFailureKind.TIMEOUT, "timeout"))
    deferred = decide_followup(_request(), (), timed_out, ledger)
    assert deferred.decision is SendDecision.DEFER
    assert ledger.simulated_send_count == 0

    recovered = ScriptedReplyProvider(())
    allowed = decide_followup(_request(decision_time=utc(10, 5)), (), recovered, ledger)
    assert allowed.decision is SendDecision.ALLOW
    assert allowed.simulated_send_recorded is True
    assert allowed.decision_time == utc(10, 5)
    assert recovered.calls == 1
    assert ledger.simulated_send_count == 1

    again = decide_followup(_request(decision_time=utc(10, 6)), (), recovered, ledger)
    assert again.from_cache is True
    assert again.decision is SendDecision.ALLOW
    assert again.simulated_send_recorded is False
    assert recovered.calls == 1
    assert ledger.simulated_send_count == 1


def test_allow_stays_terminal_at_a_later_decision_time():
    ledger = DecisionLedger()
    first_provider = ScriptedReplyProvider(())
    first = decide_followup(_request(), (), first_provider, ledger)
    assert first.decision is SendDecision.ALLOW

    later_provider = ScriptedReplyProvider(
        (
            ProviderReplyRecord(
                campaign_id="camp_synthetic",
                lead_id="lead_synthetic",
                reply_event_id="reply",
                occurred_at=utc(9, 58),
                visible_at=utc(10, 1),
            ),
        )
    )
    second = decide_followup(_request(decision_time=utc(10, 5)), (), later_provider, ledger)

    assert second.from_cache is True
    assert second.decision is SendDecision.ALLOW
    assert second.decision_time == utc(10, 0)
    assert later_provider.calls == 0
    assert ledger.simulated_send_count == 1


def test_same_key_cannot_move_to_another_campaign():
    ledger = DecisionLedger()
    decide_followup(_request(idempotency_key="shared-key"), (), ScriptedReplyProvider(()), ledger)

    with pytest.raises(LogValidationError, match="idempotency|key|lead"):
        decide_followup(
            _request(idempotency_key="shared-key", campaign_id="other_campaign"),
            (),
            ScriptedReplyProvider(()),
            ledger,
        )


def test_baseline_ignores_a_different_send_at_the_same_time():
    other_send = make_event(
        event_id="evt_followup_sent",
        type=EventType.FOLLOWUP_SENT,
        occurred_at=utc(10, 0),
        observed_at=utc(10, 0),
    )

    baseline = describe_unguarded(
        (other_send,),
        _request(idempotency_key="different-job", decision_time=utc(10, 0)),
    )

    assert baseline.outcome is BaselineOutcome.NO_RECORDED_SEND


def test_milestone_1_delayed_reply_report_is_unchanged():
    report = build_report(load_scenario(DELAYED_REPLY).events)

    assert report.diagnosis.pattern_matched is True
    assert report.diagnosis.summary == DELAYED_REPLY_SUMMARY
    assert len(report.diagnosis.findings) == 1
    assert report.diagnosis.findings[0].known_state_at_send is SequenceState.ACTIVE
    assert report.final_states[("camp_synthetic", "lead_synthetic")] is SequenceState.STOPPED


def _request(**overrides: object) -> SendRequest:
    values: dict[str, object] = {
        "idempotency_key": "followup-1",
        "campaign_id": "camp_synthetic",
        "lead_id": "lead_synthetic",
        "decision_time": utc(10, 0),
    }
    values.update(overrides)
    return SendRequest(**values)  # type: ignore[arg-type]


def _failing_provider(kind: ProviderFailureKind, detail: str) -> ScriptedReplyProvider:
    # A visible reply is present so a timeout or error cannot be mistaken for "no reply",
    # and cannot be turned into a cancel by peeking past the failure.
    visible = ProviderReplyRecord(
        campaign_id="camp_synthetic",
        lead_id="lead_synthetic",
        reply_event_id="reply",
        occurred_at=utc(9, 58),
        visible_at=utc(9, 58),
    )
    return ScriptedReplyProvider((visible,), failure=ProviderFailure(kind, detail))
