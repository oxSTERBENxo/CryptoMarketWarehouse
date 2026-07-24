import { useTranslation } from "react-i18next";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { AnalyticsExplorer } from "./pages/AnalyticsExplorer";
import { CoinDetails } from "./pages/CoinDetails";
import { MarketLeaders } from "./pages/MarketLeaders";
import { Portfolio } from "./pages/Portfolio";
import { WarehouseHealth } from "./pages/WarehouseHealth";
import { Settings } from "./pages/Settings";
import { NotFound } from "./pages/NotFound";
import "./App.css";

function App() {
  const { t } = useTranslation();

  return (
    <>
      <header className="app-header">
        <Link to="/" className="app-header__title">
          {t("app.title")}
        </Link>
        <nav className="app-header__nav">
          <NavLink to="/" end className="app-header__nav-link">
            {t("nav.dashboard")}
          </NavLink>
          <NavLink to="/market-leaders" className="app-header__nav-link">
            {t("nav.marketLeaders")}
          </NavLink>
          <NavLink to="/analytics-explorer" className="app-header__nav-link">
            {t("nav.analyticsExplorer")}
          </NavLink>
          <NavLink to="/portfolio" className="app-header__nav-link">
            {t("nav.portfolio")}
          </NavLink>
          <NavLink to="/settings" className="app-header__nav-link">
            {t("nav.settings")}
          </NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/coins/:symbol" element={<CoinDetails />} />
        <Route path="/market-leaders" element={<MarketLeaders />} />
        <Route path="/analytics-explorer" element={<AnalyticsExplorer />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/settings" element={<Settings />} />
        {/* Not in the nav -- developer/ops feature, reachable only by direct URL. See KNOWN_LIMITATIONS.md. */}
        <Route path="/warehouse-health" element={<WarehouseHealth />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  );
}

export default App;
