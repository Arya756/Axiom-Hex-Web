import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import axe from "axe-core";
import { AmbiguityRadar } from "@/components/insights/AmbiguityRadar";
import { RecurringInsightsDashboard } from "@/components/insights/RecurringInsightsDashboard";
import { AffectedContentPanel } from "@/components/admin/AffectedContentPanel";
import { SourceList } from "@/components/admin/SourceList";
import {
  SEEDED_RADAR_DATA,
  SEEDED_IMPACT_MAP,
  SEEDED_RECURRING_INSIGHTS,
  SEEDED_SOURCES,
} from "@/lib/mockData";

describe("Y5 Ambiguity Radar, Impact Analysis & Recurring Insights", () => {
  it("renders Ambiguity Radar with synthetic labels, 0% false-flag rate, counts, and evidence examples", () => {
    const onInspectImpact = vi.fn();
    render(<AmbiguityRadar data={SEEDED_RADAR_DATA} onInspectImpact={onInspectImpact} />);

    // Explicit synthetic disclosure (Y-24 / I3.5)
    expect(screen.getByText(/Synthetic Calibration History Active/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^Synthetic$/i).length).toBeGreaterThanOrEqual(4);

    // 4/4 ambiguous rules flagged, 0% false-flag rate on clear controls
    expect(screen.getByText(/Seeded ambiguous caught:\s*4\/4/i)).toBeInTheDocument();
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(screen.getByText(/0\/4 clear controls/i)).toBeInTheDocument();

    // Flagged ambiguous rules show evidence counts + concrete quote examples
    expect(screen.getAllByText(/R-07/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Confident Tone/)).toBeInTheDocument();
    expect(screen.getAllByText(/High override\/dispute rate/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/We lead compliance transformation effortlessly/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Evidence Examples/i).length).toBeGreaterThanOrEqual(1);

    // Filter tabs switch cleanly between Flagged and Clear Controls
    fireEvent.click(screen.getByRole("tab", { name: /Clear Controls/i }));
    expect(screen.queryByText("Confident Tone")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Clear Guideline \(Control\)/i).length).toBe(4);

    fireEvent.click(screen.getByRole("tab", { name: /^Flagged \(/i }));
    expect(screen.getByText("Confident Tone")).toBeInTheDocument();
    expect(screen.queryByText(/Clear Guideline \(Control\)/i)).not.toBeInTheDocument();

    // Impact quick-action from Radar card
    const inspectButtons = screen.getAllByRole("button", { name: /Check Affected Drafts/i });
    fireEvent.click(inspectButtons[0]);
    expect(onInspectImpact).toHaveBeenCalledTimes(1);
  });

  it("integrates Admin SourceList new version creation with AffectedContentPanel including supported claims", () => {
    const onSelectSource = vi.fn();
    const onCreateNewVersion = vi.fn();
    const onCheckImpact = vi.fn();
    const onRecheckItem = vi.fn();
    const onClose = vi.fn();

    render(
      <div>
        <SourceList
          sources={SEEDED_SOURCES}
          onSelectSource={onSelectSource}
          onCreateNewVersion={onCreateNewVersion}
          onCheckImpact={onCheckImpact}
        />
        <AffectedContentPanel
          impact={SEEDED_IMPACT_MAP["F-112"]}
          onRecheckItem={onRecheckItem}
          onClose={onClose}
        />
      </div>
    );

    // SourceList allows Admin to publish a new source version inline
    const newVersionButtons = screen.getAllByRole("button", { name: /Create New Version/i });
    expect(newVersionButtons.length).toBeGreaterThan(0);
    fireEvent.click(newVersionButtons[0]);
    const publishBtn = screen.getByRole("button", { name: /Publish v\d+ & Check Impact/i });
    fireEvent.click(publishBtn);
    expect(onCreateNewVersion).toHaveBeenCalledTimes(1);

    // AffectedContentPanel distinguishes Supported Claim (currently passing) from Finding Cited
    expect(screen.getByLabelText("Rule-change impact analysis panel")).toBeInTheDocument();
    expect(screen.getByText("Q1 Enterprise Growth Campaign Draft")).toBeInTheDocument();
    expect(screen.getByText("Enterprise Compliance Datasheet (Passing Draft)")).toBeInTheDocument();
    expect(screen.getByText("Supported Claim (Currently Passing)")).toBeInTheDocument();
    expect(screen.getByText(/Finding Cited/i)).toBeInTheDocument();

    const recheckButtons = screen.getAllByRole("button", { name: /Queue Re-check/i });
    fireEvent.click(recheckButtons[0]);
    expect(onRecheckItem).toHaveBeenCalledTimes(1);
  });

  it("renders Recurring Insights dashboard with synthetic disclosure and breakdown sections", () => {
    render(<RecurringInsightsDashboard data={SEEDED_RECURRING_INSIGHTS} />);

    expect(screen.getByLabelText("Recurring Insights Dashboard")).toBeInTheDocument();
    expect(screen.getByText(/Includes Synthetic History:/i)).toBeInTheDocument();
    expect(screen.getByText("Top Recurring Rule Violations")).toBeInTheDocument();
    expect(screen.getByText("Violations by Finding Type")).toBeInTheDocument();
    expect(screen.getByText("Severity Mix")).toBeInTheDocument();
    expect(screen.getByText("Most Affected Documents")).toBeInTheDocument();
    expect(screen.getByText("Product Terminology")).toBeInTheDocument();
  });

  it("has zero critical or serious WCAG violations across Y5 Radar, Impact, and Insights views", async () => {
    const { container } = render(
      <div>
        <AmbiguityRadar data={SEEDED_RADAR_DATA} />
        <AffectedContentPanel impact={SEEDED_IMPACT_MAP["F-112"]} />
        <RecurringInsightsDashboard data={SEEDED_RECURRING_INSIGHTS} />
      </div>
    );

    const results = await axe.run(container);
    const severeViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(severeViolations).toEqual([]);
  });
});
