import { formatUtcDate, formatUtcShortClock } from "@/lib/time";
import type { ReportResponse } from "@/lib/types";

export function IncidentOverview({ report }: { report: ReportResponse }) {
  const finding = report.diagnosis.findings[0];
  const showQuestion = Boolean(finding && report.diagnosis.pattern_matched);

  return (
    <div>
      <p className="text-sm text-ink">{report.name}</p>
      <h2 className="mt-1 max-w-3xl font-serif text-[1.85rem] leading-tight tracking-tight text-ink">
        {showQuestion ? "Why did a follow-up send after a prospect replied?" : report.diagnosis.summary}
      </h2>

      {finding && showQuestion ? (
        <>
          <p className="mt-3 font-mono text-xs tracking-wide text-ink">{formatUtcDate(finding.decision_time)} UTC</p>
          <ol className="mt-3 grid gap-4 sm:grid-cols-3">
            <Clock iso={finding.reply_occurred_at} label="Prospect replied" />
            <Clock iso={finding.decision_time} label="Follow-up sent" />
            <Clock iso={finding.reply_observed_at} label="Reply notification processed" />
          </ol>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-ink">
            {finding.known_state_at_decision === "ACTIVE" ? (
              <>
                The automation had not processed the reply when the follow-up was sent, so the known state was still{" "}
                {finding.known_state_at_decision}.
              </>
            ) : (
              <>The known state at the follow-up was {finding.known_state_at_decision}.</>
            )}{" "}
            This is a suspicion about a synthetic log, not a confirmed production bug.
          </p>
          {report.diagnosis.findings.length > 1 ? (
            <p className="mt-2 text-sm text-ink">Other flagged follow-ups are in the technical details.</p>
          ) : null}
        </>
      ) : (
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink">{report.diagnosis.certainty}</p>
      )}
    </div>
  );
}

function Clock({ iso, label }: { iso: string; label: string }) {
  return (
    <li className="border-t border-line-strong pt-2 sm:border-t-0 sm:border-l sm:pt-0 sm:pl-4 sm:first:border-l-0 sm:first:pl-0">
      <time className="font-mono text-xl tabular-nums text-ink" dateTime={iso}>
        {formatUtcShortClock(iso)}
      </time>
      <p className="mt-1 text-sm text-ink">{label}</p>
    </li>
  );
}
