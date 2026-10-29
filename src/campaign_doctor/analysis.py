"""Compare the two clocks and describe a delayed reply.

A follow-up is a delayed-reply suspicion only when two things are both true:
the send sits strictly after a reply happened and strictly before that reply
was processed, and the automation's known state at send time was still ACTIVE.

If the known state was already STOPPED, the send is a separate observation.
An unprocessed reply can still overlap that send. The overlap is recorded,
and it is not treated as the explanation for the send.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from campaign_doctor.models import Event, EventType, SequenceState, require_unique_event_ids
from campaign_doctor.replay import (
    ReplayStep,
    known_state_as_of,
    occurrence_timeline,
    replay,
)

# Kept as one sentence so the sample diagnosis stays stable for tests and the CLI.
DELAYED_REPLY_SUMMARY = (
    "The follow-up was sent after a prospect had replied, but before the reply "
    "notification was processed. This is consistent with delayed event delivery."
)

NO_MATCH_SUMMARY = (
    "No follow-up was sent after a prospect had replied and before that reply was observed."
)

STOPPED_SUMMARY = (
    "One or more follow-ups were sent after the known sequence state was already STOPPED."
)

STOPPED_WITH_OPEN_WINDOW_SUMMARY = (
    STOPPED_SUMMARY
    + " A reply notification was still unprocessed around a send."
    + " That delay is recorded separately and does not explain the send on its own."
)

MIXED_SUMMARY = (
    DELAYED_REPLY_SUMMARY
    + " A separate follow-up was sent after the known state was already STOPPED,"
    + " and that send is not explained by an unprocessed reply alone."
)

SUSPICION_CERTAINTY = (
    "Treat this as a suspicion rather than a confirmed root cause. "
    "The timing fits delayed event delivery. "
    "The log shows the gap between the reply and the notification, "
    "and it leaves the reason for that gap unexplained."
)

NO_MATCH_CERTAINTY = (
    "This log does not show the delayed-reply pattern. "
    "This check speaks only to that pattern."
)

STOPPED_CERTAINTY = (
    "The automation had already processed a reply before the send. "
    "An unprocessed reply window, when one is present, is a second timing fact."
)

DELAYED_REPLY_LIMITS = (
    "At send time the reply had not been processed, so the known sequence state could still be active.",
    "Checking the automation database at send time would miss a reply that had not arrived yet.",
    "Replaying an incident does not prevent the next one. A provider-side reply check can be late, unreachable, or rate-limited.",
    "These records are synthetic. They are not evidence of Cardinal's architecture or of a real customer incident.",
)

STOPPED_LIMITS = (
    "The automation had already processed a reply, so its known state at send time was STOPPED.",
    "Replay explains the log. It does not show that a later safeguard would have blocked the send.",
    "These records are synthetic. They are not evidence of Cardinal's architecture or of a real customer incident.",
)

OPEN_WINDOW_LIMIT = (
    "An overlapping unprocessed reply shows that a notification was late. It does not show why a send was recorded after the stop.",
)

NO_MATCH_LIMITS = (
    "A clear result here covers this delayed-reply check only.",
)

_SEPARATE_STOP_LIMIT = (
    "Sends recorded after the known state was STOPPED are a separate observation from the delayed-reply window.",
)


@dataclass(frozen=True)
class DelayedReplyFinding:
    """A follow-up sent inside an unprocessed-reply window while the sequence still looked active."""

    followup: Event
    reply: Event
    known_state_at_send: SequenceState


@dataclass(frozen=True)
class SendAfterKnownStop:
    """A follow-up recorded after the automation had already stopped the sequence.

    `processed_replies` are replies observed before the send.
    `unprocessed_replies` are replies whose real-world time is before the send
    and whose notification time is after the send. They explain a delay.
    They do not explain why the send happened after the stop.
    """

    followup: Event
    known_state_at_send: SequenceState
    processed_replies: tuple[Event, ...]
    unprocessed_replies: tuple[Event, ...]


@dataclass(frozen=True)
class Diagnosis:
    pattern_matched: bool
    summary: str
    certainty: str
    findings: tuple[DelayedReplyFinding, ...]
    limitations: tuple[str, ...]
    sends_after_known_stop: tuple[SendAfterKnownStop, ...] = ()


@dataclass(frozen=True)
class Report:
    """Occurrence order, processed order, end state, and diagnosis."""

    occurrence_order: tuple[Event, ...]
    steps: tuple[ReplayStep, ...]
    final_states: Mapping[tuple[str, str], SequenceState]
    diagnosis: Diagnosis


def analyze(events: Sequence[Event]) -> Diagnosis:
    """Describe delayed replies while active, and sends after a known stop."""
    events = require_unique_event_ids(events)
    active_findings: list[DelayedReplyFinding] = []
    stopped_sends: list[SendAfterKnownStop] = []
    grouped: dict[tuple[str, str], list[Event]] = {}
    for event in events:
        grouped.setdefault((event.campaign_id, event.lead_id), []).append(event)

    for (campaign_id, lead_id), group in grouped.items():
        replies = [event for event in group if event.type is EventType.PROSPECT_REPLIED]
        followups = [event for event in group if event.type is EventType.FOLLOWUP_SENT]
        for followup in followups:
            state = known_state_as_of(events, campaign_id, lead_id, followup.occurred_at)
            unprocessed = tuple(
                sorted(
                    (reply for reply in replies if _inside_unobserved_window(followup, reply)),
                    key=_reply_key,
                )
            )
            # A stop already on the books means this send is not "we had not
            # heard about a reply yet." Keep any overlapping late reply as
            # context, and keep it out of the delayed-reply findings.
            if state is SequenceState.STOPPED:
                processed = tuple(
                    sorted(
                        (reply for reply in replies if reply.observed_at < followup.occurred_at),
                        key=_reply_key,
                    )
                )
                stopped_sends.append(
                    SendAfterKnownStop(
                        followup=followup,
                        known_state_at_send=state,
                        processed_replies=processed,
                        unprocessed_replies=unprocessed,
                    )
                )
                continue
            for reply in unprocessed:
                active_findings.append(
                    DelayedReplyFinding(
                        followup=followup,
                        reply=reply,
                        known_state_at_send=state,
                    )
                )

    return _assemble(
        tuple(
            sorted(
                active_findings,
                key=lambda finding: (
                    finding.followup.occurred_at,
                    finding.followup.event_id,
                    finding.reply.occurred_at,
                    finding.reply.event_id,
                ),
            )
        ),
        tuple(
            sorted(
                stopped_sends,
                key=lambda send: (send.followup.occurred_at, send.followup.event_id),
            )
        ),
    )


def build_report(events: Sequence[Event]) -> Report:
    """Replay one log and attach the delayed-reply diagnosis.

    Duplicate event ids are rejected here, same as when a scenario file is parsed.
    """
    events = require_unique_event_ids(events)
    replayed = replay(events)
    return Report(
        occurrence_order=occurrence_timeline(events),
        steps=replayed.steps,
        final_states=MappingProxyType(dict(replayed.state_by_lead)),
        diagnosis=analyze(events),
    )


def _assemble(
    active: tuple[DelayedReplyFinding, ...],
    stopped: tuple[SendAfterKnownStop, ...],
) -> Diagnosis:
    if active and stopped:
        return Diagnosis(
            pattern_matched=True,
            summary=MIXED_SUMMARY,
            certainty=(
                SUSPICION_CERTAINTY
                + " Follow-ups sent after the known state was STOPPED are listed separately."
            ),
            findings=active,
            limitations=DELAYED_REPLY_LIMITS + (_SEPARATE_STOP_LIMIT,),
            sends_after_known_stop=stopped,
        )
    if active:
        return Diagnosis(
            pattern_matched=True,
            summary=DELAYED_REPLY_SUMMARY,
            certainty=SUSPICION_CERTAINTY,
            findings=active,
            limitations=DELAYED_REPLY_LIMITS,
        )
    if stopped:
        has_open_window = any(send.unprocessed_replies for send in stopped)
        limitations = STOPPED_LIMITS
        if has_open_window:
            limitations = STOPPED_LIMITS[:1] + (OPEN_WINDOW_LIMIT,) + STOPPED_LIMITS[1:]
        return Diagnosis(
            pattern_matched=False,
            summary=STOPPED_WITH_OPEN_WINDOW_SUMMARY if has_open_window else STOPPED_SUMMARY,
            certainty=STOPPED_CERTAINTY,
            findings=(),
            limitations=limitations,
            sends_after_known_stop=stopped,
        )
    return Diagnosis(
        pattern_matched=False,
        summary=NO_MATCH_SUMMARY,
        certainty=NO_MATCH_CERTAINTY,
        findings=(),
        limitations=NO_MATCH_LIMITS,
    )


def _inside_unobserved_window(followup: Event, reply: Event) -> bool:
    """True when the send sits strictly between reply-happened and reply-processed.

    Equal timestamps stay unmatched. On a boundary we cannot say the send
    was after the reply, or that it was before the reply was known.
    """
    return reply.occurred_at < followup.occurred_at < reply.observed_at


def _reply_key(event: Event) -> tuple[object, str]:
    return (event.occurred_at, event.event_id)
