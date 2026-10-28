import { useEffect, useState } from "react";
import { listUnits } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { listVarieties } from "@/lib/varieties-api";

export interface VarietyFilterData {
  options: { value: string; label: string }[];
  /** Block (unit) name -> variety of its current cycle. */
  byUnit: Map<string, string>;
}

const EMPTY: VarietyFilterData = { options: [], byUnit: new Map() };

/**
 * What a variety filter needs: the crop's varieties and which block is growing which. Forecast and
 * cost rows are per block, and a block's variety is the one on its current cycle (a variety is its
 * own stock item, so item and variety are the same thing here). A failure just means no filter.
 */
export function useVarietyFilter(crop: string): VarietyFilterData {
  const [data, setData] = useState<VarietyFilterData>(EMPTY);
  useEffect(() => {
    let live = true;
    setData(EMPTY);
    (async () => {
      try {
        const [v, u] = await Promise.all([listVarieties(crop), listUnits(crop)]);
        if (!live || isError(v) || isError(u)) return;
        const items = new Map(v.varieties.map((x) => [x.item, x.name]));
        const byUnit = new Map<string, string>();
        for (const row of u.units) {
          const name = row.variety || (row.item ? items.get(row.item) : undefined);
          if (name) byUnit.set(row.name, name);
        }
        setData({ options: v.varieties.map((x) => ({ value: x.name, label: x.variety_name })), byUnit });
      } catch {
        /* no filter */
      }
    })();
    return () => {
      live = false;
    };
  }, [crop]);
  return data;
}
