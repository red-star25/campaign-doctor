"""Additional independent review checks for Milestone 2.

These tests express suggested safety properties. They are expected to fail
against the current uploaded implementation until the relevant design is fixed.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

import pytest

from campaign_doctor.models import EventType, LogValidationError
from campaign_doctor.safeguards import (
    BaselineOutcome,
    DecisionLedger,
    ProviderCheckResult,
    ProviderCheckStatus,
    ProviderFailure,
    ProviderFailureKind,
    ProviderReplyRecord,
    ScriptedReplyProvider,
    SendDecision,
    SendRequest,
    decide_followup,
    describe_unguarded,
)
from tests.support import make_event, utc


def _request(key="job-1", *, lead="lead_synthetic", time=None):
    return SendRequest(
        idempotency_key=key,
        campaign_id="camp_synthetic",
        lead_id=lead,
        decision_time=time or utc(10, 0),
    )


def test_deferred_job_can_retry_under_same_idempotency_key_after_recovery():
    """A transient DEFER should not permanently freeze the logical job."""
    ledger = DecisionLedger()
    failed = ScriptedReplyProvider(failure=ProviderFailure(ProviderFailureKind.TIMEOUT, "timeout"))
    initial = decide_followup(_request(), (), failed, ledger)
    assert initial.decision is SendDecision.DEFER

    recovered = ScriptedReplyProvider((ProviderReplyRecord(
        campaign_id="camp_synthetic", lead_id="lead_synthetic", reply_event_id="reply-1",
        occurred_at=utc(9, 58), visible_at=utc(10, 1),
    ),))
    retry = decide_followup(_request(time=utc(10, 5)), (), recovered, ledger)
    assert retry.decision is SendDecision.CANCEL, "DEFER should be retryable after recovery"
    assert recovered.calls == 1
    assert ledger.simulated_send_count == 0


def test_idempotency_key_cannot_be_reused_for_another_lead():
    """A cached decision must be tied to its original campaign/lead/job identity."""
    ledger = DecisionLedger()
    first = decide_followup(_request(key="shared-key"), (), ScriptedReplyProvider(()), ledger)
    assert first.decision is SendDecision.ALLOW
    with pytest.raises(LogValidationError, match="idempotency|key|lead"):
        decide_followup(
            _request(key="shared-key", lead="different_lead"), (),
            ScriptedReplyProvider(()), ledger,
        )


def test_baseline_does_not_count_another_leads_followup_as_ours():
    """A log lookup by event ID also needs matching campaign and lead."""
    other_lead_send = make_event(
        event_id="shared-send", type=EventType.FOLLOWUP_SENT,
        campaign_id="camp_synthetic", lead_id="another_lead",
        occurred_at=utc(10, 0), observed_at=utc(10, 0),
    )
    baseline = describe_unguarded(
        (other_lead_send,), _request(key="shared-send", lead="lead_synthetic")
    )
    assert baseline.outcome is BaselineOutcome.NO_RECORDED_SEND


def test_concurrent_duplicate_checks_do_not_raise_or_record_two_sends():
    """Two workers racing on one key should receive one consistent decision.

    Both workers begin together. The provider waits briefly to give the
    second worker a chance to try the same key. An implementation with a
    per-key lock should call the provider once, not wait for two provider calls.
    """
    start = Barrier(2, timeout=3)

    class SlowProvider:
        def __init__(self):
            self.calls = 0

        def check_for_reply(self, query):
            self.calls += 1
            sleep(0.08)
            return ProviderCheckResult(status=ProviderCheckStatus.NO_REPLY_FOUND)

    def worker():
        start.wait()
        return decide_followup(_request(), (), provider, ledger)

    ledger = DecisionLedger()
    provider = SlowProvider()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        decisions = [future.result() for future in futures]
    assert all(x.decision is SendDecision.ALLOW for x in decisions)
    assert ledger.simulated_send_count == 1
    assert provider.calls == 1
    assert sum(x.simulated_send_recorded for x in decisions) == 1
