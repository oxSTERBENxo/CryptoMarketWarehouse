import { useState } from "react";
import "./CoinLogo.css";

interface CoinLogoProps {
  src: string | null | undefined;
  /** Coin name, used only for the fallback glyph's first letter — the logo itself is decorative
   * (the coin name is always rendered as adjacent text), so the <img> carries no alt text. */
  name: string;
  size?: number;
}

/** Part 2: one consistent coin-logo component reused everywhere a coin is shown. Fixed
 * dimensions reserve the same box whether the image is loading, missing, or broken, so nothing
 * shifts layout; a broken/missing image falls back to a circular initial-letter glyph instead of
 * a broken-image icon. */
export function CoinLogo({ src, name, size = 28 }: CoinLogoProps) {
  const [broken, setBroken] = useState(false);
  const showFallback = !src || broken;

  return (
    <span className="coin-logo" style={{ width: size, height: size }} aria-hidden="true">
      {showFallback ? (
        <span className="coin-logo__fallback">{name.trim().charAt(0).toUpperCase() || "?"}</span>
      ) : (
        <img
          className="coin-logo__img"
          src={src}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          onError={() => setBroken(true)}
        />
      )}
    </span>
  );
}
