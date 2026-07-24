const DEFAULT_API_BASE_URL = "http://localhost:8000";

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? DEFAULT_API_BASE_URL;

/** Base URL for the FastAPI backend, configured via VITE_API_BASE_URL. Trailing slash stripped. */
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type QueryParams = Record<string, string | number | undefined>;

function buildUrl(path: string, params?: QueryParams): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

/** Extracts a readable message from a non-2xx response: FastAPI's `detail` (string, or the
 * list-of-objects shape Pydantic validation errors take), falling back to statusText. */
async function detailFor(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        const messages = detail
          .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : null))
          .filter((msg): msg is string => msg !== null);
        if (messages.length > 0) return messages.join("; ");
      }
    }
  } catch {
    // response body wasn't JSON; fall back to statusText
  }
  return response.statusText || `Request failed with status ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit, params?: QueryParams): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), init);
  } catch {
    throw new ApiError("Unable to reach the server. Check your connection and that the API is running.", 0);
  }

  if (!response.ok) {
    throw new ApiError(await detailFor(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** GET request against the API with centralized error handling for non-2xx and network failures. */
export function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  return request<T>(path, undefined, params);
}

/** POST request with a JSON body. */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** PUT request with a JSON body. */
export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** DELETE request. Resolves to undefined on the API's 204 No Content response. */
export function apiDelete(path: string): Promise<undefined> {
  return request<undefined>(path, { method: "DELETE" });
}
