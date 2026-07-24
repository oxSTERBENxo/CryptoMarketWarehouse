import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  Holding,
  HoldingCreateRequest,
  HoldingUpdateRequest,
  PortfolioCreateRequest,
  PortfolioDetail,
  PortfolioUpdateRequest,
} from "./types";

/** GET /portfolios */
export function getPortfolios(): Promise<PortfolioDetail[]> {
  return apiGet<PortfolioDetail[]>("/portfolios");
}

/** POST /portfolios */
export function createPortfolio(body: PortfolioCreateRequest): Promise<PortfolioDetail> {
  return apiPost<PortfolioDetail>("/portfolios", body);
}

/** GET /portfolios/{id} */
export function getPortfolio(portfolioId: number): Promise<PortfolioDetail> {
  return apiGet<PortfolioDetail>(`/portfolios/${portfolioId}`);
}

/** PUT /portfolios/{id} */
export function updatePortfolio(portfolioId: number, body: PortfolioUpdateRequest): Promise<PortfolioDetail> {
  return apiPut<PortfolioDetail>(`/portfolios/${portfolioId}`, body);
}

/** DELETE /portfolios/{id} */
export function deletePortfolio(portfolioId: number): Promise<undefined> {
  return apiDelete(`/portfolios/${portfolioId}`);
}

/** POST /portfolios/{id}/holdings */
export function addHolding(portfolioId: number, body: HoldingCreateRequest): Promise<Holding> {
  return apiPost<Holding>(`/portfolios/${portfolioId}/holdings`, body);
}

/** PUT /holdings/{id} */
export function updateHolding(holdingId: number, body: HoldingUpdateRequest): Promise<Holding> {
  return apiPut<Holding>(`/holdings/${holdingId}`, body);
}

/** DELETE /holdings/{id} */
export function deleteHolding(holdingId: number): Promise<undefined> {
  return apiDelete(`/holdings/${holdingId}`);
}
