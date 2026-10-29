"use client";

import { useState } from "react";
import { Pill, stateTone } from "@/components/Pill";
import { cn } from "@/lib/cn";
import { eventLabel } from "@/lib/labels";
import { citedEventIds } from "@/lib/reportView";
import { clocksDiffer, formatUtcClock, formatUtcDate } from "@/lib/time";
import type { EventModel, ReportResponse } from "@/lib/types";

type TimelineOrder = "occurrence" | "observation";

export function EventTimeline({ report }: { report: ReportResponse }) {
  const [order, setOrder] = useState<TimelineOrder>("occurrence");
  const cited = citedEventIds(report);
  const rows = order === "occurrence" ? occurrenceRows(report) : observationRows(report);
  const sharedDate = sharedUtcDate(rows.map((row) => row.primaryIso));

  return (
    <div>
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div aria-label="Timeline order" className="inline-flex rounded-full border border-line bg-raised p-1">
          <OrderButton
            pressed={order === "occurrence"}
            onClick={() => setOrder("occurrence")}
            label="Occurrence order"
          />
          <OrderButton
            pressed={order === "observation"}
            onClick={() => setOrder("observation")}
            label="Observation order"
          />
        </div>
        <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
          {sharedDate ? `${sharedDate} · ` : ""}Times shown in UTC
        </p>
      </div>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
        {order === "occurrence"
          ? "World order. This is when each event happened, including a reply the application may not have processed yet."
          : "Application order. This is when each event was processed. Sequence state changes only in this order."}
      </p>

      <ol aria-label={order === "occurrence" ? "Events in occurrence order" : "Events in observation order"} className="mt-6">
        {rows.map((row) => (
          <li key={`${order}-${row.event.event_id}`} className="grid grid-cols-[4.6rem_1.15rem_minmax(0,1fr)] gap-x-3 md:grid-cols-[6.5rem_1.15rem_minmax(0,1fr)]">
            <div className="pt-5 text-right">
              <time className="font-mono text-xs tabular-nums text-ink md:text-sm" dateTime={row.primaryIso}>
                {formatUtcClock(row.primaryIso)}
              </time>
              {sharedDate ? null : (
                <p className="font-mono text-[10px] text-muted">{formatUtcDate(row.primaryIso)}</p>
              )}
            </div>
            <div className="relative flex justify-center">
              <span className="absolute inset-y-0 w-px bg-line" aria-hidden />
              <span
                className={cn(
                  "relative mt-[1.35rem] size-2.5 rounded-full ring-4 ring-paper",
                  row.event.type === "PROSPECT_REPLIED" ? "bg-copper" : "bg-pine",
                )}
                aria-hidden
              />
            </div>
            <article
              className={cn(
                "my-2 rounded-xl border px-4 py-3",
                cited.has(row.event.event_id) ? "border-copper/40 bg-copper-soft/50" : "border-line bg-raised",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-medium text-ink">{eventLabel(row.event.type)}</h3>
                {cited.has(row.event.event_id) ? <Pill tone="copper">Cited in the diagnosis</Pill> : null}
              </div>
              <ClockLine event={row.event} />
              {row.state ? (
                <p className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted">Known state</span>
                  <Pill tone={stateTone(row.state.before)}>{row.state.before}</Pill>
                  <span className="text-muted">to</span>
                  <Pill tone={stateTone(row.state.after)}>{row.state.after}</Pill>
                </p>
              ) : null}
              <Metadata event={row.event} />
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}

function OrderButton({ pressed, onClick, label }: { pressed: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "rounded-full px-3 py-1.5 text-sm",
        pressed ? "bg-ink text-raised" : "text-muted hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}

function ClockLine({ event }: { event: EventModel }) {
  if (!clocksDiffer(event.occurred_at, event.observed_at)) {
    return (
      <p className="mt-2 text-sm text-muted">
        Occurred and processed{" "}
        <time dateTime={event.occurred_at}>{formatUtcClock(event.occurred_at)} UTC</time>
      </p>
    );
  }

  return (
    <p className="mt-2 text-sm text-muted">
      Occurred <time dateTime={event.occurred_at}>{formatUtcClock(event.occurred_at)} UTC</time>
      <span className="px-1.5 text-line-strong">/</span>
      Processed <time dateTime={event.observed_at}>{formatUtcClock(event.observed_at)} UTC</time>
    </p>
  );
}

function Metadata({ event }: { event: EventModel }) {
  const entries = Object.entries(event.metadata).filter(([, value]) => value !== null && value !== undefined);
  if (entries.length === 0) return null;
  return (
    <p className="mt-2 font-mono text-[11px] text-muted">
      {entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}
    </p>
  );
}

interface TimelineRow {
  event: EventModel;
  primaryIso: string;
  state: { before: string; after: string } | null;
}

function occurrenceRows(report: ReportResponse): TimelineRow[] {
  return report.occurrence_order.map((event) => ({
    event,
    primaryIso: event.occurred_at,
    state: null,
  }));
}

function observationRows(report: ReportResponse): TimelineRow[] {
  return report.observation_order.map((step) => ({
    event: step.event,
    primaryIso: step.event.observed_at,
    state: { before: step.known_state_before, after: step.known_state_after },
  }));
}

function sharedUtcDate(stamps: string[]): string | null {
  if (stamps.length === 0) return null;
  const dates = stamps.map((stamp) => formatUtcDate(stamp));
  return dates.every((date) => date === dates[0]) ? dates[0] : null;
}
