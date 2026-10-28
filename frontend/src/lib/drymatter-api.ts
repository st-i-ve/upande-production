/**
 * Client for `upande_production.api.drymatter`: generic dry matter tests for crops with
 * `dry_matter_testing` on (avocado keeps `avocado-api`). Resolves to an `Envelope<T>`; check `isError(r)`.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.drymatter.";

export interface DryMatterSample {
  sample_no: number;
  dry_matter_pct: number;
}

export interface DryMatterTest {
  name: string;
  unit: string;
  cycle?: string | null;
  variety?: string | null;
  test_date: string;
  tested_on?: "Fruit" | "Tuber" | null;
  avg_pct: number;
  target_pct: number | null;
  ready: 0 | 1 | boolean;
  tested_by?: string | null;
  samples: DryMatterSample[];
}

export const listDryMatterTests = (crop: string, unit?: string | null) =>
  call<{ rows: DryMatterTest[] }>(PREFIX + "list_tests", { crop, ...(unit ? { unit } : {}) });

export interface DryMatterTestInput {
  crop: string;
  unit: string;
  test_date: string;
  cycle?: string | null;
  samples: DryMatterSample[];
}

export const saveDryMatterTest = (data: DryMatterTestInput): Promise<Envelope<{ name: string; avg_pct: number; ready: boolean }>> =>
  call(PREFIX + "save_test", { data });
