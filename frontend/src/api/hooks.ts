import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./client";

export interface Fetched<T> { data: T | null; error: string | null; status: number | null; loading: boolean; reload: () => void; setData: (d: T) => void }

/** Minimal GET hook. Pass null to skip. Re-fetches when `path` changes; `reload()` forces it. */
export function useFetch<T>(path: string | null): Fetched<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    if (path === null) return;
    const mine = ++seq.current;
    setLoading(true);
    api<T>(path)
      .then((d) => mine === seq.current && (setData(d), setError(null), setStatus(null)))
      .catch((e: Error) => mine === seq.current && (setError(e.message), setStatus(e instanceof ApiError ? e.status : null)))
      .finally(() => mine === seq.current && setLoading(false));
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, status, loading, reload, setData };
}
