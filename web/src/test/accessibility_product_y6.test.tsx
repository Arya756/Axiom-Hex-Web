import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import axe from "axe-core";
import Home from "@/app/page";
import { FindingCard } from "@/components/findings/FindingCard";
import { UploadDrawer } from "@/components/creator/UploadDrawer";
import { ReviewerQueue } from "@/components/reviewer/ReviewerQueue";
import { SEEDED_FINDINGS } from "@/lib/mockData";

describe("Y6 Accessibility & Product Checks (PRD §5.4 & Y-27)", () => {
  it("displays explicit 'Assisted' and 'Assisted Fix' badges on generated findings and fixes", () => {
    const assistedFinding = SEEDED_FINDINGS.find((f) => f.disclosure.assisted)!;
    render(<FindingCard finding={assistedFinding} />);

    expect(screen.getByText("Assisted")).toBeInTheDocument();
    expect(screen.getByText("Assisted Fix")).toBeInTheDocument();
  });

  it("supports keyboard navigation across finding cards (Enter, Space, ArrowDown, ArrowUp)", () => {
    const onSelect = vi.fn();
    const onNavigate = vi.fn();
    const first = SEEDED_FINDINGS[0];

    render(
      <FindingCard
        finding={first}
        isSelected={false}
        onSelect={onSelect}
        onNavigate={onNavigate}
      />
    );

    const card = screen.getByRole("region", {
      name: new RegExp(`Finding ${first.finding_id}:`, "i"),
    });
    expect(card).toHaveAttribute("tabIndex", "0");

    fireEvent.keyDown(card, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(first);

    fireEvent.keyDown(card, { key: " " });
    expect(onSelect).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(card, { key: "ArrowDown" });
    expect(onNavigate).toHaveBeenCalledWith("next");

    fireEvent.keyDown(card, { key: "ArrowUp" });
    expect(onNavigate).toHaveBeenCalledWith("prev");
  });

  it("moves selection across FindingCards via ArrowDown/ArrowUp in workspace Home", () => {
    render(<Home />);

    const cards = screen.getAllByRole("region", { name: /^Finding /i });
    expect(cards.length).toBeGreaterThanOrEqual(2);

    cards[0].focus();
    fireEvent.keyDown(cards[0], { key: "ArrowDown" });
    expect(cards[1]).toHaveAttribute("aria-current", "true");

    fireEvent.keyDown(cards[1], { key: "ArrowUp" });
    expect(cards[0]).toHaveAttribute("aria-current", "true");
  });

  it("renders visible loading, empty, and error UI states", () => {
    // 1. Loading & Failed Error State in UploadDrawer
    const { rerender, unmount: unmountDrawer } = render(
      <UploadDrawer
        onUploadSuccess={vi.fn()}
        runProgress={{
          status: "running",
          progress: 45,
          active_step: "Hybrid BM25 + pgvector retrieval",
          findings_count: 1,
        }}
      />
    );
    expect(screen.getByRole("status")).toHaveTextContent(/45%/i);

    rerender(
      <UploadDrawer
        onUploadSuccess={vi.fn()}
        runProgress={{
          status: "failed",
          progress: 45,
          active_step: "Unreadable document",
          findings_count: 0,
        }}
      />
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/Pre-check run failed/i);

    // Unsupported file upload error alert (without simultaneous failed progress alert)
    rerender(<UploadDrawer onUploadSuccess={vi.fn()} />);
    const fileInput = document.getElementById("file-upload-input") as HTMLInputElement;
    const badFile = new File(["binary"], "malware.exe", { type: "application/octet-stream" });
    fireEvent.change(fileInput, { target: { files: [badFile] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/Unsupported file type/i);
    unmountDrawer();

    // 2. Empty State in ReviewerQueue
    const { unmount: unmountQueue } = render(
      <ReviewerQueue
        revisions={[]}
        findings={[]}
        currentUserRole="reviewer"
        onApproveRevision={vi.fn()}
        onRequestChanges={vi.fn()}
        onOverrideFinding={vi.fn()}
      />
    );
    expect(screen.getByText(/No revisions pending approval/i)).toBeInTheDocument();
    unmountQueue();

    // 3. Empty State + Reset Filter recovery in Home
    render(<Home />);
    fireEvent.click(screen.getByRole("tab", { name: /^resolved$/i }));
    expect(screen.getByText(/No findings match the selected filter/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Reset Filter/i }));
    expect(screen.getAllByRole("region", { name: /^Finding /i }).length).toBeGreaterThan(0);
  });

  it("passes axe-core WCAG 2.2 AA structural/ARIA check across Home workspace", async () => {
    const { container } = render(<Home />);
    // Avoid multi-worker node-canvas Pango crashes on Linux CI while verifying full WCAG 2.2 AA DOM/ARIA rules
    const results = await axe.run(container, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
      },
      rules: { "color-contrast": { enabled: false } },
    });
    const severeViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(severeViolations).toEqual([]);
  });
});
