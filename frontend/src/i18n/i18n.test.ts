import { afterEach, beforeEach, describe, expect, it } from "vitest";
import i18n, { LANGUAGE_STORAGE_KEY, isSupportedLanguage, persistLanguage } from "./index";
import en from "./en.json";
import mk from "./mk.json";
import { formatDate, formatNumber, formatUsd } from "../utils/format";

beforeEach(async () => {
  localStorage.clear();
  await i18n.changeLanguage("en");
});

afterEach(async () => {
  localStorage.clear();
  await i18n.changeLanguage("en");
});

describe("isSupportedLanguage", () => {
  it("accepts en and mk only", () => {
    expect(isSupportedLanguage("en")).toBe(true);
    expect(isSupportedLanguage("mk")).toBe(true);
    expect(isSupportedLanguage("de")).toBe(false);
    expect(isSupportedLanguage(null)).toBe(false);
  });
});

describe("persistLanguage", () => {
  it("writes the selection to localStorage", () => {
    persistLanguage("mk");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("mk");
  });
});

describe("translations", () => {
  it("serves English strings by default", () => {
    expect(i18n.t("nav.dashboard")).toBe("Dashboard");
    expect(i18n.t("common.retry")).toBe("Retry");
  });

  it("serves Macedonian strings after switching", async () => {
    await i18n.changeLanguage("mk");
    expect(i18n.t("nav.dashboard")).toBe("Почетна");
    expect(i18n.t("common.retry")).toBe("Обиди се пак");
  });

  it("updates <html lang> when the language changes", async () => {
    await i18n.changeLanguage("mk");
    expect(document.documentElement.lang).toBe("mk");
    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("falls back to English for keys missing from the active language", async () => {
    // A dedicated namespace, so this never mutates the shared "translation" resource objects
    // that the key-parity test below reads.
    i18n.addResource("en", "fallback-test", "fallbackOnly", "fallback value");
    await i18n.changeLanguage("mk");
    expect(i18n.t("fallback-test:fallbackOnly")).toBe("fallback value");
  });

  function collectKeys(node: Record<string, unknown>, prefix = ""): string[] {
    return Object.entries(node).flatMap(([key, value]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === "object") return collectKeys(value as Record<string, unknown>, path);
      return [path];
    });
  }

  it("has an identical key set in en.json and mk.json (no missing translations)", () => {
    const enKeys = collectKeys(en).sort();
    const mkKeys = collectKeys(mk).sort();
    expect(mkKeys).toEqual(enKeys);
  });
});

describe("locale-aware formatting", () => {
  it("formats numbers with en-US separators in English", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatUsd(65160)).toBe("$65,160.00");
  });

  it("formats numbers and dates per the Macedonian locale after switching", async () => {
    await i18n.changeLanguage("mk");
    const expectedNumber = new Intl.NumberFormat("mk-MK").format(1234567);
    expect(formatNumber(1234567)).toBe(expectedNumber);

    const expectedDate = new Intl.DateTimeFormat("mk-MK", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date("2026-07-22T00:00:00"));
    expect(formatDate("2026-07-22")).toBe(expectedDate);
  });
});
