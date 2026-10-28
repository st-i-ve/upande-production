import type { Crop } from "@/lib/api";
import type { FeedingMortalityPage, PondBatch, PondBatchesPage, WaterQualityPage } from "@/lib/aquaculture-api";

export const FISH: Crop = {
  name: "Aquaculture", crop_key: "aquaculture", accent_color: "#2b6f9e", icon_key: "fish",
  unit_label: "Pond", parent_unit_label: "", sub_unit_label: "", yield_uom: "Kg",
};

const series = (vals: number[]) => vals.map((value, i) => ({ week: `2026-10-${10 + i}`, value }));
const ponds = [
  { unit: "Pond 1", label: "Pond 1", active_stocking: "PST-1" },
  { unit: "Pond 2", label: "Pond 2", active_stocking: null },
  { unit: "Pond 4", label: "Pond 4", active_stocking: "PST-4" },
];

export const batch = (over: Partial<PondBatch> = {}): PondBatch => ({
  name: "PST-1", pond: "Pond 1", pond_name: "Pond 1", species: "Tilapia", status: "Growing", source: "Sagana", notes: null,
  stocking_date: "2026-08-19", stocked: 8000, stocking_weight_g: 5, target_weight_g: 450, target_date: "2027-02-15", harvest_date: null,
  feed_7d_kg: 183, dead_7d: 18, last_sampled: "2026-10-28", sample_age_days: 0,
  growth_curve: [{ date: "2026-08-19", days: 0, avg_weight_g: 5 }, { date: "2026-10-28", days: 70, avg_weight_g: 131.6 }],
  live: 7784, dead: 216, harvested: 0, survival_pct: 97.3, avg_weight_g: 131.6, biomass_kg: 1024.4, feed_kg: 1482.4, harvest_kg: 0,
  fcr: 1.51, days_in_water: 70, growth_g_day: 2.37, projected_harvest_date: "2027-03-12", projected_weight_g: 463, days_to_target: 135, on_track: true,
  ...over,
});

export const batchesPage = (): PondBatchesPage => ({
  today: "2026-10-28",
  batches: [
    batch(),
    batch({ name: "PST-3", pond: "Pond 3", pond_name: "Pond 3", status: "Harvested", live: 0, harvested: 4573, harvest_kg: 1696.8, harvest_date: "2026-10-22", biomass_kg: 0, projected_harvest_date: null, on_track: null, survival_pct: 91.5 }),
    batch({ name: "PST-4", pond: "Pond 4", pond_name: "Pond 4", on_track: false, survival_pct: 88.2, live: 6445 }),
  ],
  kpis: {
    growing: { value: 2, series: series([1, 2, 2]) },
    live_fish: { value: 14229, series: series([12000, 13000, 14229]) },
    biomass_kg: { value: 2140.7, series: series([1500, 1800, 2140.7]) },
    fcr: { value: 1.56, series: series([1.5, 1.55, 1.56]) },
    survival_pct: { value: 95.7, series: series([97, 96.5, 95.7]) },
    harvested_kg: { value: 1696.8, series: [] },
  },
  form: { ponds, species: ["Tilapia", "Catfish"], statuses: ["Growing", "Harvested", "Closed"] },
});

const m = (o: Partial<WaterQualityPage["ponds"][0]["series"][0]> = {}) => ({
  at: "2026-10-27 06:00", dissolved_oxygen_mg_l: 5.2, ph: 7.4, temperature_c: 26.4, ammonia_mg_l: 0.2, nitrite_mg_l: 0.1, secchi_cm: 30, out_of_band: false, ...o,
});

export const waterPage = (): WaterQualityPage => ({
  from_date: "2026-10-15", to_date: "2026-10-28",
  bands: { do_min: 4, ph_min: 6.5, ph_max: 8.5, temp_min: 25, temp_max: 30, ammonia_max: 0.5, nitrite_max: 0.3 },
  ponds: [
    {
      unit: "Pond 1", label: "Pond 1", readings: 2, status: "ok", out_of_band_count: 0, min_do_mg_l: 5.2,
      latest: { name: "W1", pond: "Pond 1", ...m({ at: "2026-10-28 06:00" }), reader: null, notes: null, out_of_band: false, flags: [] } as never,
      series: [m(), m({ at: "2026-10-28 06:00" })],
    },
    {
      unit: "Pond 4", label: "Pond 4", readings: 2, status: "alert", out_of_band_count: 1, min_do_mg_l: 2.4,
      latest: { name: "W2", pond: "Pond 4", ...m({ at: "2026-10-28 06:00", dissolved_oxygen_mg_l: 2.4, out_of_band: true }), reader: null, notes: "aerators off", out_of_band: true,
        flags: [{ metric: "do", value: 2.4, message: "Dissolved oxygen 2.4 mg/L is under 4" }] } as never,
      series: [m({ dissolved_oxygen_mg_l: 5.8 }), m({ at: "2026-10-28 06:00", dissolved_oxygen_mg_l: 2.4, out_of_band: true })],
    },
  ],
  alerts: [{ pond: "Pond 4", pond_name: "Pond 4", at: "2026-10-28 06:00", metric: "do", value: 2.4, message: "Dissolved oxygen 2.4 mg/L is under 4" }],
  readings: [],
  kpis: {
    ponds_in_band: { value: 1, of: 2, series: [] },
    alerts: { value: 1, series: series([0, 0, 1]) },
    lowest_do_mg_l: { value: 2.4, series: series([5, 5.1, 2.4]) },
    avg_temp_c: { value: 27.4, series: series([27, 27.2, 27.4]) },
    readings: { value: 4, series: [] },
  },
  form: { ponds: [{ unit: "Pond 1", label: "Pond 1" }, { unit: "Pond 4", label: "Pond 4" }], now: "2026-10-28 09:30" },
});

export const feedingPage = (): FeedingMortalityPage => ({
  from_date: "2026-10-01", to_date: "2026-10-28",
  daily: [{ date: "2026-10-26", feed_kg: 80, dead: 3 }, { date: "2026-10-27", feed_kg: 70, dead: 240 }, { date: "2026-10-28", feed_kg: 68, dead: 7 }],
  ponds: [
    { unit: "Pond 1", label: "Pond 1", feed_kg: 900, feed_kg_per_day: 32.1, dead: 20, stocked: 8000, mortality_pct: 0.25, top_cause: "Unknown" },
    { unit: "Pond 4", label: "Pond 4", feed_kg: 658.1, feed_kg_per_day: 23.5, dead: 398, stocked: 7000, mortality_pct: 5.69, top_cause: "Low DO" },
  ],
  causes: [{ cause: "Low DO", count: 335 }, { cause: "Disease", count: 85 }],
  feed_log: [{ name: "F1", pond: "Pond 1", feed_date: "2026-10-28", feed_type: "Grower Pellet 4mm", kg_fed: 32.5, feeding_times: "06:30, 17:00", times_fed: 2 }],
  mortality_log: [{ name: "M1", pond: "Pond 4", mortality_date: "2026-10-23", dead_count: 240, cause: "Low DO", notes: "Aerators were off" }],
  kpis: {
    feed_kg: { value: 1558.1, series: series([80, 70, 68]) },
    feed_kg_per_day: { value: 55.6, series: [] },
    dead: { value: 418, series: series([3, 240, 7]) },
    worst_pond: { value: "Pond 4", series: [], dead: 398 },
  },
  form: { ponds, causes: ["Low DO", "Disease", "Predation", "Handling", "Unknown"], feed_types: ["Starter Crumble", "Grower Pellet 4mm"], today: "2026-10-28" },
});
