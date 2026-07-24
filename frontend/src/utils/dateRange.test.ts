import { describe, expect, it } from "vitest";
import { RANGE_OPTIONS, fromDateForRange, isTodayRange } from "./dateRange";

const FIXED_TODAY = new Date("2026-07-23T00:00:00Z");
const FIXED_TODAY_ISO = "2026-07-23";

function daysBetween(fromDateOnly: string, toDateOnly: string): number {
  const from = new Date(`${fromDateOnly}T00:00:00Z`);
  const to = new Date(`${toDateOnly}T00:00:00Z`);
  return Math.round((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
}

describe("isTodayRange", () => {
  it("is true only for 'today', routing it to the intraday endpoint instead of daily history", () => {
    expect(isTodayRange("today")).toBe(true);
    expect(isTodayRange("7d")).toBe(false);
    expect(isTodayRange("90d")).toBe(false);
    expect(isTodayRange("1y")).toBe(false);
    expect(isTodayRange("all")).toBe(false);
  });
});

describe("fromDateForRange", () => {
  it("computes a 7-day start date for 7d", () => {
    const from = fromDateForRange("7d", FIXED_TODAY);
    expect(from).toBeDefined();
    expect(daysBetween(from!, FIXED_TODAY_ISO)).toBe(7);
  });

  it("computes a 30-day start date for 30d", () => {
    const from = fromDateForRange("30d", FIXED_TODAY);
    expect(daysBetween(from!, FIXED_TODAY_ISO)).toBe(30);
  });

  it("computes a 90-day start date for 90d", () => {
    const from = fromDateForRange("90d", FIXED_TODAY);
    expect(daysBetween(from!, FIXED_TODAY_ISO)).toBe(90);
  });

  it("computes a distinct 365-day start date for 1y, not an alias of 90d", () => {
    const from90d = fromDateForRange("90d", FIXED_TODAY);
    const from1y = fromDateForRange("1y", FIXED_TODAY);
    expect(daysBetween(from1y!, FIXED_TODAY_ISO)).toBe(365);
    expect(from1y).not.toBe(from90d);
  });

  it("omits from_date entirely for 'all'", () => {
    expect(fromDateForRange("all", FIXED_TODAY)).toBeUndefined();
  });
});

describe("RANGE_OPTIONS", () => {
  it("exposes exactly the six controls: Today, 7D, 30D, 90D, 1Y, All", () => {
    expect(RANGE_OPTIONS.map((o) => o.value)).toEqual(["today", "7d", "30d", "90d", "1y", "all"]);
    expect(RANGE_OPTIONS.map((o) => o.label)).toEqual(["Today", "7D", "30D", "90D", "1Y", "All"]);
  });
});
