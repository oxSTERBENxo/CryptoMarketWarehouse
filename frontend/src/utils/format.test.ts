import { describe, expect, it } from "vitest";
import { formatIsoDate } from "./format";

describe("formatIsoDate", () => {
  it("formats a full ISO datetime string as a date only", () => {
    expect(formatIsoDate("2026-07-16T00:00:00Z")).toBe("Jul 16, 2026");
  });

  it("returns the placeholder for null/undefined", () => {
    expect(formatIsoDate(null)).toBe("—");
    expect(formatIsoDate(undefined)).toBe("—");
  });

  it("returns the placeholder for an unparseable string", () => {
    expect(formatIsoDate("not-a-date")).toBe("—");
  });
});
