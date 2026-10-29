"use client";

import { Pill, stateTone } from "@/components/Pill";
import { cn } from "@/lib/cn";
import {
  conditionLabel,
  decisionFrameClass,
  decisionTextClass,
  guardedCaption,
  PROVIDER_CONDITIONS,
  providerCheckLabel,
  recordedCaption,
  simulatedSendLabel,
} from "@/lib/labels";
import { formatUtcShortClock } from "@/lib/time";
import type { CompareResponse, FollowUpComparisonModel, ProviderCondition, ReplyEvidenceModel } from "@/lib/types";

export function SafeguardPanel({
  condition,
  onCondition,
  comparison,
  loading,
  error,
}: {
  condition: ProviderCondition;
  onCondition: (condition: ProviderCondition) => void;
  comparison: CompareResponse | null;
  loading: boolean;
  error: string | null;
}) {
  return (
    <div>
      <h2 className="font-serif text-xl tracking-tight text-ink">Pre-send check</h2>
      <div aria-label="Provider condition" className="mt-3 grid gap-2 md:grid-cols-3">
        {PROVIDER_CONDITIONS.map((option) => {
          const selected = option.value === condition;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={selected}
              onClick={() => onCondition(option.value)}
              className={cn(
                "rounded-xl border px-3 py-2.5 text-left",
                selected ? "border-pine bg-pine-soft" : "border-line bg-raised hover:border-line-strong",
              )}
            >
              <span className="block text-sm font-medium text-ink">{option.label}</span>
              <span className="mt-0.5 block text-xs leading-snug text-ink">{option.hint}</span>
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink">
        The left card is the follow-up already in the synthetic log. The right card is a hypothetical check. Neither
        one delivers email.
      </p>

      <div className="mt-4" aria-live="polite" aria-busy={loading}>
        {error ? (
          <p role="alert" className="rounded-xl border border-copper/40 bg-copper-soft px-4 py-3 text-sm text-copper">
            {error}
          </p>
        ) : null}
        {loading && !comparison ? <p className="text-sm text-ink">Running the safeguard simulation…</p> : null}
        {comparison && comparison.comparisons.length === 0 ? (
          <p className="text-sm text-ink">This incident has no follow-up to compare.</p>
        ) : null}
        <div className="space-y-4">
          {comparison?.comparisons.map((item) => (
            <ComparisonPair
              key={item.followup_event_id}
              item={item}
              condition={comparison.provider_condition}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ComparisonPair({ item, condition }: { item: FollowUpComparisonModel; condition: string }) {
  const { unguarded, guarded } = item;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <article className="rounded-xl border border-line bg-raised px-4 py-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink">Recorded synthetic send</p>
        <h3 className="mt-2 font-serif text-4xl tracking-tight text-ink">{unguarded.outcome}</h3>
        <p className="mt-2 text-sm leading-relaxed text-ink">{recordedCaption(unguarded.outcome)}</p>
        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink">
          Known state <Pill tone={stateTone(unguarded.known_state)}>{unguarded.known_state}</Pill>
        </p>
      </article>

      <article className={cn("rounded-xl border bg-raised px-4 py-4", decisionFrameClass(guarded.decision))}>
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink">
          Hypothetical check · {conditionLabel(condition)}
        </p>
        <h3 className={cn("mt-2 font-serif text-4xl tracking-tight", decisionTextClass(guarded.decision))}>
          {guarded.decision}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-ink">{guardedCaption(guarded.decision)}</p>
        <p className="mt-3 text-sm text-ink">Provider check: {providerCheckLabel(guarded.provider_check)}</p>
        <p className="mt-1 text-sm text-ink">{simulatedSendLabel(guarded.simulated_send_recorded)}</p>
        <Visibility replies={guarded.replies} consulted={guarded.records_consulted} />
      </article>
    </div>
  );
}

function Visibility({ replies, consulted }: { replies: ReplyEvidenceModel[]; consulted: boolean }) {
  if (replies.length === 0) {
    return (
      <p className="mt-3 text-sm text-ink">
        {consulted ? "Provider records were consulted." : "Provider records were not consulted."}
      </p>
    );
  }

  return (
    <ul className="mt-3 space-y-1">
      {replies.map((reply) => (
        <li key={reply.reply_event_id} className="text-sm text-ink">
          Reply occurred {formatUtcShortClock(reply.occurred_at)} UTC. Visible to the provider{" "}
          {formatUtcShortClock(reply.visible_at)} UTC.{" "}
          {reply.visible_to_provider_at_decision ? "Visible at the decision." : "Not visible at the decision."}
        </li>
      ))}
    </ul>
  );
}
