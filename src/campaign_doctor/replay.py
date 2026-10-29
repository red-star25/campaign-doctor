"""Replay the automation's known state.

Processing order is `observed_at`, then `event_id`. A prospect reply stops
the sequence only at that moment. Send rows are outcomes already in the log.
Walking them again does not send another message.

The state on each step is what the automation believed when it processed
that row. It is not a guess about what the mail provider knew.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Sequence

from campaign_doctor.models import Event, EventType, SequenceState

LeadKey = tuple[str, str]


@dataclass(frozen=True)
class ReplayStep:
    event: Event
    known_state_before: SequenceState
    known_state_after: SequenceState


@dataclass(frozen=True)
class ReplayResult:
    steps: tuple[ReplayStep, ...]
    state_by_lead: Mapping[LeadKey, SequenceState]


def occurrence_timeline(events: Sequence[Event]) -> tuple[Event, ...]:
    """Order events by when they happened in the world."""
    return tuple(sorted(events, key=_occurred_key))


def replay(events: Sequence[Event]) -> ReplayResult:
    """Order events by when the automation processed them, and apply state."""
    state_by_lead: dict[LeadKey, SequenceState] = {}
    steps: list[ReplayStep] = []
    for event in sorted(events, key=_observed_key):
        lead = (event.campaign_id, event.lead_id)
        before = state_by_lead.get(lead, SequenceState.ACTIVE)
        after = apply_event(before, event)
        state_by_lead[lead] = after
        steps.append(
            ReplayStep(
                event=event,
                known_state_before=before,
                known_state_after=after,
            )
        )
    return ReplayResult(
        steps=tuple(steps),
        state_by_lead=MappingProxyType(dict(state_by_lead)),
    )


def known_state_as_of(
    events: Sequence[Event],
    campaign_id: str,
    lead_id: str,
    as_of: datetime,
) -> SequenceState:
    """Known state from events observed strictly before `as_of`.

    Used for "what did we believe at send time?" The send row itself is
    excluded when its observed time equals the send time. A reply still
    waiting in a webhook queue is excluded too, because it is not known yet.
    """
    state = SequenceState.ACTIVE
    prior = [
        event
        for event in events
        if event.campaign_id == campaign_id
        and event.lead_id == lead_id
        and event.observed_at < as_of
    ]
    for event in sorted(prior, key=_observed_key):
        state = apply_event(state, event)
    return state


def apply_event(state: SequenceState, event: Event) -> SequenceState:
    """Advance known state for one processed event.

    Only a processed reply stops the sequence. An initial email or a
    follow-up is evidence that a send was recorded, so the state stays
    whatever it already was.
    """
    if event.type is EventType.PROSPECT_REPLIED:
        return SequenceState.STOPPED
    return state


def _occurred_key(event: Event) -> tuple[datetime, str]:
    return (event.occurred_at, event.event_id)


def _observed_key(event: Event) -> tuple[datetime, str]:
    return (event.observed_at, event.event_id)
