/** JSON shapes from src/campaign_doctor/api/schemas.py. */

export type ProviderCondition =
  | "reply_visible"
  | "reply_not_yet_visible"
  | "provider_unavailable";

export interface ScenarioSummary {
  scenario_id: string;
  name: string;
  description: string;
  problem_category: string;
  synthetic: boolean;
}

export interface ScenarioListResponse {
  scenarios: ScenarioSummary[];
}

export interface EventModel {
  event_id: string;
  campaign_id: string;
  lead_id: string;
  type: string;
  occurred_at: string;
  observed_at: string;
  metadata: Record<string, unknown>;
}

export interface ObservationStepModel {
  event: EventModel;
  known_state_before: string;
  known_state_after: string;
}

export interface LeadStateModel {
  campaign_id: string;
  lead_id: string;
  state: string;
}

export interface FindingModel {
  followup_event_id: string;
  reply_event_id: string;
  decision_time: string;
  known_state_at_decision: string;
  reply_occurred_at: string;
  reply_observed_at: string;
}

export interface SendAfterStopModel {
  followup_event_id: string;
  decision_time: string;
  known_state_at_decision: string;
  processed_reply_event_ids: string[];
  unprocessed_reply_event_ids: string[];
}

export interface DiagnosisModel {
  pattern_matched: boolean;
  summary: string;
  certainty: string;
  findings: FindingModel[];
  sends_after_known_stop: SendAfterStopModel[];
  limitations: string[];
  confirmed_production_bug: boolean;
}

export interface ReportResponse {
  synthetic: boolean;
  confirmed_production_bug: boolean;
  scenario_id: string;
  name: string;
  description: string;
  problem_category: string;
  occurrence_order: EventModel[];
  observation_order: ObservationStepModel[];
  final_states: LeadStateModel[];
  diagnosis: DiagnosisModel;
}

export interface UnguardedOutcomeModel {
  outcome: string;
  decision_time: string;
  known_state: string;
  provider_check: string;
  explanation: string;
  matched_event_id: string | null;
  evidence_note: string;
}

export interface ReplyEvidenceModel {
  reply_event_id: string;
  occurred_at: string;
  visible_at: string;
  visible_to_provider_at_decision: boolean;
}

export interface GuardedOutcomeModel {
  decision: string;
  decision_time: string;
  known_state: string;
  provider_check: string;
  failure_kind: string | null;
  explanation: string;
  simulated_send_recorded: boolean;
  records_consulted: boolean;
  replies: ReplyEvidenceModel[];
  evidence_note: string;
}

export interface FollowUpComparisonModel {
  followup_event_id: string;
  unguarded: UnguardedOutcomeModel;
  guarded: GuardedOutcomeModel;
}

export interface LedgerLifecycleModel {
  durable_across_requests: boolean;
  scope: string;
  explanation: string;
}

export interface CompareResponse {
  synthetic: boolean;
  confirmed_production_bug: boolean;
  scenario_id: string;
  provider_condition: ProviderCondition;
  ledger: LedgerLifecycleModel;
  comparisons: FollowUpComparisonModel[];
  limitations: string[];
}
