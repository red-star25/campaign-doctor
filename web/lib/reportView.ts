import type { ReportResponse } from "@/lib/types";

export interface FollowupStateView {
  eventId: string;
  state: string;
}

/** Read follow-up state from fields the report already computed. */
export function followupStates(report: ReportResponse): FollowupStateView[] {
  const rows: FollowupStateView[] = [];
  const seen = new Set<string>();

  for (const finding of report.diagnosis.findings) {
    if (seen.has(finding.followup_event_id)) continue;
    seen.add(finding.followup_event_id);
    rows.push({ eventId: finding.followup_event_id, state: finding.known_state_at_decision });
  }

  for (const send of report.diagnosis.sends_after_known_stop) {
    if (seen.has(send.followup_event_id)) continue;
    seen.add(send.followup_event_id);
    rows.push({ eventId: send.followup_event_id, state: send.known_state_at_decision });
  }

  for (const step of report.observation_order) {
    if (step.event.type !== "FOLLOWUP_SENT" || seen.has(step.event.event_id)) continue;
    seen.add(step.event.event_id);
    rows.push({ eventId: step.event.event_id, state: step.known_state_before });
  }

  return rows;
}

export function formatStateList(rows: FollowupStateView[]): string {
  if (rows.length === 0) return "No follow-up in this log";
  if (rows.length === 1) return rows[0].state;
  return rows.map((row) => `${row.eventId} ${row.state}`).join(", ");
}

export function formatFinalStates(report: ReportResponse): string {
  if (report.final_states.length === 0) return "None";
  if (report.final_states.length === 1) return report.final_states[0].state;
  return report.final_states.map((state) => `${state.lead_id} ${state.state}`).join(", ");
}

export function citedEventIds(report: ReportResponse): Set<string> {
  const ids = new Set<string>();
  for (const finding of report.diagnosis.findings) {
    ids.add(finding.followup_event_id);
    ids.add(finding.reply_event_id);
  }
  return ids;
}
