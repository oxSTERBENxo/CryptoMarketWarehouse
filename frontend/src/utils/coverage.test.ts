import { describe, expect, it } from "vitest";
import { buildCoverageMessage, rangeRequestedDays } from "./coverage";

const summary = {
  minPrice: 100,
  maxPrice: 200,
  avgPrice: 150,
  percentChange: 5,
  observationCount: 80,
  firstLabel: "Apr 25",
  latestLabel: "Jul 23",
};

describe("rangeRequestedDays", () => {
  it("returns a distinct 365 for 1y and 90 for 90d", () => {
    expect(rangeRequestedDays("90d")).toBe(90);
    expect(rangeRequestedDays("1y")).toBe(365);
    expect(rangeRequestedDays("1y")).not.toBe(rangeRequestedDays("90d"));
  });

  it("returns null for 'all' (no fixed requested window)", () => {
    expect(rangeRequestedDays("all")).toBeNull();
  });
});

describe("buildCoverageMessage", () => {
  it("marks partial coverage honestly when the database has fewer than 365 daily observations for 1y", () => {
    const message = buildCoverageMessage(false, "1y", 80, summary);
    expect(message).toContain("80");
    expect(message).toContain("365");
    expect(message.toLowerCase()).toContain("only");
  });

  it("does not claim full 1y coverage when 90d and 1y happen to return the same 90 rows", () => {
    const full90d = buildCoverageMessage(false, "90d", 90, summary);
    const partial1y = buildCoverageMessage(false, "1y", 90, summary);
    expect(full90d).not.toContain("365");
    expect(partial1y).toContain("365");
    expect(partial1y).not.toBe(full90d);
  });

  it("reports full coverage once 365 daily observations exist for 1y", () => {
    const message = buildCoverageMessage(false, "1y", 365, summary);
    expect(message.toLowerCase()).toContain("365");
    expect(message.toLowerCase()).not.toContain("only");
  });

  it("shows an empty-state message for Today with zero intraday observations", () => {
    const message = buildCoverageMessage(true, "today", 0, null);
    expect(message.toLowerCase()).toContain("no intraday observations");
  });

  it("does not crash when summarizing Today with observations but a null summary", () => {
    expect(() => buildCoverageMessage(true, "today", 5, null)).not.toThrow();
  });

  it("omits a requested-day ceiling entirely for 'all'", () => {
    const message = buildCoverageMessage(false, "all", 90, summary);
    expect(message.toLowerCase()).toContain("all");
    expect(message).not.toContain("365");
  });
});
