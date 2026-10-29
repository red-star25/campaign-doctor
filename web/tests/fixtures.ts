import type {
  CompareResponse,
  ProviderCondition,
  ReportResponse,
  ScenarioSummary,
} from "@/lib/types";

export const scenarioSummary: ScenarioSummary = {
  scenario_id: "delayed_reply",
  name: "Delayed reply notification",
  description: "Synthetic incident on 2026-10-27 UTC. The prospect replied at 09:58.",
  problem_category: "delayed_reply",
  synthetic: true,
};

const reply = {
  event_id: "evt_prospect_reply",
  campaign_id: "camp_synthetic",
  lead_id: "lead_synthetic",
  type: "PROSPECT_REPLIED",
  occurred_at: "2026-10-27T09:58:00Z",
  observed_at: "2026-10-27T10:02:00Z",
  metadata: { channel: "email", source: "webhook" },
};

const followup = {
  event_id: "evt_followup_sent",
  campaign_id: "camp_synthetic",
  lead_id: "lead_synthetic",
  type: "FOLLOWUP_SENT",
  occurred_at: "2026-10-27T10:00:00Z",
  observed_at: "2026-10-27T10:00:00Z",
  metadata: { channel: "email" },
};

const initial = {
  event_id: "evt_initial_email",
  campaign_id: "camp_synthetic",
  lead_id: "lead_synthetic",
  type: "INITIAL_EMAIL_SENT",
  occurred_at: "2026-10-27T09:00:00Z",
  observed_at: "2026-10-27T09:00:00Z",
  metadata: { channel: "email" },
};

export const report: ReportResponse = {
  synthetic: true,
  confirmed_production_bug: false,
  scenario_id: "delayed_reply",
  name: "Delayed reply notification",
  description: scenarioSummary.description,
  problem_category: "delayed_reply",
  occurrence_order: [initial, reply, followup],
  observation_order: [
    { event: initial, known_state_before: "ACTIVE", known_state_after: "ACTIVE" },
    { event: followup, known_state_before: "ACTIVE", known_state_after: "ACTIVE" },
    { event: reply, known_state_before: "ACTIVE", known_state_after: "STOPPED" },
  ],
  final_states: [{ campaign_id: "camp_synthetic", lead_id: "lead_synthetic", state: "STOPPED" }],
  diagnosis: {
    pattern_matched: true,
    summary:
      "The follow-up was sent after a prospect had replied, but before the reply notification was processed. This is consistent with delayed event delivery.",
    certainty: "Treat this as a suspicion rather than a confirmed root cause.",
    findings: [
      {
        followup_event_id: "evt_followup_sent",
        reply_event_id: "evt_prospect_reply",
        decision_time: "2026-10-27T10:00:00Z",
        known_state_at_decision: "ACTIVE",
        reply_occurred_at: "2026-10-27T09:58:00Z",
        reply_observed_at: "2026-10-27T10:02:00Z",
      },
    ],
    sends_after_known_stop: [],
    limitations: ["These records are synthetic."],
    confirmed_production_bug: false,
  },
};

export function makeComparison(condition: ProviderCondition, decision: string): CompareResponse {
  const replyVisible = condition === "reply_visible";
  return {
    synthetic: true,
    confirmed_production_bug: false,
    scenario_id: "delayed_reply",
    provider_condition: condition,
    ledger: {
      durable_across_requests: false,
      scope: "single_request",
      explanation: "The ledger is not saved.",
    },
    comparisons: [
      {
        followup_event_id: "evt_followup_sent",
        unguarded: {
          outcome: "SENT",
          decision_time: "2026-10-27T10:00:00Z",
          known_state: "ACTIVE",
          provider_check: "not run",
          explanation: "Unguarded path: the follow-up is the one recorded in the log.",
          matched_event_id: "evt_followup_sent",
          evidence_note: "Unguarded uses the follow-up already stored in the synthetic log.",
        },
        guarded: {
          decision,
          decision_time: "2026-10-27T10:00:00Z",
          known_state: "ACTIVE",
          provider_check: replyVisible ? "REPLY_CONFIRMED" : decision === "DEFER" ? "UNAVAILABLE" : "NO_REPLY_FOUND",
          failure_kind: decision === "DEFER" ? "TIMEOUT" : null,
          explanation:
            decision === "ALLOW"
              ? "This simulation recorded one send. No message left this program."
              : "No email was sent.",
          simulated_send_recorded: decision === "ALLOW",
          records_consulted: decision !== "DEFER",
          replies: replyVisible
            ? [
                {
                  reply_event_id: "evt_prospect_reply",
                  occurred_at: "2026-10-27T09:58:00Z",
                  visible_at: "2026-10-27T09:58:00Z",
                  visible_to_provider_at_decision: true,
                },
              ]
            : [],
          evidence_note: "CANCEL means no email was sent.",
        },
      },
    ],
    limitations: ["This safeguard does not guarantee that an unwanted follow-up can never go out."],
  };
}
