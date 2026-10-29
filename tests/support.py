"""Event builders shared by the tests."""

from datetime import datetime, timezone
from pathlib import Path

from campaign_doctor.models import Event, EventType

ROOT = Path(__file__).resolve().parents[1]
DELAYED_REPLY = ROOT / "scenarios" / "delayed_reply.json"


def utc(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, 27, hour, minute, second, tzinfo=timezone.utc)


def make_event(**overrides: object) -> Event:
    values: dict[str, object] = {
        "event_id": "evt",
        "campaign_id": "camp_synthetic",
        "lead_id": "lead_synthetic",
        "type": EventType.FOLLOWUP_SENT,
        "occurred_at": utc(10, 0),
        "observed_at": utc(10, 0),
        "metadata": {},
    }
    values.update(overrides)
    return Event(**values)  # type: ignore[arg-type]
