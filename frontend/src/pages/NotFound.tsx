import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import "./NotFound.css";

export function NotFound() {
  const { t } = useTranslation();

  return (
    <main className="not-found">
      <h1>404</h1>
      <p>{t("notFound.message")}</p>
      <Link to="/" className="back-link">
        ← {t("notFound.backLink")}
      </Link>
    </main>
  );
}
