import { useCallback, useEffect, useState } from "react";

// Petit utilitaire de chargement : état « en cours / erreur / données » et relance.
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const run = useCallback(loader, deps);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    run()
      .then((value) => alive && setData(value))
      .catch((e: Error) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [run, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}
