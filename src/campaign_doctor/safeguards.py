"""Decide a simulated follow-up before it is sent.

The automation's own state only includes replies it has already processed.
A provider check can see a reply sooner, but only once that reply is visible
to the provider. A reply can have happened and still be invisible.

Nothing here sends email. CANCEL and DEFER record no send. ALLOW records
one simulated send for an idempotency key. DEFER can be checked again later
with that same key. ALLOW and CANCEL stay fixed. This does not guarantee
that a real sender could never deliver an unwanted follow-up.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import Lock
from typing import Iterator, Protocol, Sequence

from campaign_doctor.models import Event, EventType, LogValidationError, SequenceState, require_unique_event_ids
from campaign_doctor.replay import known_state_as_of

_UTC = timedelta(0)


class ProviderCheckStatus(StrEnum):
    REPLY_CONFIRMED = "REPLY_CONFIRMED"
    NO_REPLY_FOUND = "NO_REPLY_FOUND"
    UNAVAILABLE = "UNAVAILABLE"


class ProviderFailureKind(StrEnum):
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class SendDecision(StrEnum):
    ALLOW = "ALLOW"
    CANCEL = "CANCEL"
    DEFER = "DEFER"


class BaselineOutcome(StrEnum):
    """What the log shows for a follow-up when no provider check runs."""

    SENT = "SENT"
    NO_RECORDED_SEND = "NO_RECORDED_SEND"


SAFEGUARD_LIMITS = (
    "This safeguard does not guarantee that an unwanted follow-up can never go out.",
    "A reply can exist before the provider's index shows it. A check that finds nothing can still allow a follow-up the prospect has already answered.",
    "ALLOW is a decision at one instant. A reply can arrive after that check and before a real message is handed off. This simulator does not close that gap.",
    "DEFER avoids a simulated send while the provider is down. The same idempotency key can be checked again at a later time. ALLOW and CANCEL stay fixed for that key.",
    "A finished ALLOW or CANCEL is returned again without another simulated send. A DEFER retry records a send only when the new check allows one, and only once.",
    "The ledger lock lives in this process. Another process can still decide the same key on its own.",
    "The application's own state only includes replies already processed. A webhook that has not arrived yet is invisible to that check.",
    "CANCEL and DEFER do not send email. The unguarded SENT line is the follow-up already recorded in the log.",
)


@dataclass(frozen=True)
class ProviderFailure:
    kind: ProviderFailureKind
    detail: str


@dataclass(frozen=True)
class ProviderCheckResult:
    status: ProviderCheckStatus
    failure_kind: ProviderFailureKind | None = None
    detail: str = ""


@dataclass(frozen=True)
class ProviderQuery:
    """The only facts a provider check is allowed to receive."""

    campaign_id: str
    lead_id: str
    as_of: datetime


@dataclass(frozen=True)
class ProviderReplyRecord:
    """One reply the provider might show, once `visible_at` has arrived.

    `occurred_at` is when the prospect replied. `visible_at` is when this
    provider's index would include it. Those can differ. The automation's
    webhook time is not stored here.
    """

    campaign_id: str
    lead_id: str
    reply_event_id: str
    occurred_at: datetime
    visible_at: datetime

    def __post_init__(self) -> None:
        occurred_at = _as_utc(self.occurred_at, "occurred_at")
        visible_at = _as_utc(self.visible_at, "visible_at")
        if visible_at < occurred_at:
            raise LogValidationError("visible_at cannot be earlier than occurred_at")
        object.__setattr__(self, "campaign_id", _token(self.campaign_id, "campaign_id"))
        object.__setattr__(self, "lead_id", _token(self.lead_id, "lead_id"))
        object.__setattr__(self, "reply_event_id", _token(self.reply_event_id, "reply_event_id"))
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "visible_at", visible_at)


@dataclass(frozen=True)
class SendRequest:
    idempotency_key: str
    campaign_id: str
    lead_id: str
    decision_time: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", _token(self.idempotency_key, "idempotency_key"))
        object.__setattr__(self, "campaign_id", _token(self.campaign_id, "campaign_id"))
        object.__setattr__(self, "lead_id", _token(self.lead_id, "lead_id"))
        object.__setattr__(self, "decision_time", _as_utc(self.decision_time, "decision_time"))


@dataclass(frozen=True)
class PreSendDecision:
    idempotency_key: str
    decision_time: datetime
    known_state: SequenceState
    provider_result: ProviderCheckResult | None
    decision: SendDecision
    explanation: str
    from_cache: bool = False
    simulated_send_recorded: bool = False


@dataclass(frozen=True)
class UnguardedOutcome:
    decision_time: datetime
    known_state: SequenceState
    outcome: BaselineOutcome
    explanation: str


@dataclass(frozen=True)
class SafeguardComparison:
    unguarded: UnguardedOutcome
    guarded: PreSendDecision
    limits: tuple[str, ...]


class ReplyProvider(Protocol):
    def check_for_reply(self, query: ProviderQuery) -> ProviderCheckResult:
        """Report what is visible at `query.as_of`, and nothing later."""


class ScriptedReplyProvider:
    """Deterministic stand-in. It never sees the automation's event log."""

    def __init__(
        self,
        records: Sequence[ProviderReplyRecord] = (),
        *,
        failure: ProviderFailure | None = None,
    ) -> None:
        self._records = tuple(records)
        self._failure = failure
        self._call_lock = Lock()
        self.calls = 0

    def check_for_reply(self, query: ProviderQuery) -> ProviderCheckResult:
        with self._call_lock:
            self.calls += 1
        if self._failure is not None:
            return ProviderCheckResult(
                status=ProviderCheckStatus.UNAVAILABLE,
                failure_kind=self._failure.kind,
                detail=self._failure.detail,
            )
        visible = [record for record in self._records if _is_visible(record, query)]
        if not visible:
            return ProviderCheckResult(
                status=ProviderCheckStatus.NO_REPLY_FOUND,
                detail="no reply visible at decision time",
            )
        first = min(visible, key=lambda record: (record.visible_at, record.reply_event_id))
        return ProviderCheckResult(
            status=ProviderCheckStatus.REPLY_CONFIRMED,
            detail=f"reply {first.reply_event_id} visible",
        )


@dataclass(frozen=True)
class _OperationRecord:
    """A key belongs to one campaign, one lead, and one logical send.

    `decision_time` lives on the decision, not here. A retry may use a later
    clock without becoming a different operation.
    """

    campaign_id: str
    lead_id: str
    decision: PreSendDecision


class DecisionLedger:
    """In-process memory of one decision per idempotency key.

    ALLOW and CANCEL are kept. DEFER is replaced when the same operation is
    checked again. A threading lock per key stops two workers in this process
    from both passing the empty-cache check.
    """

    def __init__(self) -> None:
        self._map_lock = Lock()
        self._key_locks: dict[str, Lock] = {}
        self._records: dict[str, _OperationRecord] = {}

    @contextmanager
    def hold(self, idempotency_key: str) -> Iterator[None]:
        """Hold the lock for one key across the check and the write."""
        key_lock = self._lock_for(idempotency_key)
        with key_lock:
            yield

    def get(self, idempotency_key: str) -> PreSendDecision | None:
        record = self._lookup(idempotency_key)
        if record is None:
            return None
        return record.decision

    def _lock_for(self, idempotency_key: str) -> Lock:
        with self._map_lock:
            key_lock = self._key_locks.get(idempotency_key)
            if key_lock is None:
                key_lock = Lock()
                self._key_locks[idempotency_key] = key_lock
            return key_lock

    def _lookup(self, idempotency_key: str) -> _OperationRecord | None:
        with self._map_lock:
            return self._records.get(idempotency_key)

    def _save(self, campaign_id: str, lead_id: str, decision: PreSendDecision) -> None:
        with self._map_lock:
            current = self._records.get(decision.idempotency_key)
            if current is not None and (
                current.campaign_id != campaign_id or current.lead_id != lead_id
            ):
                raise LogValidationError(
                    f"idempotency key {decision.idempotency_key} is already bound "
                    f"to lead {current.lead_id} in campaign {current.campaign_id}"
                )
            if current is not None and current.decision.decision is not SendDecision.DEFER:
                raise LogValidationError(
                    f"idempotency key {decision.idempotency_key} already has a final decision"
                )
            self._records[decision.idempotency_key] = _OperationRecord(
                campaign_id=campaign_id,
                lead_id=lead_id,
                decision=decision,
            )

    @property
    def simulated_send_count(self) -> int:
        with self._map_lock:
            return sum(
                1
                for record in self._records.values()
                if record.decision.simulated_send_recorded
            )


def records_visible_at_occurrence(events: Sequence[Event]) -> tuple[ProviderReplyRecord, ...]:
    """Provider rows for a demo where the mailbox sees a reply when it happens.

    Visibility is `occurred_at`. The webhook's `observed_at` is intentionally
    left out, because that is when our app processed the reply, not when the
    provider could show it.
    """
    records: list[ProviderReplyRecord] = []
    for event in events:
        if event.type is not EventType.PROSPECT_REPLIED:
            continue
        records.append(
            ProviderReplyRecord(
                campaign_id=event.campaign_id,
                lead_id=event.lead_id,
                reply_event_id=event.event_id,
                occurred_at=event.occurred_at,
                visible_at=event.occurred_at,
            )
        )
    return tuple(records)


def request_for_followup(event: Event) -> SendRequest:
    """One simulated request for one recorded follow-up. The event id is the key."""
    if event.type is not EventType.FOLLOWUP_SENT:
        raise LogValidationError("request_for_followup expects a FOLLOWUP_SENT event")
    return SendRequest(
        idempotency_key=event.event_id,
        campaign_id=event.campaign_id,
        lead_id=event.lead_id,
        decision_time=event.occurred_at,
    )


def decide_followup(
    request: SendRequest,
    events: Sequence[Event],
    provider: ReplyProvider,
    ledger: DecisionLedger,
) -> PreSendDecision:
    """Choose ALLOW, CANCEL, or DEFER using only facts available at decision time.

    The key's lock is held for the whole check. A second worker for that key
    waits, then sees the stored ALLOW or CANCEL instead of starting another one.
    """
    with ledger.hold(request.idempotency_key):
        existing = ledger._lookup(request.idempotency_key)
        if existing is not None:
            _require_same_operation(existing, request)
            if existing.decision.decision is not SendDecision.DEFER:
                return _as_repeat(existing.decision)

        events = require_unique_event_ids(events)
        known_state = known_state_as_of(
            events,
            request.campaign_id,
            request.lead_id,
            request.decision_time,
        )
        if known_state is SequenceState.STOPPED:
            decision = _stopped_decision(request, known_state)
        else:
            result = provider.check_for_reply(
                ProviderQuery(
                    campaign_id=request.campaign_id,
                    lead_id=request.lead_id,
                    as_of=request.decision_time,
                )
            )
            kind, explanation, recorded = _decision_from_provider(result, request.decision_time)
            if existing is not None:
                explanation = f"Rechecked after an earlier deferral. {explanation}"
            decision = PreSendDecision(
                idempotency_key=request.idempotency_key,
                decision_time=request.decision_time,
                known_state=known_state,
                provider_result=result,
                decision=kind,
                explanation=explanation,
                from_cache=False,
                simulated_send_recorded=recorded,
            )
        ledger._save(request.campaign_id, request.lead_id, decision)
        return decision


def describe_unguarded(events: Sequence[Event], request: SendRequest) -> UnguardedOutcome:
    """Describe the follow-up the log already recorded. No provider is asked."""
    events = require_unique_event_ids(events)
    known_state = known_state_as_of(
        events,
        request.campaign_id,
        request.lead_id,
        request.decision_time,
    )
    recorded = _recorded_followup(events, request)
    clock = _format_utc(request.decision_time)
    if recorded is None:
        return UnguardedOutcome(
            decision_time=request.decision_time,
            known_state=known_state,
            outcome=BaselineOutcome.NO_RECORDED_SEND,
            explanation=(
                f"Unguarded path at {clock}: no follow-up was recorded at this decision time. "
                f"Known state was {known_state.value}."
            ),
        )
    return UnguardedOutcome(
        decision_time=request.decision_time,
        known_state=known_state,
        outcome=BaselineOutcome.SENT,
        explanation=(
            f"Unguarded path at {clock}: the follow-up is the one recorded in the log. "
            f"Known state was {known_state.value}. No provider check ran. "
            "This line is not a new simulated send."
        ),
    )


def compare_safeguards(
    events: Sequence[Event],
    request: SendRequest,
    provider: ReplyProvider,
    ledger: DecisionLedger | None = None,
) -> SafeguardComparison:
    """Put the recorded follow-up next to a guarded decision for the same instant."""
    events = require_unique_event_ids(events)
    if ledger is None:
        ledger = DecisionLedger()
    return SafeguardComparison(
        unguarded=describe_unguarded(events, request),
        guarded=decide_followup(request, events, provider, ledger),
        limits=SAFEGUARD_LIMITS,
    )


def _stopped_decision(request: SendRequest, known_state: SequenceState) -> PreSendDecision:
    clock = _format_utc(request.decision_time)
    return PreSendDecision(
        idempotency_key=request.idempotency_key,
        decision_time=request.decision_time,
        known_state=known_state,
        provider_result=None,
        decision=SendDecision.CANCEL,
        explanation=(
            f"Known state was STOPPED at {clock}, so the follow-up was cancelled "
            "before a provider check. No email was sent."
        ),
        from_cache=False,
        simulated_send_recorded=False,
    )


def _decision_from_provider(
    result: ProviderCheckResult,
    decision_time: datetime,
) -> tuple[SendDecision, str, bool]:
    clock = _format_utc(decision_time)
    if result.status is ProviderCheckStatus.REPLY_CONFIRMED:
        return (
            SendDecision.CANCEL,
            (
                f"Known state was ACTIVE at {clock}. The provider confirmed a reply "
                "that was already visible. The simulated follow-up was cancelled. "
                "No email was sent."
            ),
            False,
        )
    if result.status is ProviderCheckStatus.NO_REPLY_FOUND:
        return (
            SendDecision.ALLOW,
            (
                f"Known state was ACTIVE at {clock}. The provider reported no reply "
                "visible at that time. This simulation recorded one send. "
                "No message left this program. A reply can already exist if the provider's view is behind."
            ),
            True,
        )
    if result.failure_kind is ProviderFailureKind.TIMEOUT:
        return (
            SendDecision.DEFER,
            (
                f"Known state was ACTIVE at {clock}. The provider check timed out. "
                "The simulated follow-up was deferred. No email was sent. "
                "The same idempotency key can be checked again at a later time."
            ),
            False,
        )
    if result.failure_kind is ProviderFailureKind.ERROR:
        return (
            SendDecision.DEFER,
            (
                f"Known state was ACTIVE at {clock}. The provider check returned an error. "
                "The simulated follow-up was deferred. No email was sent. "
                "The same idempotency key can be checked again at a later time."
            ),
            False,
        )
    return (
        SendDecision.DEFER,
        (
            f"Known state was ACTIVE at {clock}. The provider check was unavailable. "
            "The simulated follow-up was deferred. No email was sent. "
            "The same idempotency key can be checked again at a later time."
        ),
        False,
    )


def _as_repeat(decision: PreSendDecision) -> PreSendDecision:
    return replace(
        decision,
        from_cache=True,
        simulated_send_recorded=False,
        explanation=(
            decision.explanation
            + " Same idempotency key: the stored decision was returned, "
            "and no additional simulated send was recorded."
        ),
    )


def _require_same_operation(record: _OperationRecord, request: SendRequest) -> None:
    if record.campaign_id == request.campaign_id and record.lead_id == request.lead_id:
        return
    raise LogValidationError(
        f"idempotency key {request.idempotency_key} is already bound "
        f"to lead {record.lead_id} in campaign {record.campaign_id}"
    )


def _recorded_followup(events: Sequence[Event], request: SendRequest) -> Event | None:
    """Match a logged follow-up only when id, campaign, and lead all agree.

    A shared event id on another lead is not this send. A shared timestamp
    is not enough either: the key names the operation.
    """
    matches = [
        event
        for event in events
        if event.type is EventType.FOLLOWUP_SENT
        and event.event_id == request.idempotency_key
        and event.campaign_id == request.campaign_id
        and event.lead_id == request.lead_id
    ]
    return matches[0] if matches else None


def _is_visible(record: ProviderReplyRecord, query: ProviderQuery) -> bool:
    """A reply is visible only if it has already happened and the index shows it."""
    return (
        record.campaign_id == query.campaign_id
        and record.lead_id == query.lead_id
        and record.occurred_at <= query.as_of
        and record.visible_at <= query.as_of
    )


def _as_utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise LogValidationError(f"{field} must be a UTC datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LogValidationError(f"{field} must include a UTC offset")
    if value.utcoffset() != _UTC:
        raise LogValidationError(f"{field} must be UTC")
    return value.astimezone(timezone.utc)


def _token(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LogValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _format_utc(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text
