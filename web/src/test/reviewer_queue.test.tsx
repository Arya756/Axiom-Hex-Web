import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReviewerQueue } from "../components/reviewer/ReviewerQueue";
import { SEEDED_REVISION, SEEDED_FINDINGS } from "../lib/mockData";

describe("Reviewer Queue & Actions (Y-20)", () => {
  it("displays pending approvals and enforces legal_reviewer role on claim findings", () => {
    // Current role is standard "reviewer"
    render(
      <ReviewerQueue
        revisions={[SEEDED_REVISION]}
        findings={SEEDED_FINDINGS}
        currentUserRole="reviewer"
        onApproveRevision={vi.fn()}
        onRequestChanges={vi.fn()}
        onOverrideFinding={vi.fn()}
      />
    );

    // Pending file displayed
    expect(screen.getByText(SEEDED_REVISION.file_name)).toBeInTheDocument();

    // Alert regarding mandatory legal_reviewer sign-off is shown
    expect(screen.getByText(/Mandatory Legal Reviewer Sign-Off Enforced/i)).toBeInTheDocument();

    // The approve button should be disabled for standard "reviewer"
    const approveBtn = screen.getByRole("button", { name: /Approve \(Hash-Bound\)/i });
    expect(approveBtn).toBeDisabled();
  });

  it("enables approval when active role is legal_reviewer", () => {
    const handleApprove = vi.fn();
    render(
      <ReviewerQueue
        revisions={[SEEDED_REVISION]}
        findings={SEEDED_FINDINGS}
        currentUserRole="legal_reviewer"
        onApproveRevision={handleApprove}
        onRequestChanges={vi.fn()}
        onOverrideFinding={vi.fn()}
      />
    );

    const approveBtn = screen.getByRole("button", { name: /Approve \(Hash-Bound\)/i });
    expect(approveBtn).toBeEnabled();

    fireEvent.click(approveBtn);
    expect(handleApprove).toHaveBeenCalledWith(SEEDED_REVISION.id, SEEDED_REVISION.content_hash);
  });

  it("toggles and displays revision diff", () => {
    render(
      <ReviewerQueue
        revisions={[SEEDED_REVISION]}
        findings={SEEDED_FINDINGS}
        currentUserRole="legal_reviewer"
        onApproveRevision={vi.fn()}
        onRequestChanges={vi.fn()}
        onOverrideFinding={vi.fn()}
      />
    );

    const diffToggleBtn = screen.getByRole("button", { name: /View Revision Diff/i });
    fireEvent.click(diffToggleBtn);

    // Diff view should now be visible
    expect(screen.getByText(/Tracked Change Diff: Revision v1 → v2/i)).toBeInTheDocument();
  });
});

