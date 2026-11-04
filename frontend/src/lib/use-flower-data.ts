import { useCallback, useEffect, useState } from "react";
import { isError } from "@/lib/frappe";
import { flowerData, type FlowerData } from "@/lib/flowers-api";

/** The crop's blocks/greenhouses, beds and cycles (one call), with a reload. */
export function useFlowerData(crop: string, onError?: (msg: string) => void) {
  const [data, setData] = useState<FlowerData | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    const r = await flowerData(crop);
    setLoading(false);
    if (isError(r)) {
      onError?.(r.error);
      return;
    }
    setData(r as FlowerData);
  }, [crop, onError]);
  useEffect(() => {
    void load();
  }, [load]);
  return { data, loading, reload: load };
}
