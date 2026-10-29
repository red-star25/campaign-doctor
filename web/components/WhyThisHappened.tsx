import { ChevronDown } from "lucide-react";
import type { ReportResponse } from "@/lib/types";

export function HowItWorks({ report }: { report: ReportResponse }) {
  return (
    <details className="rounded-xl border border-line bg-raised">
      <summary className="flex list-none items-center justify-between gap-4 px-5 py-4 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="block font-serif text-2xl leading-tight tracking-tight text-ink">How it works</span>
          <span className="mt-1 block text-sm text-ink">
            Two clocks, a sequence that updates late, and a check that can still miss a reply.
          </span>
        </span>
        <ChevronDown className="details-chevron size-4 shrink-0 text-ink" aria-hidden />
      </summary>
      <div className="space-y-4 border-t border-line px-5 py-4 text-sm leading-relaxed text-ink">
        <p>
          Occurrence time is when something happened. Processing time is when this application handled the
          notification. The sequence stays in its previous state until a reply is processed, so a follow-up can go out
          while a reply is already sitting unseen.
        </p>
        <p>
          A pre-send check asks the provider whether a reply is already visible. Cancel means the check saw the reply
          and the hypothetical follow-up was prevented. Allow means the provider&apos;s information was stale and a
          simulated send was permitted. Defer means the provider was unavailable and the simulated send was postponed.
          None of those delivers email. The recorded send is the follow-up already in the synthetic log.
        </p>
        <p>
          A stale index, a timeout, or a reply that arrives after an allow can still leave a gap. The safeguard does
          not guarantee that an unwanted follow-up never goes out.
        </p>
        <p>{report.diagnosis.summary}</p>
        <p>{report.diagnosis.certainty}</p>
      </div>
    </details>
  );
}
