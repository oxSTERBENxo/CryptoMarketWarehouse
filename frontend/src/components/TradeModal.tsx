import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Modal } from "./Modal";
import { CoinSelect } from "./CoinSelect";
import { getCurrentMarket } from "../api/analytics";
import { useApiData } from "../hooks/useApiData";
import { ApiError } from "../api/client";
import { formatCryptoPrice, formatUsd } from "../utils/format";
import type { PaperHolding } from "../api/types";
import "./TradeModal.css";

export interface TradeFormValues {
  coin_symbol: string;
  quantity: number;
}

interface TradeModalProps {
  mode: "buy" | "sell";
  /** Present when opened from a specific holding row ("Buy More" / "Sell") — locks the coin. */
  fixedSymbol?: string;
  fixedCoinName?: string | null;
  /** For sell: only coins currently held can be chosen from. */
  sellableHoldings?: PaperHolding[];
  cashBalance: number;
  onSubmit: (values: TradeFormValues) => Promise<void>;
  onClose: () => void;
}

const PRICE_FETCH_LIMIT = 500;

export function TradeModal({
  mode,
  fixedSymbol,
  fixedCoinName,
  sellableHoldings = [],
  cashBalance,
  onSubmit,
  onClose,
}: TradeModalProps) {
  const { t } = useTranslation();
  const prices = useApiData(() => getCurrentMarket(PRICE_FETCH_LIMIT));
  const [coinSymbol, setCoinSymbol] = useState(fixedSymbol ?? "");
  const [quantity, setQuantity] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const priceMap = useMemo(() => {
    const map = new Map<string, number>();
    prices.data?.coins.forEach((coin) => map.set(coin.symbol.toUpperCase(), coin.price_usd));
    return map;
  }, [prices.data]);

  const quantityNum = Number(quantity);
  const currentPrice = coinSymbol ? priceMap.get(coinSymbol) ?? null : null;
  const estimatedTotal = currentPrice !== null && quantityNum > 0 ? currentPrice * quantityNum : null;
  const heldQuantity = sellableHoldings.find((h) => h.coin_symbol === coinSymbol)?.quantity ?? null;

  const symbolError = !coinSymbol ? t("portfolio.forms.selectCoin") : null;
  const quantityError =
    quantity.trim() === "" || Number.isNaN(quantityNum) || quantityNum <= 0
      ? t("portfolio.forms.quantityMustBePositive")
      : mode === "buy" && estimatedTotal !== null && estimatedTotal > cashBalance
        ? t("portfolio.trade.costExceedsCash")
        : mode === "sell" && heldQuantity !== null && quantityNum > heldQuantity
          ? t("portfolio.trade.exceedsHoldings")
          : null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (symbolError || quantityError) return;

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ coin_symbol: coinSymbol, quantity: quantityNum });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
      setSubmitting(false);
    }
  }

  return (
    <Modal title={mode === "buy" ? t("portfolio.trade.buyTitle") : t("portfolio.trade.sellTitle")} onClose={onClose}>
      <form className="modal-form trade-modal-form" onSubmit={handleSubmit}>
        <div className="modal-field">
          <label htmlFor="trade-coin">{t("table.coin")}</label>
          {fixedSymbol ? (
            <input id="trade-coin" type="text" value={`${fixedCoinName ?? ""} (${fixedSymbol})`} disabled />
          ) : mode === "buy" ? (
            <CoinSelect value={coinSymbol} onChange={setCoinSymbol} />
          ) : (
            <CoinSelect
              value={coinSymbol}
              onChange={setCoinSymbol}
              restrictToSymbols={sellableHoldings.map((h) => h.coin_symbol)}
            />
          )}
          {touched && symbolError && <span className="modal-field-error">{symbolError}</span>}
        </div>

        <div className="modal-field">
          <label htmlFor="trade-quantity">{t("portfolio.holdingsTable.quantity")}</label>
          <input
            id="trade-quantity"
            type="number"
            step="any"
            min="0"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            autoFocus
          />
          {touched && quantityError && <span className="modal-field-error">{quantityError}</span>}
        </div>

        <div className="trade-modal-estimate">
          <div>
            <span>{t("portfolio.trade.currentPrice")}</span>
            <strong>{currentPrice === null ? "—" : formatCryptoPrice(currentPrice)}</strong>
          </div>
          <div>
            <span>{mode === "buy" ? t("portfolio.trade.estimatedCost") : t("portfolio.trade.estimatedProceeds")}</span>
            <strong>{estimatedTotal === null ? "—" : formatUsd(estimatedTotal)}</strong>
          </div>
          {mode === "sell" && heldQuantity !== null && (
            <div>
              <span>{t("portfolio.trade.youHold")}</span>
              <strong>{heldQuantity.toLocaleString(undefined, { maximumFractionDigits: 8 })}</strong>
            </div>
          )}
          {mode === "buy" && (
            <div>
              <span>{t("portfolio.paper.availableCash")}</span>
              <strong>{formatUsd(cashBalance)}</strong>
            </div>
          )}
        </div>

        {error && <p className="modal-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="modal-button" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className={`modal-button ${mode === "sell" ? "modal-button--danger" : "modal-button--primary"}`}
            disabled={submitting}
          >
            {submitting ? t("portfolio.trade.submitting") : mode === "buy" ? t("portfolio.paper.buy") : t("portfolio.paper.sell")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
