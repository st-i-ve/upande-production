/**
 * Typed client for `upande_production.api.aquaculture`: one endpoint per aquaculture page
 * plus the record actions behind each dialog.
 *
 * Every function resolves to an `Envelope<T>` (data, or `{error}`); nothing throws, check
 * `isError(r)` first. Units are in the field names: `_kg`, `_g`, `_mg_l`, `_c`, `_cm`, `_pct`.
 * A fish "batch" is a Pond Stocking: fish have no crop cycles.
 */

import type { Bands as KpiBands } from "@/lib/bands";
import { call, type Envelope } from "@/lib/frappe";
import type { SeriesPoint } from "@/components/Sparkline";

const PREFIX = "upande_production.api.aquaculture.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

function clean(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out;
}

export type ISODate = string;
export type StockingStatus = "Growing" | "Harvested" | "Closed";
export type MortalityCause = "Low DO" | "Disease" | "Predation" | "Handling" | "Unknown";

export interface KpiValue {
  value: number | string | null;
  /** Oldest first; `week` holds the day or week-end date (see Sparkline). */
  series: SeriesPoint[];
  of?: number;
  dead?: number;
}

export interface PondOption {
  unit: string;
  label: string;
  active_stocking?: string | null;
}

// -- Pond batches ---------------------------------------------------------------

export interface GrowthPoint {
  date: ISODate;
  days: number;
  avg_weight_g: number;
}

export interface PondBatch {
  name: string;
  pond: string;
  pond_name: string;
  species: string;
  status: StockingStatus;
  source: string | null;
  notes: string | null;
  stocking_date: ISODate;
  stocked: number;
  stocking_weight_g: number;
  target_weight_g: number | null;
  target_date: ISODate | null;
  harvest_date: ISODate | null;
  feed_7d_kg: number;
  dead_7d: number;
  last_sampled: ISODate | null;
  sample_age_days: number | null;
  growth_curve: GrowthPoint[];
  live: number;
  dead: number;
  harvested: number;
  survival_pct: number | null;
  avg_weight_g: number;
  biomass_kg: number;
  feed_kg: number;
  harvest_kg: number;
  fcr: number | null;
  days_in_water: number;
  growth_g_day: number | null;
  projected_harvest_date: ISODate | null;
  projected_weight_g: number | null;
  days_to_target: number | null;
  on_track: boolean | null;
}

export interface PondBatchesPage {
  today: ISODate;
  bands: KpiBands;
  /** A growing batch not weighed within this many days is flagged; null until set on the crop. */
  sample_stale_days: number | null;
  batches: PondBatch[];
  kpis: {
    growing: KpiValue;
    live_fish: KpiValue;
    biomass_kg: KpiValue;
    fcr: KpiValue;
    survival_pct: KpiValue;
    harvested_kg: KpiValue;
  };
  form: { ponds: PondOption[]; species: string[]; statuses: StockingStatus[] };
}

export const getPondBatches = (a: { status?: string; unit?: string } = {}) =>
  rpc<PondBatchesPage>("pond_batches", clean(a));

export interface StockingInput {
  pond: string;
  species: string;
  stocking_date: ISODate;
  fingerlings_count: number;
  avg_weight_g: number;
  source?: string;
  target_harvest_weight_g?: number;
  target_harvest_date?: ISODate;
}
export const saveStocking = (data: StockingInput) => rpc<{ ok: boolean; name: string }>("save_stocking", { data });

export interface SamplingInput {
  pond: string;
  stocking?: string;
  sample_date: ISODate;
  sample_size: number;
  avg_weight_g: number;
}
export const saveSampling = (data: SamplingInput) => rpc<{ ok: boolean; name: string }>("save_sampling", { data });

export interface HarvestInput {
  stocking: string;
  harvest_date: ISODate;
  count: number;
  qty_kg: number;
  price_per_kg?: number;
  final?: boolean;
}
export const saveFishHarvest = (data: HarvestInput) =>
  rpc<{ ok: boolean; name: string; status: StockingStatus }>("save_fish_harvest", { data });

// -- Water quality ----------------------------------------------------------------

/** Safe water ranges from the pond's strain (else the crop); a limit the manager has not set is absent. */
export interface Bands {
  do_min?: number;
  ph_min?: number;
  ph_max?: number;
  temp_min?: number;
  temp_max?: number;
  ammonia_max?: number;
  nitrite_max?: number;
}

export interface ReadingFlag {
  metric: "do" | "ph" | "temp" | "ammonia" | "nitrite";
  value: number;
  message: string;
}

export interface Measures {
  dissolved_oxygen_mg_l: number | null;
  ph: number | null;
  temperature_c: number | null;
  ammonia_mg_l: number | null;
  nitrite_mg_l: number | null;
  secchi_cm: number | null;
}

export interface WaterReading extends Measures {
  name: string;
  pond: string;
  at: string;
  reader: string | null;
  notes: string | null;
  out_of_band: boolean;
  flags: ReadingFlag[];
}

export interface WaterPond {
  unit: string;
  label: string;
  readings: number;
  latest: WaterReading | null;
  status: "ok" | "alert" | "none";
  bands: Bands;
  out_of_band_count: number;
  min_do_mg_l: number | null;
  series: Array<Measures & { at: string; out_of_band: boolean }>;
}

export interface WaterAlert {
  pond: string;
  pond_name: string;
  at: string;
  metric: ReadingFlag["metric"];
  value: number;
  message: string;
}

export interface WaterQualityPage {
  from_date: ISODate;
  to_date: ISODate;
  bands: Bands;
  ponds: WaterPond[];
  alerts: WaterAlert[];
  readings: WaterReading[];
  kpis: {
    ponds_in_band: KpiValue;
    alerts: KpiValue;
    lowest_do_mg_l: KpiValue;
    avg_temp_c: KpiValue;
    readings: KpiValue;
  };
  form: { ponds: PondOption[]; now: string };
}

export const getWaterQuality = (a: { from_date?: string; to_date?: string; unit?: string } = {}) =>
  rpc<WaterQualityPage>("water_quality", clean(a));

export interface WaterReadingInput {
  pond: string;
  reading_datetime?: string;
  dissolved_oxygen_mg_l?: number;
  ph?: number;
  temperature_c?: number;
  ammonia_mg_l?: number;
  nitrite_mg_l?: number;
  secchi_cm?: number;
  notes?: string;
}
export const saveWaterReading = (data: WaterReadingInput) =>
  rpc<{ ok: boolean; name: string; out_of_band: boolean; flags: string }>("save_water_reading", { data });

// -- Feeding and mortality ------------------------------------------------------------

export interface DailyFeedMortality {
  date: ISODate;
  feed_kg: number;
  dead: number;
}

export interface FeedingPondRow {
  unit: string;
  label: string;
  feed_kg: number;
  feed_kg_per_day: number;
  dead: number;
  stocked: number | null;
  mortality_pct: number | null;
  top_cause: MortalityCause | null;
}

export interface FeedLogRow {
  name: string;
  pond: string;
  feed_date: ISODate;
  feed_type: string | null;
  kg_fed: number;
  feeding_times: string | null;
  times_fed: number;
}

export interface MortalityLogRow {
  name: string;
  pond: string;
  mortality_date: ISODate;
  dead_count: number;
  cause: MortalityCause;
  notes: string | null;
}

export interface FeedingMortalityPage {
  from_date: ISODate;
  to_date: ISODate;
  daily: DailyFeedMortality[];
  ponds: FeedingPondRow[];
  causes: Array<{ cause: MortalityCause; count: number }>;
  feed_log: FeedLogRow[];
  mortality_log: MortalityLogRow[];
  kpis: { feed_kg: KpiValue; feed_kg_per_day: KpiValue; dead: KpiValue; worst_pond: KpiValue };
  form: { ponds: PondOption[]; causes: MortalityCause[]; feed_types: string[]; today: ISODate };
}

export const getFeedingMortality = (a: { from_date?: string; to_date?: string; unit?: string } = {}) =>
  rpc<FeedingMortalityPage>("feeding_mortality", clean(a));

export interface FeedingInput {
  pond: string;
  feed_date: ISODate;
  kg_fed: number;
  feed_type?: string;
  feeding_times?: string;
}
export const saveFeeding = (data: FeedingInput) => rpc<{ ok: boolean; name: string }>("save_feeding", { data });

export interface MortalityInput {
  pond: string;
  mortality_date: ISODate;
  dead_count: number;
  cause: MortalityCause;
  notes?: string;
}
export const saveMortality = (data: MortalityInput) => rpc<{ ok: boolean; name: string }>("save_mortality", { data });
