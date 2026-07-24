import { API_BASE_URL, ApiError, apiPost } from "./client";
import type { ExplorerRequest, ExplorerResponse } from "./types";

/** POST /analytics/explorer/query — run one registered analysis over historical warehouse data. */
export function runExplorerQuery(request: ExplorerRequest): Promise<ExplorerResponse> {
  return apiPost<ExplorerResponse>("/analytics/explorer/query", request);
}

/** POST /analytics/explorer/export — the same analysis as a full (unpaginated) CSV. Returns the
 * CSV body plus the server-suggested filename, for the caller to hand to a download link. The
 * response is a file attachment rather than JSON, so this bypasses apiPost deliberately. */
export async function exportExplorerCsv(request: ExplorerRequest): Promise<{ csv: string; filename: string }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/analytics/explorer/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw new ApiError("Unable to reach the server. Check your connection and that the API is running.", 0);
  }

  if (!response.ok) {
    throw new ApiError(response.statusText || `Export failed with status ${response.status}`, response.status);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  return {
    csv: await response.text(),
    filename: match?.[1] ?? "analytics-explorer.csv",
  };
}
