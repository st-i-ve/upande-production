# Splitting upande_agriculture into three apps (Margin Par)

Date: 2026-11-04. Decided by the user: retire `upande_agriculture` and spread it over three apps.
Phase 1 (this document) = **functional mirror**: once the three apps are installed, Margin Par must
work exactly as `upande_agriculture` `live` did. Separate UIs come later.

## Where things are

| App | Repo / path (Margin Par bench) | Branch | Module for ported doctypes |
|---|---|---|---|
| upande_production | `/mnt/data/code/frappe16-marginpar/apps/upande_production` (remote `mutara` = the Mutara clone, `origin` = st-i-ve/upande-production) | `marginpar` | **Crop Production** (new) |
| upande_crop_material_planning | `/mnt/data/code/frappe16-marginpar/apps/upande_crop_material_planning` (new, no remote yet) | `marginpar` | **Upande Crop Material Planning** (scaffold module) |
| upande_propagation | `/mnt/data/code/frappe16-marginpar/apps/upande_propagation` (origin Jimmypaps001/upande-propagation) | `marginpar` (from `james`) | **Upande Propagation** (existing) |
| upande_agriculture (SOURCE, read-only) | `/mnt/data/code/frappe16-marginpar/apps/upande_agriculture` | `live` @ 54bdaad | — uninstalled from marginpar.local, folder kept |

Site: `marginpar.local` (bench `/mnt/data/code/frappe16-marginpar`, port 8002). It is an empty dev copy.

Dependency direction (one way only): `upande_core` ← `upande_production` ← `upande_crop_material_planning`
and `upande_production` ← `upande_propagation`. Production never imports planning or propagation code.
Each app registers its **own** `doc_events` / scheduler entries for the behaviour it owns (e.g. planning
hooks Stock Entry on_submit to update forecast actuals; production hooks it for harvest things).

## Doctype map (names and fieldnames stay EXACTLY as in agriculture — live data must survive)

**upande_production — module "Crop Production"** (field execution)
greenhouse, greenhouse_bed, greenhouse_bed_range, bed_range, greenhouse_variety, greenhouse_replanting_log,
greenhouse_uprooting_log, replanting_log, uprooting_log, employee_greenhouse, item_greenhouses,
crop_cycle, crop_cycle_bed, crop_cycle_uproot, crop_cycle_variety,
crop_protocol, crop_protocol_flush, crop_protocol_grade_mix, crop_protocol_growth_stage,
crop_protocol_length_distribution (protocol + all its child tables stay together; planning reads them),
cut_stage, bucket_reuse_anomaly, scan_location_mapping, scan_location_mapping_items,
production_plan_form, production_plan_task, production_plan_variety, irrigation_plan_task,
crop_protection_plan_task,
crop_type and agriculture_settings — **union of fields** from agriculture + propagation
(crop_type: crop_type_name, description; agriculture_settings: week_one_rule, week_start_day,
week_rule_help, days_to_zero_bending, days_to_expected_production). Propagation drops its copies.

**upande_crop_material_planning** (planning output: stems per week per grade)
production_forecast, production_forecast_week, production_projection, projection_week,
page production_budget, www budget-forecast, public css/budget.css + lib/jspreadsheet.

**upande_propagation** — flower_trial (links Propagation Batch, promotes to Crop Cycle), plus the
seedling-request / propagation-batch mobile endpoints.

## Code map (agriculture file → owner)

- `plan.py`, `farm_map.py` (+ `data/*.json`), `controllers.py` crop-cycle / greenhouse / plan-form hooks,
  `todo_helpers.py`, `stock_entry_connections.py`, `weekcal.py` (shared helper; planning imports it from
  production), `setup/build_crop_protocols.py`, `setup/sync_doctypes.py`, scheduled `release_stale_buckets`
  and `_rollup_plan_tasks` → **production**.
- `budget.py`, `projection_calc.py`, `setup/forecasting_cycles.py`, scheduled `rollup_actuals` /
  `_refresh_forecast_actuals`, Stock Entry on_submit/on_cancel forecast-actuals update, `_seasonal_factor_map`
  if only planning uses it → **planning**.
- `api.py`: week summary, budget grid, projection/aggregated-week edits, prior-year actuals,
  regenerate_projection → planning; mark_cycle_harvestable, submit_production_plan, list_active_cycles →
  production; promote_trial_to_cycle → propagation.
- `mobile/api.py` (37 endpoints): harvest/grading/bucket/greenhouse/crop-cycle/plan-form/uproot/replant/
  rejects/telemetry → production; projection + revised forecast → planning; seedling request,
  propagation batch/log, grower candidates → propagation.
- Workspaces "Agriculture" and "Roses Production", sidebar `roses_production`, Custom HTML Blocks,
  Scan Location Mapping fixtures → production. `maintenance.py` one-offs are not ported (note them).

## Rules every port follows

1. **Old method paths keep working.** Mark's roses mobile app and desk JS call
   `upande_agriculture.mobile.api.X` / `upande_agriculture.api.X`. Each app adds
   `override_whitelisted_methods = {"upande_agriculture.mobile.api.X": "<new path>", ...}` for the
   endpoints it now owns. Doctype JS / pages are updated to call the new paths directly.
2. **Ownership patch for live.** Each app adds a `[pre_model_sync]` patch that, for every doctype it took,
   updates `tabDocType.module` (and Report/Page/Workspace/Custom HTML Block/Workspace Sidebar rows) from
   "Upande Agriculture" to its own module when the row exists. No-op on a fresh site. This is how live
   Margin Par keeps its records. Agriculture's historic patches are not copied.
3. No `upande_agriculture` imports anywhere when done (`grep -r upande_agriculture` only finds the
   override map, the ownership patch and comments).
4. Tests from `upande_agriculture/tests` move with the code they test.
5. Same names as ERPNext/HRMS/other installed apps are forbidden (that trap already bit us once).

## Clash with existing upande_production doctypes

upande_production already had `Production Forecast`, `Production Forecast Week`, `Production Plan Task`.
They are renamed on `main` (affects Mutara; in-place pre_model_sync rename patch like Field Activity):
Production Forecast → **Crop Forecast**, Production Forecast Week → **Crop Forecast Week**,
Production Plan Task → **Work Plan Task**. `main` is then merged into `marginpar`.

## Later (not phase 1)

Separate UIs per app; merging the two forecast engines (kg by tree age vs stems by flush/grade);
Margin Par crops in Production Crop: Standard Roses / Spray Roses / Summer Flowers
(Standard Roses → Rose → Candid; Summer Flowers → Eryngium → Orion); live migration runbook.
