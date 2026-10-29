const UTC_STAMP = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|\+00:00)$/;

/** Format an API timestamp without using the browser timezone. */
export function formatUtc(iso: string): string {
  const match = UTC_STAMP.exec(iso);
  if (!match) return iso;
  return `${match[1]} ${match[2]}:${match[3]}:${match[4]} UTC`;
}

export function formatUtcDate(iso: string): string {
  const match = UTC_STAMP.exec(iso);
  if (!match) return iso;
  return match[1];
}

export function formatUtcClock(iso: string): string {
  const match = UTC_STAMP.exec(iso);
  if (!match) return iso;
  return `${match[2]}:${match[3]}:${match[4]}`;
}

/** Hour and minute for the opening clocks. Non-zero seconds stay visible. */
export function formatUtcShortClock(iso: string): string {
  const clock = formatUtcClock(iso);
  if (!/^\d{2}:\d{2}:\d{2}$/.test(clock)) return clock;
  return clock.endsWith(":00") ? clock.slice(0, 5) : clock;
}

export function clocksDiffer(occurredAt: string, observedAt: string): boolean {
  return occurredAt !== observedAt;
}
