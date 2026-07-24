import { useTranslation } from "react-i18next";
import type { HealthScore } from "../utils/healthScore";
import "./HealthScoreCard.css";

interface HealthScoreCardProps {
  healthScore: HealthScore;
}

function scoreClass(score: number): string {
  if (score >= 70) return "health-score__value--good";
  if (score >= 40) return "health-score__value--fair";
  return "health-score__value--poor";
}

export function HealthScoreCard({ healthScore }: HealthScoreCardProps) {
  const { t } = useTranslation();
  return (
    <div className="health-score">
      <div className="health-score__headline">
        <div>
          <h3>{t("portfolio.health.title")}</h3>
          <p className="health-score__disclaimer">{t("portfolio.health.disclaimer")}</p>
        </div>
        <span className={`health-score__value ${scoreClass(healthScore.score)}`}>{healthScore.score}</span>
      </div>
      <ul className="health-score__factors">
        {healthScore.factors.map((factor) => (
          <li key={factor.id}>
            <div className="health-score__factor-header">
              <span>{factor.label}</span>
              <span>
                {factor.points.toFixed(1)} / {factor.maxPoints}
              </span>
            </div>
            <div className="health-score__track">
              <div
                className="health-score__fill"
                style={{ width: `${Math.min((factor.points / factor.maxPoints) * 100, 100)}%` }}
              />
            </div>
            <p className="health-score__detail">{factor.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
