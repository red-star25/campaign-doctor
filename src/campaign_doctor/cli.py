"""Print both timelines, the diagnosis, and a guarded versus unguarded comparison."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from campaign_doctor.analysis import Report, build_report
from campaign_doctor.models import Event, EventType, LogValidationError, Scenario, load_scenario
from campaign_doctor.replay import ReplayStep
from campaign_doctor.safeguards import (
    DecisionLedger,
    PreSendDecision,
    ProviderCheckResult,
    SafeguardComparison,
    ScriptedReplyProvider,
    compare_safeguards,
    records_visible_at_occurrence,
    request_for_followup,
)


def console_main() -> None:
    """Entry point for the installed `campaign-doctor` command."""
    raise SystemExit(main())


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 1 and args[0] in {"-h", "--help"}:
        print(_usage(), file=sys.stderr)
        return 0
    if len(args) != 1:
        print(_usage(), file=sys.stderr)
        return 2
    try:
        scenario = load_scenario(args[0])
    except LogValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render(scenario))
    return 0


def render(scenario: Scenario) -> str:
    report = build_report(scenario.events)
    lines = [f"Scenario: {scenario.scenario_id}"]
    if scenario.description:
        lines.append(scenario.description)
    lines.append("")
    lines.append("Occurrence order (when it happened):")
    lines.extend(_occurrence_rows(report.occurrence_order))
    lines.append("")
    lines.append("Observation order (when the automation processed it):")
    lines.append("A reply stops the sequence in this order, at processing time.")
    lines.extend(_observation_rows(report.steps))
    lines.append("")
    lines.append("Known state after replay:")
    lines.extend(_state_rows(report))
    lines.append("")
    lines.extend(_diagnosis_rows(report))
    lines.append("")
    lines.extend(_safeguard_rows(scenario))
    return "\n".join(lines)


def _usage() -> str:
    return "usage: python -m campaign_doctor <scenario.json>"


def _occurrence_rows(events: tuple[Event, ...]) -> list[str]:
    if not events:
        return ["  (no events)"]
    rows = [("occurred_at", "observed_at", "type", "event_id", "lead")]
    rows.extend(
        (
            _format_utc(event.occurred_at),
            _format_utc(event.observed_at),
            event.type.value,
            event.event_id,
            event.lead_id,
        )
        for event in events
    )
    return _table(rows)


def _observation_rows(steps: tuple[ReplayStep, ...]) -> list[str]:
    if not steps:
        return ["  (no events)"]
    rows = [("observed_at", "occurred_at", "type", "event_id", "lead", "known_state")]
    rows.extend(
        (
            _format_utc(step.event.observed_at),
            _format_utc(step.event.occurred_at),
            step.event.type.value,
            step.event.event_id,
            step.event.lead_id,
            f"{step.known_state_before.value} -> {step.known_state_after.value}",
        )
        for step in steps
    )
    return _table(rows)


def _state_rows(report: Report) -> list[str]:
    if not report.final_states:
        return ["  (no leads in the log)"]
    rows = [
        (campaign_id, lead_id, state.value)
        for (campaign_id, lead_id), state in sorted(report.final_states.items())
    ]
    return _table(rows)


def _diagnosis_rows(report: Report) -> list[str]:
    diagnosis = report.diagnosis
    lines = ["Diagnosis:", f"  {diagnosis.summary}", "", f"  {diagnosis.certainty}"]
    if diagnosis.findings:
        lines.append("")
        lines.append("  Matching sends:")
        for finding in diagnosis.findings:
            lines.append(
                "  - "
                f"{finding.followup.event_id} sent at {_format_utc(finding.followup.occurred_at)} "
                f"for {finding.followup.lead_id}"
            )
            lines.append(
                "    "
                f"reply {finding.reply.event_id} occurred at {_format_utc(finding.reply.occurred_at)} "
                f"and was observed at {_format_utc(finding.reply.observed_at)}"
            )
            lines.append(
                f"    known state at send time: {finding.known_state_at_send.value}"
            )
    if diagnosis.sends_after_known_stop:
        lines.append("")
        lines.append("  Sends after the known state was STOPPED:")
        for send in diagnosis.sends_after_known_stop:
            lines.append(
                "  - "
                f"{send.followup.event_id} sent at {_format_utc(send.followup.occurred_at)} "
                f"for {send.followup.lead_id}"
            )
            lines.append(f"    known state at send time: {send.known_state_at_send.value}")
            if send.processed_replies:
                lines.append("    replies already processed:")
                for reply in send.processed_replies:
                    lines.append(
                        "    - "
                        f"{reply.event_id} occurred at {_format_utc(reply.occurred_at)} "
                        f"and was observed at {_format_utc(reply.observed_at)}"
                    )
            if send.unprocessed_replies:
                lines.append("    replies still unprocessed at send time:")
                for reply in send.unprocessed_replies:
                    lines.append(
                        "    - "
                        f"{reply.event_id} occurred at {_format_utc(reply.occurred_at)} "
                        f"and was observed at {_format_utc(reply.observed_at)}"
                    )
    if diagnosis.limitations:
        lines.append("")
        lines.append("Limits of this result:")
        for limit in diagnosis.limitations:
            lines.append(f"  - {limit}")
    return lines


def _safeguard_rows(scenario: Scenario) -> list[str]:
    followups = sorted(
        (event for event in scenario.events if event.type is EventType.FOLLOWUP_SENT),
        key=lambda event: (event.occurred_at, event.event_id),
    )
    lines = [
        "Safeguard simulation:",
        "  Synthetic provider check. This tool does not send email.",
    ]
    if not followups:
        lines.append("  No follow-up in this log to compare.")
        return lines
    provider = ScriptedReplyProvider(records_visible_at_occurrence(scenario.events))
    ledger = DecisionLedger()
    lines.append("  The provider can see a reply once it has happened. The webhook time is not used.")
    comparison: SafeguardComparison | None = None
    for followup in followups:
        comparison = compare_safeguards(
            scenario.events,
            request_for_followup(followup),
            provider,
            ledger,
        )
        lines.append("")
        lines.append(
            f"  Follow-up {followup.event_id} for {followup.lead_id}:"
        )
        lines.extend(_unguarded_rows(comparison))
        lines.extend(_guarded_rows(comparison.guarded))
    if comparison is not None:
        lines.append("")
        lines.append("Limits of the safeguard:")
        for limit in comparison.limits:
            lines.append(f"  - {limit}")
    return lines


def _unguarded_rows(comparison: SafeguardComparison) -> list[str]:
    outcome = comparison.unguarded
    return [
        "  Unguarded:",
        f"    decision_time: {_format_utc(outcome.decision_time)}",
        f"    known_state: {outcome.known_state.value}",
        "    provider_check: not run",
        f"    outcome: {outcome.outcome.value}",
        f"    {outcome.explanation}",
    ]


def _guarded_rows(decision: PreSendDecision) -> list[str]:
    return [
        "  Guarded:",
        f"    decision_time: {_format_utc(decision.decision_time)}",
        f"    known_state: {decision.known_state.value}",
        f"    provider_check: {_provider_label(decision.provider_result)}",
        f"    decision: {decision.decision.value}",
        f"    {decision.explanation}",
    ]


def _provider_label(result: ProviderCheckResult | None) -> str:
    if result is None:
        return "not run"
    if result.failure_kind is None:
        return result.status.value
    return f"{result.status.value} ({result.failure_kind.value})"


def _table(rows: list[tuple[str, ...]]) -> list[str]:
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    rendered: list[str] = []
    for row in rows:
        cells = [cell.ljust(widths[index]) for index, cell in enumerate(row)]
        rendered.append("  " + "  ".join(cells).rstrip())
    return rendered


def _format_utc(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


if __name__ == "__main__":
    sys.exit(main())
