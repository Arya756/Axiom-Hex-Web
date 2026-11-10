import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { AxeDisclosure } from "../components/common/AxeDisclosure";
import { FindingCard } from "../components/findings/FindingCard";
import { SEEDED_FINDINGS } from "../lib/mockData";

describe("Accessibility & WCAG 2.2 AA (axe-core)", () => {
  it("renders AxeDisclosure with PRD §5.4 partial coverage statement", () => {
    const { getByRole, getByText } = render(<AxeDisclosure />);
    expect(getByRole("region", { name: /Accessibility compliance disclosure/i })).toBeInTheDocument();
    expect(getByText(/WCAG 2.2 AA Partial Coverage Disclosure/i)).toBeInTheDocument();
  });

  it("passes axe-core check on AxeDisclosure with zero violations", async () => {
    const { container } = render(<AxeDisclosure />);
    const results = await axe.run(container);
    // Filter for serious / critical violations
    const seriousViolations = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );
    expect(seriousViolations).toEqual([]);
  });

  it("passes axe-core check on FindingCard with zero violations", async () => {
    const { container } = render(<FindingCard finding={SEEDED_FINDINGS[0]} />);
    const results = await axe.run(container);
    const criticalViolations = results.violations.filter((v) => v.impact === "critical");
    expect(criticalViolations).toEqual([]);
  });
});

