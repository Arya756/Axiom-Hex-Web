import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { UploadDrawer } from "../components/creator/UploadDrawer";
import { IntentCardDrawer } from "../components/creator/IntentCardDrawer";
import { INITIAL_INTENT_CARD } from "../lib/mockData";

describe("Creator Upload & Intent Card (Y-17)", () => {
  it("renders upload drawer and handles sensitivity policy selection", () => {
    const handleUploadSuccess = vi.fn();
    render(<UploadDrawer onUploadSuccess={handleUploadSuccess} />);

    // Check sensitivity options exist
    expect(screen.getByRole("radio", { name: /Public/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Internal/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Restricted/i })).toBeInTheDocument();

    // Select Restricted (0 external calls)
    const restrictedRadio = screen.getByRole("radio", { name: /Restricted/i });
    fireEvent.click(restrictedRadio);
    expect(restrictedRadio).toHaveAttribute("aria-checked", "true");
  });

  it("displays review run progress telemetry when active", () => {
    render(
      <UploadDrawer
        onUploadSuccess={vi.fn()}
        runProgress={{
          status: "running",
          progress: 60,
          active_step: "Deterministic terminology & temporal fact ledger checks",
          findings_count: 2,
        }}
      />
    );

    expect(screen.getByText(/Review Run: RUNNING/i)).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText(/2 findings identified/i)).toBeInTheDocument();
  });

  it("renders non-blocking editable Intent Card drawer and saves updates", () => {
    const handleSaveIntent = vi.fn();
    const handleRerun = vi.fn();

    render(
      <IntentCardDrawer
        intentCard={INITIAL_INTENT_CARD}
        onSaveIntentCard={handleSaveIntent}
        onRerunConstrainedFixes={handleRerun}
      />
    );

    // Initial collapsed preview
    expect(screen.getByText("Intent Card (Constrained Fixes)")).toBeInTheDocument();
    expect(screen.getByText(/Auto-extracted/i)).toBeInTheDocument();

    // Open drawer
    const toggleBtn = screen.getByRole("button", { name: /Intent Card/i });
    fireEvent.click(toggleBtn);

    // Purpose input should now be visible
    const purposeInput = screen.getByLabelText(/Content Purpose/i);
    expect(purposeInput).toHaveValue(INITIAL_INTENT_CARD.purpose);

    // Edit purpose
    fireEvent.change(purposeInput, { target: { value: "Updated Enterprise Campaign" } });

    // Save and re-run
    const saveBtn = screen.getByRole("button", { name: /Save & Re-run/i });
    fireEvent.click(saveBtn);

    expect(handleSaveIntent).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: "Updated Enterprise Campaign",
      })
    );
    expect(handleRerun).toHaveBeenCalled();
  });
});

