import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FrequencyChart from "./FrequencyChart";
import GapChart from "./GapChart";
import AverageChart from "./AverageChart";
import DistributionChart from "./DistributionChart";

const freqRows = [
  { number: 1, count: 14 },
  { number: 2, count: 11 },
  { number: 3, count: 9 },
];

const gapRows = [
  { number: 1, count: 14, min_gap: 1, max_gap: 12, avg_gap: 4.5 },
  { number: 2, count: 11, min_gap: 0, max_gap: 8, avg_gap: 2.3 },
  { number: 3, count: 9, min_gap: 2, max_gap: 15, avg_gap: 6.1 },
];

const avgSeries = [
  { series_key: "sum", mean: 42.5, non_null_count: 90 },
  { series_key: "pairs", mean: 3.2, non_null_count: 90 },
];

const distributionRows = [
  { subject: "number-1", value: "0.32" },
  { subject: "number-2", value: 0.24 },
];

describe("FrequencyChart", () => {
  it("renders an accessible img with sample data", () => {
    render(<FrequencyChart rows={freqRows} />);
    const chart = screen.getByRole("img", {
      name: /frequency distribution per number/i,
    });
    expect(chart).toBeInTheDocument();
  });

  it("does not crash on empty rows", () => {
    render(<FrequencyChart rows={[]} />);
    expect(screen.getByRole("img", { name: /frequency distribution/i })).toBeInTheDocument();
  });
});

describe("GapChart", () => {
  it("renders an accessible img with sample data", () => {
    render(<GapChart rows={gapRows} />);
    const chart = screen.getByRole("img", {
      name: /gap analysis per number/i,
    });
    expect(chart).toBeInTheDocument();
  });

  it("does not crash on null gaps or empty rows", () => {
    const withNulls = [{ number: 4, count: 5, min_gap: null, max_gap: null, avg_gap: null }];
    const { rerender } = render(<GapChart rows={withNulls} />);
    expect(screen.getByRole("img", { name: /gap analysis/i })).toBeInTheDocument();
    rerender(<GapChart rows={[]} />);
    expect(screen.getByRole("img", { name: /gap analysis/i })).toBeInTheDocument();
  });
});

describe("AverageChart", () => {
  it("renders an accessible img with sample data", () => {
    render(<AverageChart series={avgSeries} />);
    const chart = screen.getByRole("img", {
      name: /average gap per series/i,
    });
    expect(chart).toBeInTheDocument();
  });

  it("does not crash on null means or empty series", () => {
    const withNulls = [{ series_key: "empty", mean: null, non_null_count: 0 }];
    const { rerender } = render(<AverageChart series={withNulls} />);
    expect(screen.getByRole("img", { name: /average gap per series/i })).toBeInTheDocument();
    rerender(<AverageChart series={[]} />);
    expect(screen.getByRole("img", { name: /average gap per series/i })).toBeInTheDocument();
  });
});

describe("DistributionChart", () => {
  it("renders an accessible img with string and numeric values", () => {
    render(<DistributionChart rows={distributionRows} />);
    const chart = screen.getByRole("img", {
      name: /probability distribution per subject/i,
    });
    expect(chart).toBeInTheDocument();
  });

  it("does not crash on non-numeric values or empty rows", () => {
    const bad = [
      { subject: "number-1", value: "not-a-number" },
      { subject: "number-2", value: "" },
    ];
    const { rerender } = render(<DistributionChart rows={bad} />);
    expect(screen.getByRole("img", { name: /probability distribution/i })).toBeInTheDocument();
    rerender(<DistributionChart rows={[]} />);
    expect(screen.getByRole("img", { name: /probability distribution/i })).toBeInTheDocument();
  });
});
