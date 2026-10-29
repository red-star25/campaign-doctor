import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { EventTimeline } from "@/components/EventTimeline";
import { report } from "./fixtures";

describe("EventTimeline", () => {
  it("toggles between occurrence order and observation order in UTC", async () => {
    const user = userEvent.setup();
    render(<EventTimeline report={report} />);

    expect(screen.getByText(/Times shown in UTC/)).toBeInTheDocument();
    let items = screen.getAllByRole("listitem");
    expect(items[1]).toHaveTextContent("Prospect reply");
    expect(items[1]).toHaveTextContent("09:58:00");
    expect(items[1]).toHaveTextContent("10:02:00");
    expect(items[2]).toHaveTextContent("Follow-up sent");
    expect(screen.queryByText("02:58:00")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Observation order" }));

    items = screen.getAllByRole("listitem");
    expect(items[1]).toHaveTextContent("Follow-up sent");
    expect(items[1]).toHaveTextContent("ACTIVE");
    expect(items[2]).toHaveTextContent("Prospect reply");
    expect(items[2]).toHaveTextContent("STOPPED");
    expect(screen.getByRole("list", { name: "Events in observation order" })).toBeInTheDocument();
  });
});
