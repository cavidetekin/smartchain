// Ekranların iş bildirimiyle kendiliğinden yenilenmesi (K-143; Veri yükleme, Veri kuralları, Validasyon kuralları).
import { useEffect } from "react";

import { type Job, JOB_EVENT } from "../api/client";

export function useJobRefresh(types: readonly string[], refresh: () => void, delay = 300): void {
  /** Kullanıcının işleri değişince ekran yenilenir (K-143): iş göstergesinin anlık bildirimi (`smartchain:job`). */
  useEffect(() => {
    let timer: number | undefined;
    const onJob = (e: Event) => {
      if (!types.includes((e as CustomEvent<Job>).detail.job_type)) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(refresh, delay);
    };
    window.addEventListener(JOB_EVENT, onJob);
    return () => {
      window.removeEventListener(JOB_EVENT, onJob);
      window.clearTimeout(timer);
    };
  }, [types, refresh, delay]);
}
