"""Replay synthetic campaign logs and describe delayed-reply timing.

This package does not connect to a mailbox, a CRM, or Cardinal.
"""

from campaign_doctor.analysis import (
    DELAYED_REPLY_SUMMARY,
    Diagnosis,
    DelayedReplyFinding,
    Report,
    SendAfterKnownStop,
    analyze,
    build_report,
)
from campaign_doctor.models import (
    Event,
    EventType,
    LogValidationError,
    Scenario,
    SequenceState,
    load_scenario,
    require_unique_event_ids,
)
from campaign_doctor.replay import ReplayResult, ReplayStep, occurrence_timeline, replay
from campaign_doctor.safeguards import (
    DecisionLedger,
    PreSendDecision,
    ProviderCheckStatus,
    SafeguardComparison,
    ScriptedReplyProvider,
    SendDecision,
    compare_safeguards,
    decide_followup,
)

__all__ = [
    "DELAYED_REPLY_SUMMARY",
    "DelayedReplyFinding",
    "DecisionLedger",
    "Diagnosis",
    "Event",
    "EventType",
    "LogValidationError",
    "ReplayResult",
    "PreSendDecision",
    "ProviderCheckStatus",
    "ReplayStep",
    "Report",
    "SafeguardComparison",
    "ScriptedReplyProvider",
    "SendDecision",
    "Scenario",
    "SendAfterKnownStop",
    "SequenceState",
    "analyze",
    "build_report",
    "compare_safeguards",
    "decide_followup",
    "load_scenario",
    "occurrence_timeline",
    "replay",
    "require_unique_event_ids",
]
