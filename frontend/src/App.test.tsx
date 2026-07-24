import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "./i18n";
import { ThemeProvider } from "./contexts/ThemeContext";
import App from "./App";

// The pages the router mounts pull live data; stub them so this test exercises only the
// navigation chrome and routing, not each page's fetching.
vi.mock("./pages/Dashboard", () => ({ Dashboard: () => <div>dashboard-page</div> }));
vi.mock("./pages/MarketLeaders", () => ({ MarketLeaders: () => <div>market-leaders-page</div> }));
vi.mock("./pages/AnalyticsExplorer", () => ({ AnalyticsExplorer: () => <div>explorer-page</div> }));
vi.mock("./pages/Portfolio", () => ({ Portfolio: () => <div>portfolio-page</div> }));
vi.mock("./pages/CoinDetails", () => ({ CoinDetails: () => <div>coin-details-page</div> }));
vi.mock("./pages/WarehouseHealth", () => ({ WarehouseHealth: () => <div>warehouse-health-page</div> }));

function mockMatchMedia() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
  );
  window.matchMedia = globalThis.matchMedia as typeof window.matchMedia;
}

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </ThemeProvider>
  );
}

beforeEach(async () => {
  mockMatchMedia();
  localStorage.clear();
  await i18n.changeLanguage("en");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("App navigation", () => {
  it("does not offer Warehouse Health anywhere in the navigation", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation");
    expect(within(nav).queryByText(/warehouse health/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /warehouse health/i })).not.toBeInTheDocument();
  });

  it("offers Dashboard, Market Leaders, Analytics Explorer, Portfolio, and Settings", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Dashboard")).toBeInTheDocument();
    expect(within(nav).getByText("Market Leaders")).toBeInTheDocument();
    expect(within(nav).getByText("Analytics Explorer")).toBeInTheDocument();
    expect(within(nav).getByText("Portfolio")).toBeInTheDocument();
    expect(within(nav).getByText("Settings")).toBeInTheDocument();
  });

  it("still serves the Warehouse Health page at its direct URL", () => {
    renderAt("/warehouse-health");
    expect(screen.getByText("warehouse-health-page")).toBeInTheDocument();
  });

  it("serves the Settings page at /settings", () => {
    renderAt("/settings");
    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });

  it("renders the navigation in Macedonian after a language switch", async () => {
    await i18n.changeLanguage("mk");
    renderAt("/");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByText("Почетна")).toBeInTheDocument();
    expect(within(nav).getByText("Пазарни лидери")).toBeInTheDocument();
    expect(within(nav).getByText("Поставки")).toBeInTheDocument();
    await i18n.changeLanguage("en");
  });
});
