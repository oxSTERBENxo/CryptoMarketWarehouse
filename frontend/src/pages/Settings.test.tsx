import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n, { LANGUAGE_STORAGE_KEY } from "../i18n";
import { THEME_STORAGE_KEY } from "../theme/theme";
import { ThemeProvider } from "../contexts/ThemeContext";
import { Settings } from "./Settings";

function mockMatchMedia(dark = false) {
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

function renderSettings() {
  return render(
    <ThemeProvider>
      <Settings />
    </ThemeProvider>
  );
}

beforeEach(async () => {
  mockMatchMedia(false);
  localStorage.clear();
  await i18n.changeLanguage("en");
});

afterEach(async () => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.style.colorScheme = "";
  await i18n.changeLanguage("en");
});

describe("Settings — appearance", () => {
  it("offers Light, Dark, and System options with System selected by default", () => {
    renderSettings();
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "System" })).toHaveAttribute("aria-checked", "true");
  });

  it("applies and persists Dark", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("applies and persists Light", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("radio", { name: "Light" }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("System follows the OS dark preference", () => {
    mockMatchMedia(true);
    renderSettings();
    fireEvent.click(screen.getByRole("radio", { name: "System" }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
  });

  it("restores a persisted preference on mount", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderSettings();

    expect(screen.getByRole("radio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("falls back to System when storage holds an invalid value", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "hotdog-stand");
    renderSettings();

    expect(screen.getByRole("radio", { name: "System" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("Settings — language", () => {
  it("switches the whole UI to Macedonian, persists it, and updates <html lang>", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("radio", { name: "Македонски" }));

    expect(i18n.language).toBe("mk");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("mk");
    expect(document.documentElement.lang).toBe("mk");
    // The page's own chrome re-renders in Macedonian.
    expect(screen.getByText("Поставки")).toBeInTheDocument();
    expect(screen.getByText("Изглед")).toBeInTheDocument();
  });

  it("switches back to English and persists it", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("radio", { name: "Македонски" }));
    fireEvent.click(screen.getByRole("radio", { name: "English" }));

    expect(i18n.language).toBe("en");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
