import { useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Modal } from "./Modal";
import { CoinSelect } from "./CoinSelect";
import { ApiError } from "../api/client";
import type { Holding } from "../api/types";

export interface HoldingFormValues {
  coin_symbol: string;
  quantity: number;
  average_buy_price: number;
}

interface HoldingFormModalProps {
  /** Present when editing an existing holding; absent when adding a new one. Coin symbol is
   * fixed once a holding exists — editing only changes quantity/average buy price. */
  holding?: Holding;
  onSubmit: (values: HoldingFormValues) => Promise<void>;
  onClose: () => void;
}

export function HoldingFormModal({ holding, onSubmit, onClose }: HoldingFormModalProps) {
  const { t } = useTranslation();
  const [coinSymbol, setCoinSymbol] = useState(holding?.coin_symbol ?? "");
  const [quantity, setQuantity] = useState(holding ? String(holding.quantity) : "");
  const [averageBuyPrice, setAverageBuyPrice] = useState(holding ? String(holding.average_buy_price) : "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const quantityNum = Number(quantity);
  const priceNum = Number(averageBuyPrice);

  const symbolError = !holding && !coinSymbol ? t("portfolio.forms.selectCoin") : null;
  const quantityError =
    quantity.trim() === "" || Number.isNaN(quantityNum) || quantityNum <= 0
      ? t("portfolio.forms.quantityMustBePositive")
      : null;
  const priceError =
    averageBuyPrice.trim() === "" || Number.isNaN(priceNum) || priceNum < 0
      ? t("portfolio.forms.priceMustBeNonNegative")
      : null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (symbolError || quantityError || priceError) return;

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ coin_symbol: coinSymbol, quantity: quantityNum, average_buy_price: priceNum });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.somethingWentWrong"));
      setSubmitting(false);
    }
  }

  return (
    <Modal title={holding ? t("portfolio.forms.editHolding") : t("portfolio.forms.addHolding")} onClose={onClose}>
      <form className="modal-form" onSubmit={handleSubmit}>
        <div className="modal-field">
          <label htmlFor="holding-coin">{t("table.coin")}</label>
          {holding ? (
            <input id="holding-coin" type="text" value={`${holding.coin_name ?? ""} (${holding.coin_symbol})`} disabled />
          ) : (
            <CoinSelect value={coinSymbol} onChange={setCoinSymbol} />
          )}
          {touched && symbolError && <span className="modal-field-error">{symbolError}</span>}
        </div>
        <div className="modal-field">
          <label htmlFor="holding-quantity">{t("portfolio.holdingsTable.quantity")}</label>
          <input
            id="holding-quantity"
            type="number"
            step="any"
            min="0"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            autoFocus={!!holding}
          />
          {touched && quantityError && <span className="modal-field-error">{quantityError}</span>}
        </div>
        <div className="modal-field">
          <label htmlFor="holding-price">{t("portfolio.forms.averageBuyPriceUsd")}</label>
          <input
            id="holding-price"
            type="number"
            step="any"
            min="0"
            value={averageBuyPrice}
            onChange={(event) => setAverageBuyPrice(event.target.value)}
          />
          {touched && priceError && <span className="modal-field-error">{priceError}</span>}
        </div>
        {error && <p className="modal-error">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="modal-button" onClick={onClose} disabled={submitting}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="modal-button modal-button--primary" disabled={submitting}>
            {submitting ? t("common.saving") : holding ? t("common.save") : t("common.add")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
