import type { ProviderCondition } from "@/lib/types";

export interface ConditionOption {
  value: ProviderCondition;
  label: string;
  hint: string;
}

export const PROVIDER_CONDITIONS: ConditionOption[] = [
  {
    value: "reply_visible",
    label: "Reply visible",
    hint: "The index already includes the reply.",
  },
  {
    value: "reply_not_yet_visible",
    label: "Provider index stale",
    hint: "A reply may already be invisible to the provider.",
  },
  {
    value: "provider_unavailable",
    label: "Provider unavailable",
    hint: "The check does not answer.",
  },
];

const EVENT_LABELS: Record<string, string> = {
  INITIAL_EMAIL_SENT: "Initial email",
  PROSPECT_REPLIED: "Prospect reply",
  FOLLOWUP_SENT: "Follow-up sent",
};

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] ?? type.replaceAll("_", " ").toLowerCase();
}

export function conditionLabel(value: string): string {
  return PROVIDER_CONDITIONS.find((option) => option.value === value)?.label ?? value;
}

export function providerCheckLabel(value: string): string {
  switch (value) {
    case "REPLY_CONFIRMED":
      return "Reply confirmed";
    case "NO_REPLY_FOUND":
      return "No reply found";
    case "UNAVAILABLE":
      return "Unavailable";
    case "not run":
      return "Not run";
    default:
      return value;
  }
}

export function recordedCaption(outcome: string): string {
  if (outcome === "SENT") {
    return "This follow-up is already in the synthetic event log. It is not a new send.";
  }
  return "No matching follow-up was recorded in the log.";
}

export function guardedCaption(decision: string): string {
  switch (decision) {
    case "ALLOW":
      return "Provider information was stale; a simulated send was permitted. No email was delivered.";
    case "CANCEL":
      return "Safeguard detected the reply. No email was sent.";
    case "DEFER":
      return "Provider was unavailable; simulated sending was postponed. No email was sent.";
    default:
      return "Hypothetical decision from the safeguard simulation. No email was sent.";
  }
}

export function simulatedSendLabel(recorded: boolean): string {
  return recorded
    ? "A simulated send was recorded. No email was delivered."
    : "No simulated send was recorded.";
}

export function decisionTextClass(decision: string): string {
  if (decision === "CANCEL") return "text-pine";
  if (decision === "ALLOW") return "text-amber";
  if (decision === "DEFER") return "text-sea";
  return "text-ink";
}

export function decisionFrameClass(decision: string): string {
  if (decision === "CANCEL") return "border-pine/40";
  if (decision === "ALLOW") return "border-amber/50";
  if (decision === "DEFER") return "border-sea/40";
  return "border-line";
}
