import { afterEach, describe, expect, it, vi } from "vitest";
import { LANGUAGE_STORAGE_KEY } from "./index";

/** First-launch language detection runs at i18n module load, so each case re-imports a fresh
 * module graph with a stubbed navigator.language and controlled localStorage. */
async function importFreshI18n(browserLanguage: string, stored?: string) {
  vi.resetModules();
  localStorage.clear();
  if (stored !== undefined) localStorage.setItem(LANGUAGE_STORAGE_KEY, stored);
  vi.stubGlobal("navigator", { ...navigator, language: browserLanguage });
  const mod = await import("./index");
  return mod;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
  localStorage.clear();
});

describe("first-launch browser-language detection", () => {
  it("picks Macedonian when the browser language starts with mk", async () => {
    const mod = await importFreshI18n("mk-MK");
    expect(mod.initialLanguage).toBe("mk");
  });

  it("picks English for any other browser language", async () => {
    const mod = await importFreshI18n("de-DE");
    expect(mod.initialLanguage).toBe("en");
  });

  it("respects a saved preference over the browser language", async () => {
    const mod = await importFreshI18n("mk-MK", "en");
    expect(mod.initialLanguage).toBe("en");
  });

  it("ignores an invalid saved preference and falls back to detection", async () => {
    const mod = await importFreshI18n("mk-MK", "klingon");
    expect(mod.initialLanguage).toBe("mk");
  });
});
