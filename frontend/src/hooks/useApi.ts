import { useState, useCallback } from "react";

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Generic hook for API calls with loading/error state management.
 * Wraps any async function that returns data.
 */
export function useApi<TArgs extends unknown[], TResult>(
  fetcher: (...args: TArgs) => Promise<TResult>,
): UseApiState<TResult> & {
  execute: (...args: TArgs) => Promise<TResult | null>;
} {
  const [state, setState] = useState<UseApiState<TResult>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const execute = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setState({ data: null, isLoading: true, error: null });
      try {
        const result = await fetcher(...args);
        setState({ data: result, isLoading: false, error: null });
        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setState({ data: null, isLoading: false, error: message });
        return null;
      }
    },
    [fetcher],
  );

  return { ...state, execute };
}
