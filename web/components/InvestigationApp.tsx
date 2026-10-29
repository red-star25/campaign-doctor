"use client";

import { BackendNotice } from "@/components/BackendNotice";
import { EventTimeline } from "@/components/EventTimeline";
import { Header } from "@/components/Header";
import { HowItWorks } from "@/components/WhyThisHappened";
import { IncidentOverview } from "@/components/IncidentOverview";
import { IncidentPicker } from "@/components/IncidentPicker";
import { SafeguardPanel } from "@/components/SafeguardPanel";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { useInvestigation } from "@/components/useInvestigation";
import { apiBaseUrl } from "@/lib/api";
import { githubRepoUrl } from "@/lib/site";

export function InvestigationApp() {
  const api = apiBaseUrl();
  const github = githubRepoUrl();
  const {
    scenarios,
    selectedId,
    setSelectedId,
    condition,
    setCondition,
    report,
    comparison,
    listError,
    reportError,
    compareError,
    loadingList,
    loadingReport,
    loadingCompare,
    retryList,
  } = useInvestigation();

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-5xl px-5 pb-12 md:px-8">
        {loadingList && !scenarios ? (
          <p className="pt-6 text-sm text-ink">Loading the incident…</p>
        ) : null}

        {listError ? (
          <div className="pt-6">
            <BackendNotice message={listError.message} onRetry={retryList} />
          </div>
        ) : (
          <>
            <section id="overview" className="pt-5">
              {scenarios && scenarios.length !== 1 ? (
                <IncidentPicker
                  scenarios={scenarios}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              ) : null}
              {reportError ? (
                <p role="alert" className="text-sm text-copper">
                  {reportError.message}
                </p>
              ) : loadingReport && !report ? (
                <p className="text-sm text-ink">Loading the incident report…</p>
              ) : report ? (
                <IncidentOverview report={report} />
              ) : scenarios && scenarios.length > 0 ? (
                <p className="text-sm text-ink">
                  Select an incident to load its report.
                </p>
              ) : null}
            </section>

            {report ? (
              <>
                <section id="safeguard" className="pt-6">
                  <SafeguardPanel
                    condition={condition}
                    onCondition={setCondition}
                    comparison={comparison}
                    loading={loadingCompare}
                    error={compareError?.message ?? null}
                  />
                </section>
                <section
                  id="timeline"
                  className="mt-8 border-t border-line pt-8"
                >
                  <h2 className="font-serif text-2xl tracking-tight text-ink">
                    Timeline
                  </h2>
                  <div className="mt-4">
                    <EventTimeline report={report} />
                  </div>
                </section>
                <div className="mt-8 space-y-3 border-t border-line pt-8">
                  <HowItWorks report={report} />
                  <TechnicalDetails report={report} comparison={comparison} />
                </div>
              </>
            ) : null}
          </>
        )}

        <footer className="mt-8 border-t border-line py-6 text-sm text-ink">
          <p>
            Synthetic records only. No mailbox is connected, and this page does
            not send email.
          </p>
          <p className="mt-2">
            Built by Dhruv Nakum
            {github ? (
              <>
                {" "}
                ·{" "}
                <a
                  className="underline decoration-line-strong underline-offset-4"
                  href={github}
                  rel="noreferrer"
                  target="_blank"
                >
                  GitHub
                </a>
              </>
            ) : null}
          </p>
          {api ? (
            <p className="mt-2 break-all font-mono text-xs">
              API {api} ·{" "}
              <a
                className="underline decoration-line-strong underline-offset-4"
                href={`${api}/docs`}
              >
                API docs
              </a>
            </p>
          ) : (
            <p className="mt-2 font-mono text-xs">
              Set NEXT_PUBLIC_API_BASE_URL when building the frontend.
            </p>
          )}
        </footer>
      </main>
    </>
  );
}
