import { ChevronDown } from "lucide-react";
import { formatFinalStates, followupStates } from "@/lib/reportView";
import { formatUtc } from "@/lib/time";
import type { CompareResponse, ReportResponse } from "@/lib/types";

export function TechnicalDetails({
  report,
  comparison,
}: {
  report: ReportResponse;
  comparison: CompareResponse | null;
}) {
  return (
    <details className="rounded-xl border border-line bg-raised">
      <summary className="flex list-none items-center justify-between gap-4 px-5 py-4 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="block font-serif text-2xl leading-tight tracking-tight text-ink">Technical details</span>
          <span className="mt-1 block text-sm text-ink">Event ids, findings, provider evidence, and limitations.</span>
        </span>
        <ChevronDown className="details-chevron size-4 shrink-0 text-ink" aria-hidden />
      </summary>
      <div className="space-y-8 border-t border-line px-5 py-5 text-sm">
        <dl className="grid gap-3 sm:grid-cols-3">
          <Meta label="Scenario" value={report.scenario_id} />
          <Meta label="Synthetic" value={report.synthetic ? "true" : "false"} />
          <Meta label="Confirmed production bug" value={report.confirmed_production_bug ? "true" : "false"} />
          <Meta label="Pattern matched" value={report.diagnosis.pattern_matched ? "true" : "false"} />
          <Meta
            label="Known state at follow-up"
            value={followupStates(report).map((row) => `${row.eventId} ${row.state}`).join(", ") || "None"}
          />
          <Meta label="Final sequence state" value={formatFinalStates(report)} />
        </dl>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse text-left">
            <caption className="mb-2 text-left font-medium text-ink">Events</caption>
            <thead className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
              <tr>
                <th className="border-b border-line py-2 pr-3 font-medium">event_id</th>
                <th className="border-b border-line py-2 pr-3 font-medium">type</th>
                <th className="border-b border-line py-2 pr-3 font-medium">occurred_at</th>
                <th className="border-b border-line py-2 font-medium">observed_at</th>
              </tr>
            </thead>
            <tbody>
              {report.occurrence_order.map((event) => (
                <tr key={event.event_id}>
                  <td className="border-b border-line py-2 pr-3 font-mono text-xs">{event.event_id}</td>
                  <td className="border-b border-line py-2 pr-3 font-mono text-xs">{event.type}</td>
                  <td className="border-b border-line py-2 pr-3 font-mono text-xs">{formatUtc(event.occurred_at)}</td>
                  <td className="border-b border-line py-2 font-mono text-xs">{formatUtc(event.observed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h3 className="font-medium">Findings</h3>
          {report.diagnosis.findings.length === 0 ? (
            <p className="mt-2 text-muted">None.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {report.diagnosis.findings.map((finding) => (
                <li key={`${finding.followup_event_id}-${finding.reply_event_id}`} className="rounded-lg bg-paper px-3 py-3">
                  <dl className="grid gap-2 sm:grid-cols-2">
                    <Meta label="followup_event_id" value={finding.followup_event_id} />
                    <Meta label="reply_event_id" value={finding.reply_event_id} />
                    <Meta label="decision_time" value={formatUtc(finding.decision_time)} />
                    <Meta label="known_state_at_decision" value={finding.known_state_at_decision} />
                    <Meta label="reply_occurred_at" value={formatUtc(finding.reply_occurred_at)} />
                    <Meta label="reply_observed_at" value={formatUtc(finding.reply_observed_at)} />
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="font-medium">Sends after a known stop</h3>
          {report.diagnosis.sends_after_known_stop.length === 0 ? (
            <p className="mt-2 text-muted">None recorded.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {report.diagnosis.sends_after_known_stop.map((send) => (
                <li key={send.followup_event_id} className="rounded-lg bg-paper px-3 py-3">
                  <dl className="grid gap-2 sm:grid-cols-2">
                    <Meta label="followup_event_id" value={send.followup_event_id} />
                    <Meta label="decision_time" value={formatUtc(send.decision_time)} />
                    <Meta label="known_state_at_decision" value={send.known_state_at_decision} />
                    <Meta label="processed replies" value={send.processed_reply_event_ids.join(", ") || "None"} />
                    <Meta label="unprocessed replies" value={send.unprocessed_reply_event_ids.join(", ") || "None"} />
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </div>

        <LimitList title="Diagnosis limitations" items={report.diagnosis.limitations} />

        {comparison ? (
          <>
            <div>
              <h3 className="font-medium">Safeguard evidence</h3>
              <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                <Meta label="provider_condition" value={comparison.provider_condition} />
                <Meta label="ledger scope" value={comparison.ledger.scope} />
                <Meta
                  label="durable across requests"
                  value={comparison.ledger.durable_across_requests ? "true" : "false"}
                />
              </dl>
              <p className="mt-3 text-muted">{comparison.ledger.explanation}</p>
              <ul className="mt-4 space-y-4">
                {comparison.comparisons.map((item) => (
                  <li key={item.followup_event_id} className="rounded-lg bg-paper px-3 py-3">
                    <p className="font-mono text-xs">{item.followup_event_id}</p>
                    <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                      <Meta label="unguarded outcome" value={item.unguarded.outcome} />
                      <Meta label="unguarded known state" value={item.unguarded.known_state} />
                      <Meta label="guarded decision" value={item.guarded.decision} />
                      <Meta label="provider check" value={item.guarded.provider_check} />
                      <Meta label="failure kind" value={item.guarded.failure_kind ?? "none"} />
                      <Meta
                        label="simulated send recorded"
                        value={item.guarded.simulated_send_recorded ? "true" : "false"}
                      />
                      <Meta label="records consulted" value={item.guarded.records_consulted ? "true" : "false"} />
                    </dl>
                    <p className="mt-3 text-ink">{item.unguarded.explanation}</p>
                    <p className="mt-2 text-ink">{item.guarded.explanation}</p>
                    <p className="mt-3 text-muted">{item.unguarded.evidence_note}</p>
                    <p className="mt-2 text-muted">{item.guarded.evidence_note}</p>
                    {item.guarded.replies.length > 0 ? (
                      <ul className="mt-3 space-y-2">
                        {item.guarded.replies.map((reply) => (
                          <li key={reply.reply_event_id} className="font-mono text-xs text-muted">
                            {reply.reply_event_id} occurred {formatUtc(reply.occurred_at)} · visible{" "}
                            {formatUtc(reply.visible_at)} · visible at decision{" "}
                            {reply.visible_to_provider_at_decision ? "true" : "false"}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 text-muted">No reply records were returned for this check.</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
            <LimitList title="Safeguard limitations" items={comparison.limitations} />
          </>
        ) : (
          <p className="text-muted">Safeguard evidence appears here after a comparison loads.</p>
        )}
      </div>
    </details>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">{label}</dt>
      <dd className="mt-1 font-mono text-xs text-ink">{value}</dd>
    </div>
  );
}

function LimitList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="font-medium">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-2 text-muted">None.</p>
      ) : (
        <ul className="mt-2 list-disc space-y-2 pl-5 text-muted">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
