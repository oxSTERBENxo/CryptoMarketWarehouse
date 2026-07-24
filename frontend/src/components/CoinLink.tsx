import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import "./CoinLink.css";

interface CoinLinkProps {
  symbol: string;
  children: ReactNode;
}

/** Links a coin's name/symbol cell to its details page, using a normalized lowercase symbol. */
export function CoinLink({ symbol, children }: CoinLinkProps) {
  return (
    <Link to={`/coins/${symbol.toLowerCase()}`} className="coin-link">
      {children}
    </Link>
  );
}
