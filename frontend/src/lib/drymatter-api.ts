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
  tested_on?: "Fruit" | "Tuber" | "Bulb" | "Head" | "Leaf" | null;
  /** The cycle's stage on the test date. */
  stage?: string | null;
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

/** due: in or past the variety's sampling stage with no test in the retest window; recent: tested inside it;
 *  not_yet: still before the sampling stage. */
export type DueState = "due" | "recent" | "not_yet";

export interface DueRow {
  unit: string;
  cycle: string;
  variety: string | null;
  stage: string | null;
  from_stage: string | null;
  on: string | null;
  target_pct: number | null;
  state: DueState;
  last_test: string | null;
  days_since: number | null;
  last_pct: number | null;
  next_due: string | null;
}

export interface DueList {
  rows: DueRow[];
  retest_days: number;
  counts: Record<DueState, number>;
}

export const listDryMatterDue = (crop: string) => call<DueList>(PREFIX + "list_due", { crop });
