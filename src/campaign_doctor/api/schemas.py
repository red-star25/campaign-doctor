"""JSON shapes for the synthetic replay API.

Times are ISO-8601 UTC with a Z suffix. Every scenario payload is marked
synthetic. A diagnosis is an explanation of a made-up log, not a confirmed
production bug.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProviderCondition(str, Enum):
    REPLY_VISIBLE = "reply_visible"
    REPLY_NOT_YET_VISIBLE = "reply_not_yet_visible"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class HealthResponse(BaseModel):
    status: str = "ok"


class ScenarioSummary(BaseModel):
    scenario_id: str
    name: str
    description: str
    problem_category: str
    synthetic: bool = True


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioSummary]


class EventModel(BaseModel):
    event_id: str
    campaign_id: str
    lead_id: str
    type: str
    occurred_at: str
    observed_at: str
    metadata: dict[str, Any]


class ObservationStepModel(BaseModel):
    event: EventModel
    known_state_before: str
    known_state_after: str


class LeadStateModel(BaseModel):
    campaign_id: str
    lead_id: str
    state: str


class FindingModel(BaseModel):
    followup_event_id: str
    reply_event_id: str
    decision_time: str
    known_state_at_decision: str
    reply_occurred_at: str
    reply_observed_at: str


class SendAfterStopModel(BaseModel):
    followup_event_id: str
    decision_time: str
    known_state_at_decision: str
    processed_reply_event_ids: list[str]
    unprocessed_reply_event_ids: list[str]


class DiagnosisModel(BaseModel):
    pattern_matched: bool
    summary: str
    certainty: str
    findings: list[FindingModel]
    sends_after_known_stop: list[SendAfterStopModel]
    limitations: list[str]
    confirmed_production_bug: bool = False


class ReportResponse(BaseModel):
    synthetic: bool = True
    confirmed_production_bug: bool = False
    scenario_id: str
    name: str
    description: str
    problem_category: str
    occurrence_order: list[EventModel]
    observation_order: list[ObservationStepModel]
    final_states: list[LeadStateModel]
    diagnosis: DiagnosisModel


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_condition: ProviderCondition
    followup_event_id: str | None = None


class UnguardedOutcomeModel(BaseModel):
    outcome: str
    decision_time: str
    known_state: str
    provider_check: str = "not run"
    explanation: str
    matched_event_id: str | None
    evidence_note: str


class ReplyEvidenceModel(BaseModel):
    reply_event_id: str
    occurred_at: str
    visible_at: str
    visible_to_provider_at_decision: bool


class GuardedOutcomeModel(BaseModel):
    decision: str
    decision_time: str
    known_state: str
    provider_check: str
    failure_kind: str | None
    explanation: str
    simulated_send_recorded: bool
    records_consulted: bool
    replies: list[ReplyEvidenceModel]
    evidence_note: str


class FollowUpComparisonModel(BaseModel):
    followup_event_id: str
    unguarded: UnguardedOutcomeModel
    guarded: GuardedOutcomeModel


class LedgerLifecycleModel(BaseModel):
    durable_across_requests: bool = False
    scope: str = "single_request"
    explanation: str


class CompareResponse(BaseModel):
    synthetic: bool = True
    confirmed_production_bug: bool = False
    scenario_id: str
    provider_condition: ProviderCondition
    ledger: LedgerLifecycleModel
    comparisons: list[FollowUpComparisonModel]
    limitations: list[str]


def format_utc(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text
