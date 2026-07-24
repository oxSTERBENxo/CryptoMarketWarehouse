import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  isThemePreference,
  readStoredThemePreference,
  resolveTheme,
  storeThemePreference,
} from "./theme";

function mockMatchMedia(dark: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("dark") ? dark : !dark,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  );
  window.matchMedia = globalThis.matchMedia as typeof window.matchMedia;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
});

describe("isThemePreference", () => {
  it("accepts only light/dark/system", () => {
    expect(isThemePreference("light")).toBe(true);
    expect(isThemePreference("dark")).toBe(true);
    expect(isThemePreference("system")).toBe(true);
    expect(isThemePreference("solarized")).toBe(false);
    expect(isThemePreference(null)).toBe(false);
    expect(isThemePreference(42)).toBe(false);
  });
});

describe("resolveTheme", () => {
  it("passes through explicit light/dark", () => {
    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("resolves system against prefers-color-scheme: dark", () => {
    mockMatchMedia(true);
    expect(resolveTheme("system")).toBe("dark");
  });

  it("resolves system against prefers-color-scheme: light", () => {
    mockMatchMedia(false);
    expect(resolveTheme("system")).toBe("light");
  });
});

describe("stored preference", () => {
  it("round-trips through localStorage", () => {
    storeThemePreference("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readStoredThemePreference()).toBe("dark");
  });

  it("falls back to system for missing storage", () => {
    expect(readStoredThemePreference()).toBe("system");
  });

  it("falls back to system for invalid stored values", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "neon");
    expect(readStoredThemePreference()).toBe("system");
  });
});

describe("applyTheme", () => {
  it("sets data-theme and color-scheme on the document root", () => {
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");

    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });
});
