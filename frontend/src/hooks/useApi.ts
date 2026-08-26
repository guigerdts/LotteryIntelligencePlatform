import { useState, useCallback, useEffect, useRef } from "react";

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Module-level active AbortController.  ``useApi`` sets this before calling the
 * fetcher so that ``apiClient`` can pick up the signal without every service
 * function needing an explicit ``signal`` parameter.
 */
let _activeController: AbortController | null = null;

/** Return the live AbortSignal set by the currently-executing ``useApi`` call. */
export function getActiveSignal(): AbortSignal | undefined {
  return _activeController?.signal;
}

/** A fetcher that receives the live AbortSignal as its final argument. */
export type AbortableFetcher<TArgs extends unknown[], TResult> = (
  ...args: [...TArgs, AbortSignal]
) => Promise<TResult>;

/**
 * Adapt a fetcher that expects an AbortSignal as its final argument into the
 * plain `(...args) => Promise` shape useApi expects.  The live AbortSignal is
 * injected automatically from the module-level slot (``getActiveSignal()``)
 * at call time, so cancellation reaches the underlying request without
 * changing the page-level call signature.
 */
export function abortable<TArgs extends unknown[], TResult>(
  fn: (...args: [...TArgs, AbortSignal]) => Promise<TResult>
): (...args: TArgs) => Promise<TResult> {
  return (...args: TArgs) => fn(...args, getActiveSignal() as AbortSignal);
}

/**
 * Generic hook for API calls with loading/error state management.
 * Wraps any async function that returns data. Exposes `abort` to cancel the
 * in-flight request (via an AbortController) and `isCancelled` so pages can
 * show a short "Cancelado" note instead of an error.
 *
 * The live ``AbortSignal`` is stored in a module-level slot read by
 * ``apiClient`` via ``getActiveSignal()`` — it is **never** appended as a
 * function argument, so service functions that do not accept a signal are
 * unaffected.
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
      _activeController = controller;
      setIsCancelled(false);
      setState({ data: null, isLoading: true, error: null });
      try {
        // Pass only the caller's arguments — the signal reaches apiClient
        // through getActiveSignal(), NOT as an extra function argument.
        const result = await fetcher(...args);
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
      } finally {
        if (_activeController === controller) _activeController = null;
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
