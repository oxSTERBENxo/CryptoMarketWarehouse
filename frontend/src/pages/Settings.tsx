import { useTranslation } from "react-i18next";
import { useTheme } from "../contexts/ThemeContext";
import { isSupportedLanguage, persistLanguage } from "../i18n";
import type { SupportedLanguage } from "../i18n";
import type { ThemePreference } from "../theme/theme";
import "./Settings.css";

const THEME_OPTIONS: ThemePreference[] = ["light", "dark", "system"];
const LANGUAGE_OPTIONS: SupportedLanguage[] = ["en", "mk"];

export function Settings() {
  const { t, i18n } = useTranslation();
  const { preference, setPreference } = useTheme();

  const handleLanguageChange = (language: SupportedLanguage) => {
    if (!isSupportedLanguage(language)) return;
    void i18n.changeLanguage(language);
    persistLanguage(language);
  };

  return (
    <main className="settings-page">
      <h1 className="settings-page__title">{t("settings.title")}</h1>
      <p className="settings-page__subtitle">{t("settings.subtitle")}</p>

      <section aria-labelledby="settings-appearance-heading" className="settings-section">
        <h2 id="settings-appearance-heading">{t("settings.appearance.title")}</h2>
        <p className="settings-section__description">{t("settings.appearance.description")}</p>
        <div className="settings-options" role="radiogroup" aria-labelledby="settings-appearance-heading">
          {THEME_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={preference === option}
              className={`settings-option${preference === option ? " settings-option--active" : ""}`}
              onClick={() => setPreference(option)}
            >
              {t(`settings.appearance.${option}`)}
            </button>
          ))}
        </div>
      </section>

      <section aria-labelledby="settings-language-heading" className="settings-section">
        <h2 id="settings-language-heading">{t("settings.language.title")}</h2>
        <p className="settings-section__description">{t("settings.language.description")}</p>
        <div className="settings-options" role="radiogroup" aria-labelledby="settings-language-heading">
          {LANGUAGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={i18n.language === option}
              className={`settings-option${i18n.language === option ? " settings-option--active" : ""}`}
              onClick={() => handleLanguageChange(option)}
            >
              {t(`settings.language.${option}`)}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
