import { describe, expect, it } from "vitest";
import { formatUtc, formatUtcClock, formatUtcDate, formatUtcShortClock } from "@/lib/time";

describe("UTC formatting", () => {
  it("keeps the clock that arrived from the API", () => {
    expect(formatUtcClock("2026-10-27T07:30:00Z")).toBe("07:30:00");
    expect(formatUtcDate("2026-10-27T07:30:00Z")).toBe("2026-10-27");
    expect(formatUtc("2026-10-27T09:58:00Z")).toBe("2026-10-27 09:58:00 UTC");
    expect(formatUtc("2026-10-27T10:02:00+00:00")).toBe("2026-10-27 10:02:00 UTC");
    expect(formatUtcShortClock("2026-10-27T09:58:00Z")).toBe("09:58");
    expect(formatUtcShortClock("2026-10-27T09:58:30Z")).toBe("09:58:30");
  });
});
