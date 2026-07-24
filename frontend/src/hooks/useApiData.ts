import { useCallback, useEffect, useRef, useState } from "react";
import type { DependencyList } from "react";
import { ApiError } from "../api/client";

export interface ApiDataState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

/**
 * Fetches data for one dashboard section independently: tracks its own loading/error state
 * and exposes retry() so one failing section never blocks the rest of the page.
 *
 * `deps` lets callers refetch when parameters baked into `fetcher` change (e.g. a selected
 * date range), without firing an extra request on every render — pass the values `fetcher`
 * closes over, same as a `useEffect` dependency list.
 */
export function useApiData<T>(fetcher: () => Promise<T>, deps: DependencyList = []): ApiDataState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Keep the latest fetcher without re-triggering the effect on every render.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(messageFor(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, ...deps]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);

  return { data, loading, error, retry };
}
