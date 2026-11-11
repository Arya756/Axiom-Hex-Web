import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FindingCard } from "../components/findings/FindingCard";
import { SEEDED_FINDINGS } from "../lib/mockData";

describe("Finding Cards (Y-18)", () => {
  const outdatedFinding = SEEDED_FINDINGS.find((f) => f.type === "outdated")!;
  const assistedFinding = SEEDED_FINDINGS.find((f) => f.disclosure.assisted)!;

  it("renders evidence-first layout showing verified citation receipt before explanation", () => {
    render(<FindingCard finding={outdatedFinding} />);

    // Verified Evidence Block
    expect(screen.getByText(/Verified Evidence & Citation Receipt/i)).toBeInTheDocument();
    expect(screen.getByText(/F-112/i)).toBeInTheDocument();
    expect(screen.getByText(/25,000\+ customers/i)).toBeInTheDocument();

    // Verdict explanation
    expect(
      screen.getByText(/This figure matches an earlier approved fact/i)
    ).toBeInTheDocument();
  });

  it("renders method, confidence, and 'Assisted' badge when appropriate", () => {
    render(<FindingCard finding={assistedFinding} />);

    expect(screen.getByText("Assisted")).toBeInTheDocument();
    expect(screen.getByText(/88% conf/i)).toBeInTheDocument();
    expect(screen.getByText("llm assisted")).toBeInTheDocument();
  });

  it("renders tracked-change diff for suggested fix", () => {
    render(<FindingCard finding={outdatedFinding} />);

    expect(screen.getByText(/Suggested Tracked-Change Fix/i)).toBeInTheDocument();
    // Diff should show addition of 25
    expect(screen.getByText(/\+25/i)).toBeInTheDocument();
  });

  it("triggers accept action on button click", () => {
    const handleDecision = vi.fn();
    render(<FindingCard finding={outdatedFinding} onDecision={handleDecision} />);

    const acceptBtn = screen.getByRole("button", { name: /Accept Fix/i });
    fireEvent.click(acceptBtn);

    expect(handleDecision).toHaveBeenCalledWith(outdatedFinding.finding_id, "accept");
  });

  it("enforces mandatory written reason for disputes", () => {
    const handleDecision = vi.fn();
    render(<FindingCard finding={outdatedFinding} onDecision={handleDecision} />);

    // Click dispute button to open prompt
    const disputeBtn = screen.getByRole("button", { name: /Dispute/i });
    fireEvent.click(disputeBtn);

    const submitBtn = screen.getByRole("button", { name: /Submit Dispute/i });

    // Empty reason should trigger validation error and not call handleDecision
    const reasonTextarea = screen.getByLabelText(/Mandatory Dispute Reason/i);
    fireEvent.change(reasonTextarea, { target: { value: "   " } });
    fireEvent.click(submitBtn);

    expect(handleDecision).not.toHaveBeenCalled();
    expect(screen.getByText(/A written reason is required to dispute this finding/i)).toBeInTheDocument();

    // With written justification
    fireEvent.change(reasonTextarea, { target: { value: "Statistical context is bounded by Q4 2024 cutoff." } });
    fireEvent.click(submitBtn);

    expect(handleDecision).toHaveBeenCalledWith(
      outdatedFinding.finding_id,
      "dispute",
      "Statistical context is bounded by Q4 2024 cutoff."
    );
  });
});
