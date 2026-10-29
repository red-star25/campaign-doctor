"""Turn engine results into API models.

The historical events are only read. Provider records are new objects, so a
what-if check cannot change the log.
"""

from __future__ import annotations

from datetime import timedelta

from campaign_doctor.analysis import Report, build_report
from campaign_doctor.api.catalog import LoadedScenario, list_entries, load_entry
from campaign_doctor.api.schemas import (
    CompareResponse,
    DiagnosisModel,
    EventModel,
    FindingModel,
    FollowUpComparisonModel,
    GuardedOutcomeModel,
    HealthResponse,
    LeadStateModel,
    LedgerLifecycleModel,
    ObservationStepModel,
    ProviderCondition,
    ReplyEvidenceModel,
    ReportResponse,
    ScenarioListResponse,
    ScenarioSummary,
    SendAfterStopModel,
    UnguardedOutcomeModel,
    format_utc,
)
from campaign_doctor.models import Event, EventType
from campaign_doctor.safeguards import (
    SAFEGUARD_LIMITS,
    BaselineOutcome,
    DecisionLedger,
    ProviderFailure,
    ProviderFailureKind,
    ProviderReplyRecord,
    SafeguardComparison,
    ScriptedReplyProvider,
    compare_safeguards,
    records_visible_at_occurrence,
    request_for_followup,
)

LEDGER_EXPLANATION = (
    "This comparison creates a new in-memory ledger and drops it when the response is built. "
    "Inside that one simulation, one idempotency key records at most one simulated send. "
    "The ledger is not saved. The next HTTP request starts from an empty ledger. "
    "Idempotency here is not durable across API requests."
)

_STALE_GAP = timedelta(minutes=1)


class UnknownFollowUp(Exception):
    """The caller named a follow-up that is not in this scenario."""


def health() -> HealthResponse:
    return HealthResponse()


def list_scenarios() -> ScenarioListResponse:
    rows: list[ScenarioSummary] = []
    for entry in list_entries():
        loaded = load_entry(entry.scenario_id)
        rows.append(
            ScenarioSummary(
                scenario_id=entry.scenario_id,
                name=entry.name,
                description=loaded.scenario.description,
                problem_category=entry.problem_category,
            )
        )
    return ScenarioListResponse(scenarios=rows)


def build_scenario_report(scenario_id: str) -> ReportResponse:
    loaded = load_entry(scenario_id)
    report = build_report(loaded.scenario.events)
    return _report_response(loaded, report)


def compare_scenario(
    scenario_id: str,
    condition: ProviderCondition,
    followup_event_id: str | None,
) -> CompareResponse:
    loaded = load_entry(scenario_id)
    events = loaded.scenario.events
    followups = _select_followups(events, followup_event_id)
    ledger = DecisionLedger()
    rows: list[FollowUpComparisonModel] = []
    limitations = list(SAFEGUARD_LIMITS)
    for followup in followups:
        provider, consulted, failure_kind, replies = _provider_for(events, followup, condition)
        comparison = compare_safeguards(
            events,
            request_for_followup(followup),
            provider,
            ledger,
        )
        limitations = list(comparison.limits)
        rows.append(
            _comparison_row(
                followup,
                comparison,
                condition,
                consulted,
                failure_kind,
                replies,
            )
        )
    return CompareResponse(
        scenario_id=loaded.entry.scenario_id,
        provider_condition=condition,
        ledger=LedgerLifecycleModel(explanation=LEDGER_EXPLANATION),
        comparisons=rows,
        limitations=limitations,
    )


def _select_followups(events: tuple[Event, ...], followup_event_id: str | None) -> tuple[Event, ...]:
    followups = tuple(
        sorted(
            (event for event in events if event.type is EventType.FOLLOWUP_SENT),
            key=lambda event: (event.occurred_at, event.event_id),
        )
    )
    if followup_event_id is None:
        return followups
    chosen = tuple(event for event in followups if event.event_id == followup_event_id)
    if not chosen:
        raise UnknownFollowUp()
    return chosen


def _provider_for(
    events: tuple[Event, ...],
    followup: Event,
    condition: ProviderCondition,
) -> tuple[ScriptedReplyProvider, bool, str | None, tuple[ProviderReplyRecord, ...]]:
    if condition is ProviderCondition.REPLY_VISIBLE:
        records = records_visible_at_occurrence(events)
        return ScriptedReplyProvider(records), True, None, records
    if condition is ProviderCondition.REPLY_NOT_YET_VISIBLE:
        records = _stale_records(events, followup)
        return ScriptedReplyProvider(records), True, None, records
    failure = ProviderFailure(ProviderFailureKind.TIMEOUT, "simulated timeout")
    return ScriptedReplyProvider(failure=failure), False, failure.kind.value, ()


def _stale_records(events: tuple[Event, ...], followup: Event) -> tuple[ProviderReplyRecord, ...]:
    """Show each reply only after the follow-up decision.

    `occurred_at` stays the historical time. `visible_at` is moved later so
    the provider index has not caught up yet. The event objects are not changed.
    """
    records: list[ProviderReplyRecord] = []
    later = followup.occurred_at + _STALE_GAP
    for event in events:
        if event.type is not EventType.PROSPECT_REPLIED:
            continue
        visible_at = later if later >= event.occurred_at else event.occurred_at
        records.append(
            ProviderReplyRecord(
                campaign_id=event.campaign_id,
                lead_id=event.lead_id,
                reply_event_id=event.event_id,
                occurred_at=event.occurred_at,
                visible_at=visible_at,
            )
        )
    return tuple(records)


def _report_response(loaded: LoadedScenario, report: Report) -> ReportResponse:
    diagnosis = report.diagnosis
    return ReportResponse(
        scenario_id=loaded.entry.scenario_id,
        name=loaded.entry.name,
        description=loaded.scenario.description,
        problem_category=loaded.entry.problem_category,
        occurrence_order=[_event_model(event) for event in report.occurrence_order],
        observation_order=[
            ObservationStepModel(
                event=_event_model(step.event),
                known_state_before=step.known_state_before.value,
                known_state_after=step.known_state_after.value,
            )
            for step in report.steps
        ],
        final_states=[
            LeadStateModel(campaign_id=campaign_id, lead_id=lead_id, state=state.value)
            for (campaign_id, lead_id), state in sorted(report.final_states.items())
        ],
        diagnosis=DiagnosisModel(
            pattern_matched=diagnosis.pattern_matched,
            summary=diagnosis.summary,
            certainty=diagnosis.certainty,
            findings=[
                FindingModel(
                    followup_event_id=finding.followup.event_id,
                    reply_event_id=finding.reply.event_id,
                    decision_time=format_utc(finding.followup.occurred_at),
                    known_state_at_decision=finding.known_state_at_send.value,
                    reply_occurred_at=format_utc(finding.reply.occurred_at),
                    reply_observed_at=format_utc(finding.reply.observed_at),
                )
                for finding in diagnosis.findings
            ],
            sends_after_known_stop=[
                SendAfterStopModel(
                    followup_event_id=send.followup.event_id,
                    decision_time=format_utc(send.followup.occurred_at),
                    known_state_at_decision=send.known_state_at_send.value,
                    processed_reply_event_ids=[reply.event_id for reply in send.processed_replies],
                    unprocessed_reply_event_ids=[
                        reply.event_id for reply in send.unprocessed_replies
                    ],
                )
                for send in diagnosis.sends_after_known_stop
            ],
            limitations=list(diagnosis.limitations),
        ),
    )


def _comparison_row(
    followup: Event,
    comparison: SafeguardComparison,
    condition: ProviderCondition,
    records_consulted: bool,
    failure_kind: str | None,
    replies: tuple[ProviderReplyRecord, ...],
) -> FollowUpComparisonModel:
    unguarded = comparison.unguarded
    guarded = comparison.guarded
    provider_result = guarded.provider_result
    provider_check = "not run" if provider_result is None else provider_result.status.value
    matched = followup.event_id if unguarded.outcome is BaselineOutcome.SENT else None
    return FollowUpComparisonModel(
        followup_event_id=followup.event_id,
        unguarded=UnguardedOutcomeModel(
            outcome=unguarded.outcome.value,
            decision_time=format_utc(unguarded.decision_time),
            known_state=unguarded.known_state.value,
            explanation=unguarded.explanation,
            matched_event_id=matched,
            evidence_note=(
                "Unguarded uses the follow-up already stored in the synthetic log. "
                "No provider was asked, and this outcome is not a new email."
            ),
        ),
        guarded=GuardedOutcomeModel(
            decision=guarded.decision.value,
            decision_time=format_utc(guarded.decision_time),
            known_state=guarded.known_state.value,
            provider_check=provider_check,
            failure_kind=failure_kind,
            explanation=guarded.explanation,
            simulated_send_recorded=guarded.simulated_send_recorded,
            records_consulted=records_consulted,
            replies=[_reply_evidence(record, followup) for record in replies],
            evidence_note=_guarded_note(condition),
        ),
    )


def _reply_evidence(record: ProviderReplyRecord, followup: Event) -> ReplyEvidenceModel:
    visible = record.occurred_at <= followup.occurred_at and record.visible_at <= followup.occurred_at
    return ReplyEvidenceModel(
        reply_event_id=record.reply_event_id,
        occurred_at=format_utc(record.occurred_at),
        visible_at=format_utc(record.visible_at),
        visible_to_provider_at_decision=visible,
    )


def _guarded_note(condition: ProviderCondition) -> str:
    if condition is ProviderCondition.REPLY_VISIBLE:
        return (
            "The provider index includes a reply at the moment it happened. "
            "The webhook time was not given to the provider. CANCEL means no email was sent."
        )
    if condition is ProviderCondition.REPLY_NOT_YET_VISIBLE:
        return (
            "The reply can already have happened. The provider index used here does not "
            "include it until after the decision, so the check can allow a follow-up."
        )
    return (
        "The provider did not answer. Reply records were not consulted. "
        "DEFER is not an email and it is not a permanent block."
    )


def _event_model(event: Event) -> EventModel:
    return EventModel(
        event_id=event.event_id,
        campaign_id=event.campaign_id,
        lead_id=event.lead_id,
        type=event.type.value,
        occurred_at=format_utc(event.occurred_at),
        observed_at=format_utc(event.observed_at),
        metadata=dict(event.metadata),
    )
