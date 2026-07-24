import { useNavigate } from "react-router-dom";
import type { KeyboardEvent, MouseEvent } from "react";

/** Part 4: makes an entire row/list-item a single navigation target to a coin's Coin Details
 * page, instead of only the name cell's link. One click/keydown handler on the row itself (spread
 * onto a `<tr>` or `<li>`) means there's exactly one navigation per activation and no nested
 * `<a>`/`<button>` inside the row competing for the click. */
export function useRowNavigate(symbol: string, label: string) {
  const navigate = useNavigate();
  const to = `/coins/${symbol.toLowerCase()}`;

  return {
    onClick: (_event: MouseEvent<HTMLElement>) => {
      navigate(to);
    },
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        navigate(to);
      }
    },
    tabIndex: 0,
    role: "link" as const,
    "aria-label": label,
  };
}
