# No hardcoded business data in Production

Date: 2026-10-29. User: "I hope the data on the production front end is not hardcoded UI; if it is, build a
backend we get that data from." An audit (2026-10-29) found no mock data in the desk app (every page loads
through `call(...)`), but the backend returns hardcoded estate figures and model constants, and a few
thresholds are duplicated in the UI. This design moves every one of them to a doctype, a setting, or a
computation from recorded data. The user is mapping the avocado blocks themselves (GeoJSON), so map shapes
are out of scope.

## Rules
- No literal estate figures in code. A number shown to a manager comes from records (harvests, yield
  history, teams, tests) or from a setting a manager can edit in Settings.
- When the records needed don't exist yet, the UI says so ("No delivered season recorded yet") instead of
  showing a stand-in number.
- Thresholds that colour a KPI live in one place (the backend) and are sent to the UI; the UI never keeps its
  own copy or fallback (`?? 24` etc. go).
- Settings are estate-level (not per user). Model parameters that differ by crop/variety live on Production
  Crop / Production Variety; estate-wide ones on Production Settings.
- Current values become the seeded defaults, so nothing changes visibly on the demo until edited — except the
  invented 2026 season, which is removed.

## Avocado model (api/avocadoapi.py, api/avocado.py, api/avocadolabour.py, api/avocadomaturity.py)
1. `SEASON_CALIBRATION` (literal 2026 season) and the "delivered" fallback: remove. Calibration factor =
   delivered ÷ estimated per past season, computed from Avocado Yield History (delivered) and the manual
   Avocado Production Forecast / Budget (estimated), averaged over the seasons that have both; none → factor
   1.0 and the Estimate accuracy KPI shows "no delivered season yet". Delivered this season comes only from
   Yield History / Harvest Log / Production Harvest.
2. Yield by age curve → child table **Production Variety Yield Age** (`age_years` Int, `kg_per_plant` Float)
   on Production Variety (`yield_by_age`). Seed Hass/Fuerte with today's ESTATE_AGE_CURVE.
   `MIN_TREES_TO_OVERRIDE_CURVE` → Production Crop `min_trees_to_override_curve` (default 1000).
3. Biennial bearing → Production Variety `biennial_off_factor` Float (default empty = no biennial effect;
   seed 0.58 for Hass) and `on_years` Select `Even\nOdd`.
4. Late crop share → from the variety's flowering seasons `crop_share_pct` (the season named/marked late);
   Production Variety `late_crop_share_pct` as fallback when no seasons (seed 84.6).
5. Price per kg → Production Crop `price_per_kg` Currency (seed 95), estate-level; the page may still let a
   manager try another price for the session but it no longer saves per user (a manager with Production
   Manager role can save it to the crop setting).
6. Crew size → active members of the crop's Harvest Teams; Production Crop `harvest_days_per_week` Int
   (default 5). The per-user crew default goes (same session-only override as price).
7. Picking rate → Production Crop `default_kg_per_picker_day` (450), `plausible_kg_per_picker_day_min`/`max`
   (150/1200).
8. Crate weight → Production Crop `avg_kg_per_crate` (exists) everywhere; KG_PER_CRATE goes.
9. Dry matter → avocado minimum = variety `dry_matter_target_pct` else crop's (exists; seed 24); maximum →
   Production Crop `dry_matter_max_pct` (34). The UI uses `minimum_pct` from the API ("crosses N%").
10. Model constants → Production Crop: `dm_gain_per_week` (0.7), `stale_sample_weeks` (8), `default_pick_weeks`
    (6); `SEASON_SHIFT_DAYS` stays a code constant (52 weeks is calendar maths). Fix the "six weeks" help text
    to read the setting. COUNT_SIZES (export count bands) → child table **Production Crop Count Size**
    (`count`, `min_g`, `max_g`) on Production Crop.
11. `VS_CURVE_BANDS` → Production Settings table **Production Band** rows with `band_set = "Vs curve"`
    (see 12) — or keep as code if it is purely a colour scale; builder's call, documented.

## Thresholds (apiary, aquaculture, F&V, forecast)
12. New child doctype **Production Band** (`band_set` Data, `label` Data, `metric` Data, `min` Float, `max`
    Float, `severity` Select `Good\nWatch\nCritical`) on Production Settings (`bands`), returned by one
    endpoint `api.production.get_bands()` → `{band_set: [rows]}` and included in each page's payload where
    used. Band sets: Forecast error (10/25 %), Estimate accuracy (≥90 good), Irrigation % of target
    (50/90/125, and "on target" ≥90), Fish survival (<90 critical), Queen status (queenright ≥95 good, ≥80
    weak — the UI's <90 goes), Grade A share (<60 warn).
13. Apiary: mite threshold/watch (3.0/2.0) and honey moisture limit (20.0) → Production Crop fields on Apiary
    (`mite_threshold`, `mite_watch`, `honey_moisture_limit`); the UI fallbacks go.
14. Aquaculture water-quality bands → child table **Production Water Band** (`parameter` Select DO / pH /
    Temperature / Ammonia / Nitrite, `min`, `max`, `unit`) on Production Variety (per species/strain; seed
    tilapia values), falling back to Production Crop. Weight-sample stale days → Production Crop
    `sample_stale_days` (10). Feed types → Select options on the feeding log fed from a Production Crop child
    table **Production Feed Type** (or Item group of feed items if feed is stocked — builder checks).
15. F&V irrigation weekly target → Production Variety `irrigation_mm_week` with Production Crop default
    `irrigation_mm_week` (25); the missing Production Settings field the code looks for is dropped.
    GRADE_ORDER / TOP_GRADES → Production Crop child table **Production Grade** (`grade`, `rank`,
    `is_top_grade`).

## Settings UI
Settings gets a "Crop model" tab (per crop: price, crate weight, picking rates, days/week, DM, model
constants, count sizes, grades, feed types, apiary/aquaculture limits) and a "Bands" tab; Varieties dialog
gains yield-by-age, biennial, late share, water bands, irrigation target. Writes need Production Manager.

## Tests
Backend: each former constant read from its setting; changing a setting changes the API output; no
SEASON_CALIBRATION / literal fallback remains (grep test for the removed names); empty history → explicit
"none" state. Desk: no `??` business fallbacks; KPIs coloured from API bands.
