import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import mk from "./mk.json";

export const LANGUAGE_STORAGE_KEY = "cmw-language";
export const SUPPORTED_LANGUAGES = ["en", "mk"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export function isSupportedLanguage(value: unknown): value is SupportedLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value as string);
}

function readStoredLanguage(): SupportedLanguage | null {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isSupportedLanguage(stored) ? stored : null;
  } catch {
    return null;
  }
}

/** First launch: honor the browser language (Macedonian if it starts with "mk", English otherwise).
 * Every launch after that respects whatever the user picked in Settings. */
function detectInitialLanguage(): SupportedLanguage {
  const stored = readStoredLanguage();
  if (stored) return stored;

  const browserLanguage = typeof navigator !== "undefined" ? navigator.language : "en";
  return browserLanguage?.toLowerCase().startsWith("mk") ? "mk" : "en";
}

export function persistLanguage(language: SupportedLanguage): void {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // localStorage unavailable (private mode/disabled) -- selection stays in-memory only.
  }
}

export const initialLanguage = detectInitialLanguage();

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    mk: { translation: mk },
  },
  lng: initialLanguage,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnEmptyString: false,
});

if (typeof document !== "undefined") {
  document.documentElement.lang = initialLanguage;
  i18n.on("languageChanged", (lng) => {
    document.documentElement.lang = lng;
  });
}

export default i18n;
