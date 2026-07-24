import type { Achievement } from "../utils/achievements";
import "./AchievementBadges.css";

interface AchievementBadgesProps {
  achievements: Achievement[];
}

export function AchievementBadges({ achievements }: AchievementBadgesProps) {
  return (
    <ul className="achievement-badges">
      {achievements.map((achievement) => (
        <li
          key={achievement.id}
          className={`achievement-badge ${achievement.earned ? "achievement-badge--earned" : ""}`}
          title={achievement.description}
        >
          <span className="achievement-badge__icon" aria-hidden="true">
            {achievement.earned ? "✓" : "○"}
          </span>
          <span className="achievement-badge__label">{achievement.label}</span>
        </li>
      ))}
    </ul>
  );
}
