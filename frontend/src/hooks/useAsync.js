import { useCallback, useEffect, useState } from "react";

/**
 * Run an async loader (a stable, module-level function) and track its state.
 * A refresh keeps the previous data on screen (only `refreshing` flips), so the layout
 * never falls back to skeletons once data has arrived.
 */
export function useAsync(loader) {
  const [state, setState] = useState({
    data: null,
    error: null,
    loading: true,
    refreshing: false,
    checkedAt: null,
  });

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: s.data === null, refreshing: s.data !== null }));
    try {
      const data = await loader();
      setState({ data, error: null, loading: false, refreshing: false, checkedAt: new Date() });
    } catch (error) {
      setState((s) => ({ ...s, error, loading: false, refreshing: false }));
    }
  }, [loader]);

  useEffect(() => {
    // Initial fetch on mount.
    run();
  }, [run]);

  return { ...state, reload: run };
}
