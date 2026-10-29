# upande_production — design

Date: 2026-10-28 · Status: draft for approval · First client: Mutara (demo 2026-10-29)

## 1. Intent

Mutara runs avocado (Blocks A and B), 87 ha of irrigated fruit & vegetables on centre pivots, fish ponds and ~800 hives. Their production scope (planning, protocol tracking, labour-to-pay figures, block cost centres, forecasting, plan vs actual) needs one multi-crop production app, the way SCP is one multi-crop protection app. `upande-avocado` (teddy) is the base: it already does avocado blocks, fruit counts, dry matter, ripening, yield history, forecast/budget and five pages. We grow it into `upande_production`, add the plan → do → tick-off loop that upande_agriculture's `mona` branch runs for roses, and make it crop-agnostic.

Tomorrow is a very important demo on **desktop**. It must work functionally end to end on mutara.local with realistic data, not be a mock-up. Mobile comes after (the user will share the RN app link later); the server-side mobile endpoints are built now.

## 2. Goals (in demo priority)

1. **Avocado & Fruits/Vegetables, real and working:**
   - Places: farm → orchard block (avocado); farm → **pivot** → **pivot block** (the pizza slice) for F&V. Each block carries area, geometry (optional), and its own ERPNext **Cost Center**.
   - **Crop cycle** per block: crop/variety, planting date, expected harvest window, status. Avocado cycles are seasons on a perennial block; F&V cycles are plantings with rotation (one block, successive cycles).
   - **Protocol** as an optional template: a list of operations with day offsets from planting that *generates* plan tasks. Not mandatory, not a permanent fixture of a cycle (user: "crop protocol is not a permanent feature").
   - **Weekly plan + tick-off** (emulating agriculture `mona` Production Plan Form / productionUpdatePlanTask): supervisor plans tasks per block per week; each task is marked Open / In Progress / Done / Partly done / Skipped. Field work = "record if the work has been done completely".
   - **Deviation flag:** task done late vs due date, or skipped/partly done, or protocol task with no plan; surfaced on the plan and a deviations list.
   - **Value adders** (the app's name for casual labourers): each task's work is recorded per value adder with quantity done, unit, optional hours, rate and **pay value = qty × rate**. Pay stays a figure (another module integrates it later; no payroll/salary-slip posting).
   - **Block cost centre & profitability:** labour (pay values) + inputs/other (GL entries on the block's cost centre) vs harvest value → per-block cost and margin.
   - **Forecasting:** avocado keeps teddy's fruit-count/dry-matter/forecast/budget/history engine. F&V gets field-sample yield forecasts (sample → estimated block yield), harvest actuals, **plan vs actual** accuracy, historical trend, and **buyer commitments** (committed qty per week vs forecast → supportable/gap).
2. **Aquaculture & Apiary as working templates:** set up as crops (unit = Pond / Hive Group) with starter operations, running on the same plan/task/value-adder/cost-centre engine. Their specialised trackers (mortality & stocking density, water quality readings, colony health & swarms, biomass/honey forecasting) are listed as next phases, not built now.
3. **Mobile API** (`upande_production/mobile/api.py`, JSON-in/`frappe.response['data']`-out like mona): list crops/blocks/cycles, get week plan, update task status, record work per value adder, record harvest, record yield sample.
4. **Our own React frontend** (as livestock/SCP): `/production_app`, crop-namespaced sidebar.

## 3. Non-goals

- No payroll/salary component posting — pay is a reported figure.
- No React Native app build now (shell later, at `~/stive/code/reactnative/upande-production`, beside Upande-Scout and upande-livestock, when the user gives the link).
- No SCP work (another session/machine). No Pivot doctype in upande_core yet — held here, moved to core later.
- Livestock production forecasting: **not in this app**. Logged as a "Production" to-do under livestock `mutara-beef` for the other session.
- Aquaculture/apiary specialised trackers (see goal 2).

## 4. Anti-goals (failure even if it "works")

- Demo breaks on an empty state, a 500, or an unseeded page.
- Hard-coded crop/product names in logic — crops, unit types, operations and rates are data.
- Losing teddy's avocado data/behaviour, or his git history.
- `Co-Authored-By` trailers in any commit. Vertical accent strips on cards. Native selects/date inputs in page filters (FilterSelect pill standard).

## 5. Decided (by the user)

- New app **`upande_production`**, new **private** GitHub repo under the st-i-ve account (same credentials as upande_scp on kaitet.local), seeded from everything committed in `teddy5456/upande-avocado`.
- Branches: `main` first, then `mutara`; a `marginpar` branch later (marginpar will use this app too).
- Multi-crop like SCP. Crops for Mutara: Avocado, Fruits & Vegetables, Aquaculture, Apiary.
- Pivot = circular area; its pizza-slice parts are called **blocks** for vegetables. Held in this app until upande_core has it; user will define the unit and bed later.
- Value adders paid on work done; pay is a figure only.
- Reference: upande_agriculture `live` (crop cycle, protocol, forecast/projection) and `mona` (mobile production endpoints). Protocol is not permanent.
- Design: our own React frontend like livestock and SCP.
- Desktop working for the demo first; mobile later.

## 6. Design (builder's calls marked *[call]*)

### 6.1 App & repo
- Repo `st-i-ve/upande-production` (private). Import teddy's history (commit 9926c32), then a rename commit `upande_avocado` → `upande_production`. *[call]* Keep the `Avocado Yield` module and all 8 Avocado* doctypes **unchanged in name and fields** so teddy's data/APIs carry over; new generic doctypes live in a new `Production` module.
- On mutara.local: uninstall-free swap — install `upande_production`, migrate Avocado* doctypes' module ownership to it (as teddy did when extracting from core), then remove `upande_avocado` from the bench's apps.txt (archive the folder like the harvest move). *[call]*
- hooks: keep avocado doc_events + the `custom_expo_push_tokens` fixture.

### 6.2 Data model (module `Production`)
| DocType | Purpose / key fields |
|---|---|
| **Production Crop** | name (Avocado, Fruits & Vegetables, Aquaculture, Apiary), accent colour, icon key, unit labels (`parent_unit_label` e.g. Pivot, `unit_label` e.g. Block/Pond/Hive Group, `sub_unit_label` e.g. Row/Bed), yield UOM (kg, crates, kg fish, kg honey), enabled |
| **Production Unit** (tree) | unit_name, crop, farm (core Farm), unit_type (Orchard Block / Pivot / Pivot Block / Pond / Hive Group / Other), parent_production_unit, area_ha, geojson, cost_center (auto-created under a per-crop group CC), avocado_block_code (links Avocado Yield Block by code), status. **Pivot lives here** as unit_type. |
| **Field Activity** | crop, operation_name, work_uom (trees, crates, ha, beds, hives…), default_rate, category (Planting/Field care/Spray/Irrigation/Harvest/Other) |
| **Production Protocol** + child **Protocol Step** | crop, variety (optional), steps: operation, day_offset, repeat_every_days, repeat_count, planned_qty basis |
| **Crop Cycle** (named `Production Crop Cycle` to avoid clashing with ERPNext/agriculture `Crop Cycle`) | unit, crop, item/variety, cycle_type (Season/Planting/Pond Cycle/Hive Season), planting/start date, expected_harvest_start/end, protocol (optional link), status (Planned/Active/Harvesting/Closed), area_ha, previous_cycle (rotation) |
| **Production Plan** + child **Production Plan Task** | farm, crop, ISO year/week; tasks: unit, cycle, operation, planned_qty, uom, rate, due_date, supervisor (Employee), status (Open/In Progress/Done/Partly Done/Skipped), started_at, completed_at, done_qty, deviation (Late/Skipped/Partial/Unplanned, computed), note. One plan per farm × crop × week *[call — mona is per greenhouse; per crop-week reads better across 10+ blocks]* |
| **Value Adder Work** | date, employee (value adder), plan + task row id, unit, cycle, operation, qty, uom, hours, rate, **pay_value**, cost_center (from unit); submittable *[call]* so the pay figure is stable for the later integration |
| **Production Harvest** | date, unit, cycle, item, qty, uom, grade (optional), price_per_uom → value |
| **Yield Sample** | date, unit, cycle, sample size (plants/trees/m²), sampled yield, growth stage → est_unit_yield (scaled by area/plant count) |
| **Production Forecast** + child weeks | unit, cycle, season/year, week rows expected_qty (+ source: sample/manual/history) |
| **Buyer Commitment** | customer, crop, item, week/date, committed_qty |
| **Production Settings** (single) | default company, cost-centre parent per crop, week start, late tolerance days |

Avocado bridges: the avocado unit links its `Avocado Yield Block` by code; avocado forecast/plan-vs-actual pages read teddy's Fruit Count/Forecast/History doctypes for avocado and the generic Yield Sample/Forecast/Harvest for the rest.

### 6.3 Logic
- **Generate tasks from protocol:** for a cycle with a protocol, "Generate week" creates plan tasks whose due date falls in that week. Editable afterwards.
- **Deviation:** computed on save: Late if completed_at.date > due_date + tolerance; Partial if Partly Done or done_qty < planned_qty; Skipped; Unplanned for work recorded without a planned task.
- **Cost:** block cost = Σ submitted Value Adder Work pay_value + Σ GL Entry debit on the block's cost centre (expense accounts) for the period; revenue = Σ Production Harvest value. No GL posting from this app.
- **Forecast accuracy:** per unit per week, forecast vs harvest actual, error %.
- **Commitment cover:** Σ forecast for crop/week vs Σ commitments → supportable/surplus/gap.

### 6.4 Frontend `/production_app` (React 19 + Vite + Tailwind, copied from the livestock frontend shell)
Crop switcher + crop-namespaced routes `#/<crop>/<view>`. Pages:
1. **Overview** — tiles: active cycles, this week's tasks done %, deviations, labour cost MTD, forecast vs committed; per-block table.
2. **Blocks** — units tree (farm → pivot → blocks), area, current cycle, cost to date; map when geojson exists.
3. **Crop Cycles** — list, create, rotation history per block.
4. **Weekly Plan** — week picker, plan grid by block; add tasks, generate from protocol, tick-off with value-adder work capture (qty per person), status pills, deviation badges.
5. **Value Adders** — work done and pay figures per person / day / block, export.
6. **Block Costs** — labour + inputs vs harvest value per block, margin.
7. **Forecast** — avocado: links/embeds teddy's Outlook, Harvest Calendar, Picking Plan, Dry Matter pages; F&V: samples → forecast, plan vs actual, trend, buyer commitments.
8. **Settings** — crops, operations & rates, protocols.
Livestock UI standards apply: Poppins, skeletons in place, floating toasts, FilterSelect pills, no strip accents.

### 6.5 Demo data (mutara.local, idempotent seed script)
Farm Mutara; Avocado Block A & B (with Avocado Yield Block records and a season cycle, fruit counts, forecasts, yield history); 3 pivots × slices summing ~87 ha with 4–6 vegetable/fruit crops in rotation; aquaculture: a few ponds; apiary: hive groups; operations + rates per crop; ~20 value-adder employees; 4 weeks of plans (past weeks mostly done with some late/skipped, current week mixed); harvests, samples, forecasts, two buyer commitments. Per-block cost centres created.

### 6.6 Builder-check rulings (builder's calls unless noted)
- **Site state (verified):** mutara.local is empty — 0 Farms, 0 Avocado Yield Blocks, 0 Employees, company `Mutara` (MUT) only. The app swap needs no data migration; the seed creates everything.
- **Revenue:** all crops, avocado included, record harvests in `Production Harvest`. Avocado price defaults from the avocado forecast's price_per_kg; teddy's Yield History stays the season-level history source.
- **Input costs:** the seed posts real Journal Entries (expense accounts from Mutara's standard CoA) on block cost centres, so margins show inputs. The app itself never posts to the GL.
- **Unplanned protocol work:** the deviations list is computed on read. It flags a protocol step that fell due in a past week but has no matching plan task, and Unplanned work. No scheduled job.
- **Weeks:** ISO weeks, Monday start. The "week start" setting is dropped.
- **Roles:** Production Manager can do everything and sees pay. Production Supervisor plans, ticks off and records work, and sees pay for their own entries. Production Viewer sees only plans and dashboards, with pay hidden.
- **Value Adder Work:** auto-submitted on capture. Managers cancel and amend corrections. Cost figures read submitted rows only.
- **Value adders are Employees** (HRMS is installed), with employment type Casual and a `Value Adder` designation, so the later payroll module can link them.
- **Cost centres:** Mutara → crop group → pivot group (F&V) → block leaf. Aggregation runs over the subtree.
- **Mutara F&V crops (user):** potatoes, cabbages, onions, passion fruit. Passion fruit is a perennial on its own pivot blocks, with season cycles like avocado; potatoes, cabbages and onions rotate as plantings. Areas, tree counts and pivot sizes are invented to be realistic (Block A/B a few ha each, ~4 pivots totalling ~87 ha) until the user supplies real figures; the seed takes them from one config dict so swapping is a single edit.
- **Build method (user):** Sonnet agents implement in parallel; Opus does review and decisions.
- **Cut order if time runs short:** the Settings page (fall back to desk forms), then Value Adders export. Overview, Blocks, Cycles, Weekly Plan, Forecast and Block Costs stay.

## 7. Left to the builder
Exact field names, naming series, page component breakdown, chart choice, seed numbers, API payload shapes (follow mona's style), test coverage depth for a demo-tomorrow build (backend logic tests for deviation/pay/cost/accuracy at minimum).

## 8. Constraints
- Frappe v16.24 / ERPNext v16.25, bench `/mnt/data/code/frappe16-mutara`, site mutara.local (:8003, https://mutara.132.145.18.63.nip.io).
- Never restart/reset the shared MariaDB. No Kaitet MCP. No Co-Authored-By trailers. Push only the new repo's branches once the user OKs.
