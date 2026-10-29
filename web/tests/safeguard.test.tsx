import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SafeguardPanel } from "@/components/SafeguardPanel";
import { makeComparison } from "./fixtures";

describe("SafeguardPanel", () => {
  it("labels ALLOW as simulated permission and asks for the selected condition", async () => {
    const user = userEvent.setup();
    const onCondition = vi.fn();
    render(
      <SafeguardPanel
        condition="reply_not_yet_visible"
        onCondition={onCondition}
        comparison={makeComparison("reply_not_yet_visible", "ALLOW")}
        loading={false}
        error={null}
      />,
    );

    expect(screen.getByRole("heading", { name: "ALLOW" })).toBeInTheDocument();
    expect(
      screen.getByText("Provider information was stale; a simulated send was permitted. No email was delivered."),
    ).toBeInTheDocument();
    expect(screen.getByText("A simulated send was recorded. No email was delivered.")).toBeInTheDocument();
    expect(screen.getByText(/already in the synthetic event log/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Provider unavailable/ }));
    expect(onCondition).toHaveBeenCalledWith("provider_unavailable");
  });

  it("shows a cancel as a prevented follow-up", () => {
    render(
      <SafeguardPanel
        condition="reply_visible"
        onCondition={vi.fn()}
        comparison={makeComparison("reply_visible", "CANCEL")}
        loading={false}
        error={null}
      />,
    );

    expect(screen.getByRole("heading", { name: "CANCEL" })).toBeInTheDocument();
    expect(screen.getByText("Safeguard detected the reply. No email was sent.")).toBeInTheDocument();
    expect(screen.getByText("No simulated send was recorded.")).toBeInTheDocument();
  });
});
