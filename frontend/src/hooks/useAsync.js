import { useCallback, useEffect, useRef, useState } from "react";

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

  const latest = useRef(0);

  const run = useCallback(async () => {
    const request = ++latest.current;
    setState((s) => ({ ...s, loading: s.data === null, refreshing: s.data !== null }));
    try {
      const data = await loader();
      if (request !== latest.current) return;
      setState({ data, error: null, loading: false, refreshing: false, checkedAt: new Date() });
    } catch (error) {
      if (request !== latest.current) return;
      setState((s) => ({ ...s, error, loading: false, refreshing: false }));
    }
  }, [loader]);

  useEffect(() => {
    // Initial fetch on mount.
    run();
  }, [run]);

  return { ...state, reload: run };
}
