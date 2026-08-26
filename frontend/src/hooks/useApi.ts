import { useState, useCallback, useEffect, useRef } from "react";

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/** A fetcher that receives the live AbortSignal as its final argument. */
export type AbortableFetcher<TArgs extends unknown[], TResult> = (
  ...args: [...TArgs, AbortSignal]
) => Promise<TResult>;

/**
 * Adapt a fetcher that expects an AbortSignal as its final argument into the
 * plain `(...args) => Promise` shape useApi expects. useApi appends the live
 * AbortSignal as the final argument when it runs, so cancellation reaches the
 * underlying request without changing the page-level call signature.
 */
export function abortable<TArgs extends unknown[], TResult>(
  fn: AbortableFetcher<TArgs, TResult>
): (...args: TArgs) => Promise<TResult> {
  return fn as unknown as (...args: TArgs) => Promise<TResult>;
}

/**
 * Generic hook for API calls with loading/error state management.
 * Wraps any async function that returns data. Exposes `abort` to cancel the
 * in-flight request (via an AbortController) and `isCancelled` so pages can
 * show a short "Cancelado" note instead of an error.
 */
export function useApi<TArgs extends unknown[], TResult>(
  fetcher: (...args: TArgs) => Promise<TResult>
): UseApiState<TResult> & {
  execute: (...args: TArgs) => Promise<TResult | null>;
  abort: () => void;
  isCancelled: boolean;
} {
  const [state, setState] = useState<UseApiState<TResult>>({
    data: null,
    isLoading: false,
    error: null,
  });
  const [isCancelled, setIsCancelled] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const execute = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      // Abort any still-running request before starting a new one.
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setIsCancelled(false);
      setState({ data: null, isLoading: true, error: null });
      try {
        const fn = fetcher as unknown as AbortableFetcher<TArgs, TResult>;
        const result = await fn(...args, controller.signal);
        // A newer request superseded this one, or it was aborted: ignore.
        if (controllerRef.current !== controller) return null;
        if (controller.signal.aborted) return null;
        setState({ data: result, isLoading: false, error: null });
        return result;
      } catch (err) {
        if (controllerRef.current !== controller) return null;
        if (controller.signal.aborted) {
          setIsCancelled(true);
          setState({ data: null, isLoading: false, error: null });
          return null;
        }
        const message = err instanceof Error ? err.message : "Unknown error";
        setState({ data: null, isLoading: false, error: message });
        return null;
      }
    },
    [fetcher]
  );

  const abort = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  // Cancel any in-flight request when the owning component unmounts.
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  return { ...state, execute, abort, isCancelled };
}
