import { apiGet } from "./client";
import type { SchedulerHealth, WarehouseHealthResponse } from "./types";

/** GET /health/scheduler */
export function getSchedulerHealth(): Promise<SchedulerHealth> {
  return apiGet<SchedulerHealth>("/health/scheduler");
}

/** GET /health/warehouse */
export function getWarehouseHealth(): Promise<WarehouseHealthResponse> {
  return apiGet<WarehouseHealthResponse>("/health/warehouse");
}
