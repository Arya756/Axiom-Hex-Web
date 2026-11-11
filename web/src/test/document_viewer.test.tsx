import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentViewer } from "../components/viewer/DocumentViewer";
import { SEEDED_CONTENT_UNITS, SEEDED_FINDINGS } from "../lib/mockData";

describe("Document Viewer & Bounding Boxes (Y-19)", () => {
  it("renders text units and highlights identified quotes", () => {
    const handleSelect = vi.fn();
    render(
      <DocumentViewer
        units={SEEDED_CONTENT_UNITS}
        findings={SEEDED_FINDINGS}
        selectedFindingId="f_81c2"
        onSelectFinding={handleSelect}
      />
    );

    expect(screen.getByText("Welcome to Meridian Flow Platform")).toBeInTheDocument();

    // The outdated quote "10,000+ customers" is rendered inside a mark tag
    const highlight = screen.getByText("10,000+ customers");
    expect(highlight.tagName.toLowerCase()).toBe("mark");

    // Clicking the highlight triggers two-way selection
    fireEvent.click(highlight);
    expect(handleSelect).toHaveBeenCalledWith("f_81c2");
  });

  it("renders responsive SVG bounding-box overlays with viewBox 0 0 1 1", () => {
    const handleSelect = vi.fn();
    const { container } = render(
      <DocumentViewer
        units={SEEDED_CONTENT_UNITS}
        findings={SEEDED_FINDINGS}
        selectedFindingId="f_12d4"
        onSelectFinding={handleSelect}
      />
    );

    // Verify SVG overlay exists with viewBox="0 0 1 1"
    const svg = container.querySelector("svg[viewBox='0 0 1 1']");
    expect(svg).toBeInTheDocument();

    // Verify rect inside SVG
    const rect = container.querySelector("rect");
    expect(rect).toBeInTheDocument();

    // Clicking bounding box triggers two-way selection for the visual accessibility finding
    const bboxBtn = screen.getByRole("button", { name: /Select bounding box for accessibility finding/i });
    expect(bboxBtn).toBeInTheDocument();
    fireEvent.click(bboxBtn);
    expect(handleSelect).toHaveBeenCalledWith("f_12d4");
  });

  it("falls back to block-level unit highlight when character match splits across runs", () => {
    const customUnits = [
      {
        unit_id: "docx_unit_99",
        kind: "text" as const,
        text: "This whole block has complex formatting.",
        offsets: [0, 41] as [number, number],
        page: 1,
      },
    ];
    const customFindings = [
      {
        ...SEEDED_FINDINGS[0],
        span: {
          unit_id: "docx_unit_99",
          start: 5,
          end: 15,
          quote: "non_matching_split_run_quote",
        },
      },
    ];

    render(
      <DocumentViewer
        units={customUnits}
        findings={customFindings}
        selectedFindingId={customFindings[0].finding_id}
      />
    );

    // Fallback highlights the entire block
    const blockMark = screen.getByText("This whole block has complex formatting.");
    expect(blockMark.tagName.toLowerCase()).toBe("mark");
  });
});
