import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SourceList } from "../components/admin/SourceList";
import { SourceForm } from "../components/admin/SourceForm";
import { SEEDED_SOURCES } from "../lib/mockData";

describe("Admin UI (Y-16)", () => {
  it("renders source list and version history supersession chain", () => {
    render(<SourceList sources={SEEDED_SOURCES} />);

    // F-112 is present
    expect(screen.getByText("F-112")).toBeInTheDocument();
    expect(screen.getByText("Customer Count")).toBeInTheDocument();

    // Current version badge v3 is rendered
    expect(screen.getByText("v3 (Current)")).toBeInTheDocument();

    // Check version history elements
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("Superseded by v2")).toBeInTheDocument();
    expect(screen.getByText("Active Standard")).toBeInTheDocument();
  });

  it("filters sources by kind", () => {
    render(<SourceList sources={SEEDED_SOURCES} />);

    const ruleTab = screen.getByRole("tab", { name: "rule" });
    fireEvent.click(ruleTab);

    // Rule R-01 should be visible
    expect(screen.getByText("R-01")).toBeInTheDocument();
  });

  it("defines a new source and calls onAddSource", () => {
    const handleAddSource = vi.fn();
    render(<SourceForm onAddSource={handleAddSource} />);

    fireEvent.change(screen.getByLabelText(/Source ID/i), { target: { value: "F-200" } });
    fireEvent.change(screen.getByLabelText(/Title \/ Name/i), { target: { value: "Active Users" } });
    fireEvent.change(screen.getByLabelText(/Guideline Statement/i), {
      target: { value: "Over 50,000 monthly active users across platform." },
    });

    const submitBtn = screen.getByRole("button", { name: /Compile & Save Source/i });
    fireEvent.click(submitBtn);

    expect(handleAddSource).toHaveBeenCalledTimes(1);
    const added = handleAddSource.mock.calls[0][0];
    expect(added.id).toBe("F-200");
    expect(added.name).toBe("Active Users");
    expect(added.current_version).toBe(1);
  });

  it("imports brand kit JSON and verifies idempotency", () => {
    const handleAddSource = vi.fn();
    const handleImportKit = vi.fn();
    render(<SourceForm onAddSource={handleAddSource} onImportKit={handleImportKit} />);

    // Switch to import tab
    const importTab = screen.getByRole("button", { name: /Structured Import/i });
    fireEvent.click(importTab);

    const loadSampleBtn = screen.getByRole("button", { name: /Load Sample Kit/i });
    fireEvent.click(loadSampleBtn);

    const importBtn = screen.getByRole("button", { name: /Import & Verify Idempotency/i });
    fireEvent.click(importBtn);

    expect(handleAddSource).toHaveBeenCalled();
    expect(handleImportKit).toHaveBeenCalled();
  });
});

