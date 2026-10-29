import { act, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InvestigationApp } from "@/components/InvestigationApp";
import { useInvestigation } from "@/components/useInvestigation";
import { compareScenario, fetchReport, fetchScenarios } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import type { CompareResponse } from "@/lib/types";
import { makeComparison, report, scenarioSummary } from "./fixtures";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchScenarios: vi.fn(),
    fetchReport: vi.fn(),
    compareScenario: vi.fn(),
  };
});

describe("investigation data", () => {
  beforeEach(() => {
    vi.mocked(fetchScenarios).mockReset();
    vi.mocked(fetchReport).mockReset();
    vi.mocked(compareScenario).mockReset();
    vi.mocked(fetchScenarios).mockResolvedValue({ scenarios: [scenarioSummary] });
    vi.mocked(fetchReport).mockResolvedValue(report);
    vi.mocked(compareScenario).mockResolvedValue(makeComparison("reply_visible", "CANCEL"));
  });

  it("renders the registered incident and the report wording", async () => {
    const user = userEvent.setup();
    render(<InvestigationApp />);

    expect(await screen.findByRole("heading", { name: /Why did a follow-up send after a prospect replied/ })).toBeInTheDocument();
    const overview = document.getElementById("overview");
    expect(overview).not.toBeNull();
    const overviewView = within(overview as HTMLElement);
    expect(overviewView.getByText("09:58")).toBeInTheDocument();
    expect(overviewView.getByText("Prospect replied")).toBeInTheDocument();
    expect(overviewView.getByText("10:00")).toBeInTheDocument();
    expect(overviewView.getByText("Follow-up sent")).toBeInTheDocument();
    expect(overviewView.getByText("10:02")).toBeInTheDocument();
    expect(overviewView.getByText("Reply notification processed")).toBeInTheDocument();
    expect(overviewView.getByText(/had not processed the reply/)).toBeInTheDocument();
    expect(overviewView.getByText(/not a confirmed production bug/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delayed reply notification/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("Delayed reply notification")).toHaveLength(1);
    expect(screen.queryByText(scenarioSummary.description)).not.toBeInTheDocument();
    expect(screen.getByText(/consistent with delayed event delivery/)).toBeInTheDocument();
    expect(screen.getByText(/Treat this as a suspicion/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Provider index stale/ }));
    await waitFor(() => expect(compareScenario).toHaveBeenCalledWith("delayed_reply", "reply_not_yet_visible"));
  });

  it("explains that the API is down", async () => {
    vi.mocked(fetchScenarios).mockReset();
    vi.mocked(fetchScenarios).mockRejectedValue(
      new ApiError("This page could not reach the API at http://localhost:8000.", { unreachable: true }),
    );
    render(<InvestigationApp />);

    expect(await screen.findByRole("heading", { name: "The investigation API is not available" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/could not reach the API/);
    expect(screen.getByText(/uvicorn campaign_doctor.api.app:app/)).toBeInTheDocument();
    expect(screen.queryAllByText("Delayed reply notification")).toHaveLength(0);
  });

  it("shows an empty registry without inventing incidents", async () => {
    vi.mocked(fetchScenarios).mockResolvedValue({ scenarios: [] });
    render(<InvestigationApp />);
    expect(await screen.findByText("No incidents are registered.")).toBeInTheDocument();
  });

  it("ignores a compare response from an earlier selection", async () => {
    let resolveFirst: (value: CompareResponse) => void = () => {};
    const first = new Promise<CompareResponse>((resolve) => {
      resolveFirst = resolve;
    });
    vi.mocked(compareScenario).mockImplementationOnce(() => first);
    vi.mocked(compareScenario).mockImplementationOnce(async () => makeComparison("provider_unavailable", "DEFER"));

    const { result } = renderHook(() => useInvestigation());
    await waitFor(() => expect(compareScenario).toHaveBeenCalledTimes(1));

    act(() => result.current.setCondition("provider_unavailable"));

    await waitFor(() => expect(result.current.comparison?.provider_condition).toBe("provider_unavailable"));
    expect(result.current.comparison?.comparisons[0].guarded.decision).toBe("DEFER");

    await act(async () => {
      resolveFirst(makeComparison("reply_visible", "CANCEL"));
    });

    expect(result.current.comparison?.provider_condition).toBe("provider_unavailable");
    expect(result.current.comparison?.comparisons[0].guarded.decision).toBe("DEFER");
  });

  it("shows the decision for the latest condition after rapid switches", async () => {
    const user = userEvent.setup();
    const pending: Partial<Record<string, (value: CompareResponse) => void>> = {};
    vi.mocked(compareScenario).mockImplementation((_id: string, condition: string) => {
      return new Promise((resolve) => {
        pending[condition] = resolve;
      });
    });

    render(<InvestigationApp />);
    await waitFor(() => expect(pending.reply_visible).toBeTypeOf("function"));
    await screen.findByRole("button", { name: /Provider index stale/ });

    await user.click(screen.getByRole("button", { name: /Provider index stale/ }));
    await user.click(screen.getByRole("button", { name: /Provider unavailable/ }));
    await waitFor(() => expect(pending.provider_unavailable).toBeTypeOf("function"));
    await waitFor(() => expect(pending.reply_not_yet_visible).toBeTypeOf("function"));

    await act(async () => {
      pending.provider_unavailable?.(makeComparison("provider_unavailable", "DEFER"));
    });
    expect(await screen.findByRole("heading", { name: "DEFER" })).toBeInTheDocument();

    await act(async () => {
      pending.reply_visible?.(makeComparison("reply_visible", "CANCEL"));
      pending.reply_not_yet_visible?.(makeComparison("reply_not_yet_visible", "ALLOW"));
    });

    expect(screen.getByRole("heading", { name: "DEFER" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Provider unavailable/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("heading", { name: "ALLOW" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "CANCEL" })).not.toBeInTheDocument();
  });
});
