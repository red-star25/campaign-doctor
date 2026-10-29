"""Event records for a campaign log.

Two clocks matter. `occurred_at` is when something happened to the prospect.
`observed_at` is when this automation processed that fact. A reply can exist
at the mail provider before the webhook arrives, so those clocks can differ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence


class LogValidationError(ValueError):
    """The log is missing a field or breaks a timestamp rule."""


class EventType(StrEnum):
    INITIAL_EMAIL_SENT = "INITIAL_EMAIL_SENT"
    PROSPECT_REPLIED = "PROSPECT_REPLIED"
    FOLLOWUP_SENT = "FOLLOWUP_SENT"


class SequenceState(StrEnum):
    """What the automation believes about one lead.

    ACTIVE means no reply has been processed yet. STOPPED means a reply
    has been processed. The real-world reply can be earlier than that.
    """

    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"


_EVENT_FIELDS = {
    "event_id",
    "campaign_id",
    "lead_id",
    "type",
    "occurred_at",
    "observed_at",
    "metadata",
}
_SCENARIO_FIELDS = {"scenario_id", "description", "events"}
_UTC = timedelta(0)


@dataclass(frozen=True)
class Event:
    event_id: str
    campaign_id: str
    lead_id: str
    type: EventType
    occurred_at: datetime
    observed_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_id = _require_token(self.event_id, "event_id")
        campaign_id = _require_token(self.campaign_id, "campaign_id")
        lead_id = _require_token(self.lead_id, "lead_id")
        event_type = _require_event_type(self.type)
        occurred_at = _require_utc(self.occurred_at, "occurred_at")
        observed_at = _require_utc(self.observed_at, "observed_at")
        # A fact cannot be processed before it happened.
        if observed_at < occurred_at:
            raise LogValidationError(
                f"event {event_id}: observed_at is earlier than occurred_at"
            )
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "campaign_id", campaign_id)
        object.__setattr__(self, "lead_id", lead_id)
        object.__setattr__(self, "type", event_type)
        object.__setattr__(self, "occurred_at", occurred_at)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "metadata", _require_metadata(self.metadata))


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    events: tuple[Event, ...]


def load_scenario(path: str | Path) -> Scenario:
    """Read one synthetic scenario file."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LogValidationError(f"could not read {file_path}: {exc.strerror}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LogValidationError(f"{file_path} is not valid JSON: {exc.msg}") from exc
    return parse_scenario(raw)


def parse_scenario(raw: object) -> Scenario:
    if not isinstance(raw, dict):
        raise LogValidationError("scenario must be a JSON object")
    _reject_unknown(raw, _SCENARIO_FIELDS, "scenario")
    if "events" not in raw:
        raise LogValidationError("scenario.events is missing")
    events_raw = raw["events"]
    if not isinstance(events_raw, list):
        raise LogValidationError("scenario.events must be a list")

    events = require_unique_event_ids(
        _parse_event(item, index=index) for index, item in enumerate(events_raw)
    )

    scenario_id = raw.get("scenario_id", "scenario")
    description = raw.get("description", "")
    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise LogValidationError("scenario_id must be a non-empty string")
    if not isinstance(description, str):
        raise LogValidationError("description must be a string")
    return Scenario(
        scenario_id=scenario_id.strip(),
        description=description.strip(),
        events=events,
    )


def _parse_event(raw: object, *, index: int) -> Event:
    label = f"events[{index}]"
    if not isinstance(raw, dict):
        raise LogValidationError(f"{label} must be an object")
    _reject_unknown(raw, _EVENT_FIELDS, label)
    for name in ("event_id", "campaign_id", "lead_id", "type", "occurred_at", "observed_at"):
        if name not in raw or raw[name] is None:
            raise LogValidationError(f"{label}.{name} is missing")
    try:
        return Event(
            event_id=raw["event_id"],
            campaign_id=raw["campaign_id"],
            lead_id=raw["lead_id"],
            type=raw["type"],
            occurred_at=raw["occurred_at"],
            observed_at=raw["observed_at"],
            metadata=raw.get("metadata", {}),
        )
    except LogValidationError as exc:
        raise LogValidationError(f"{label}: {exc}") from exc


def require_unique_event_ids(events: Sequence[Event]) -> tuple[Event, ...]:
    """Reject a log that uses the same event_id more than once.

    File parsing and the report both use this rule. A repeated id would
    pair the same send with a reply twice and invent an extra finding.
    """
    materialized = tuple(events)
    seen: set[str] = set()
    for event in materialized:
        if event.event_id in seen:
            raise LogValidationError(f"duplicate event_id: {event.event_id}")
        seen.add(event.event_id)
    return materialized


def _reject_unknown(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = sorted(set(raw) - allowed)
    if extra:
        names = ", ".join(extra)
        raise LogValidationError(f"{label} has unknown fields: {names}")


def _require_token(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LogValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _require_event_type(value: object) -> EventType:
    if isinstance(value, EventType):
        return value
    if isinstance(value, str):
        try:
            return EventType(value)
        except ValueError:
            pass
    allowed = ", ".join(item.value for item in EventType)
    raise LogValidationError(f"type must be one of: {allowed}")


def _require_utc(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = _parse_iso(value, field)
    else:
        raise LogValidationError(f"{field} is missing or not an ISO-8601 UTC timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LogValidationError(f"{field} must include a UTC offset (Z or +00:00)")
    if parsed.utcoffset() != _UTC:
        raise LogValidationError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _parse_iso(value: str, field: str) -> datetime:
    text = value.strip()
    if not text:
        raise LogValidationError(f"{field} is missing")
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise LogValidationError(f"{field} is not a valid ISO-8601 timestamp") from exc


def _require_metadata(value: object) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, dict):
        raise LogValidationError("metadata must be an object")
    for key in value:
        if not isinstance(key, str):
            raise LogValidationError("metadata keys must be strings")
    return MappingProxyType(dict(value))
