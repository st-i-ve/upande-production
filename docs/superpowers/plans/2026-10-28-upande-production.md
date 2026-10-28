# upande_production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A multi-crop production app (avocado, fruit & vegetables working; aquaculture and apiary as templates) running on mutara.local with a React desk frontend at `/production_app`, a mobile API, and seeded demo data, ready for a demo on 2026-10-29.

**Architecture:** Frappe app `upande_production` (renamed from teddy's upande-avocado; the `Avocado Yield` module stays untouched). A new `Production` module holds generic doctypes. Pure logic lives in `upande_production/production/logic/` and is unit-tested. It is wrapped by whitelisted desk endpoints (`upande_production/api/production.py`, which return an `{"error"}` envelope) and by mona-style mobile endpoints (`upande_production/mobile/api.py`). The React 19 + Vite + Tailwind frontend in `frontend/` is copied from the upande_livestock shell, built to `upande_production/public/dist` and served by `www/production_app.py`.

**Tech Stack:** Frappe 16.24 / ERPNext 16.25 / HRMS 16.9 (Python 3.14), React 19, Vite, Tailwind v4, Radix, lucide-react, vitest.

**Spec:** `docs/superpowers/specs/2026-10-28-upande-production-design.md`

## Global Constraints

- Paths: app at `/mnt/data/code/frappe16-mutara/apps/upande_production` on branch `main` (the build line; `mutara` is fast-forwarded to it at the end). Bench `/mnt/data/code/frappe16-mutara`, site `mutara.local` (company `Mutara`, abbr `MUT`, currency KES).
- **Commits: never add a `Co-Authored-By` trailer.** Never pass `-c user.name/-c user.email`; the git identity is already correct (st-i-ve).
- Never restart, reset or reconfigure MariaDB. Never use any Kaitet MCP. Don't touch other apps' code. The only exception is Task 9 (a docs file in upande_livestock).
- Don't rename or change the fields of the 8 `Avocado*` doctypes or the files in `upande_production/avocado_yield/`, `api/avocado*.py` or `www/avocado*`.
- Crop, unit-type, operation and rate values are **data**. No branching on crop names in Python or TSX: use `crop_key` / fields.
- UI standards (from livestock/SCP): Poppins with tabular figures; skeletons in place while loading, never a blank page; floating toasts (`components/Toast.tsx`); page filters use the FilterSelect pill, never a native `<select>` or `<input type=date>` in a filter row; **no vertical accent strips / coloured left-border bars on cards**; crop accent via icon/text colour or a pill.
- Terminology: casual labourers are **"Value Adders"** in every UI string.
- Weeks are ISO weeks, Monday start.
- Endpoints never raise to the browser. Desk endpoints return `{"error": "<message for a farm user>"}`. Mobile endpoints set `frappe.response['data'] = {...}`.
- Run Python tests with: `cd /mnt/data/code/frappe16-mutara && bench --site mutara.local run-tests --app upande_production --module <dotted.module>`.

## Review Focus

1. **Empty states:** a crop with no units, cycles or plan for the chosen week must return empty lists, not errors, and every page must render an empty state, not a crash. (Task 4: `test_endpoints_empty_crop`; Tasks 7–8 render empty states.)
2. **Recording work twice on a task:** a second capture must not double-count. `done_qty` is the sum of the task's submitted Value Adder Work. A status change with no entries creates no work. (Task 3: `test_record_twice_sums_not_duplicates`, `test_status_only_creates_no_work`.)
3. **ISO week edges:** 2026 has 53 weeks. Week 53 must run 2026-12-28 to 2027-01-03, and week 1 of 2027 starts 2027-01-04. (Task 3: `test_iso_week_bounds_53`.)
4. **Group units:** the costs of a pivot (a group) must roll up from its blocks, and a block with no GL entries must show 0 inputs, not vanish. (Task 4: `test_block_costs_rollup_and_zero`.)
5. **Pay visibility:** a Production Viewer must never receive `rate` or `pay_value` (null). (Task 4: `test_viewer_gets_no_pay`.)

---

### Task 1: Production doctypes, roles, settings

**Files:**
- Create: `upande_production/production/__init__.py`, `upande_production/production/doctype/<snake>/{__init__.py,<snake>.json,<snake>.py}` for every doctype below
- Modify: `upande_production/modules.txt` (add the line `Production`), `upande_production/hooks.py` (add `fixtures` entries for Role `Production Manager`, `Production Supervisor`, `Production Viewer`)
- Create: `upande_production/fixtures/role.json`
- Test: `upande_production/production/tests/__init__.py`, `upande_production/production/tests/test_doctypes.py`

**Interfaces — Produces** (module `Production`; every non-child doctype gives Production Manager full rights, Supervisor read/write/create (submit on Value Adder Work), Viewer read; System Manager full):

| DocType | naming | fields (fieldname:type[options]) |
|---|---|---|
| Production Crop | `field:crop_name` | crop_name:Data req unique, crop_key:Data req unique (slug, e.g. `avocado`, `fruits-vegetables`, `aquaculture`, `apiary`), accent_color:Color, icon_key:Data, parent_unit_label:Data, unit_label:Data req, sub_unit_label:Data, yield_uom:Link[UOM], default_cycle_type:Select[Season/Planting/Pond Cycle/Hive Season], enabled:Check default 1, sort_order:Int |
| Production Unit | `field:unit_name`, **is_tree** with `nsm_parent_field: parent_production_unit` | unit_name:Data req unique, crop:Link[Production Crop] req, farm:Link[Farm], unit_type:Select[Orchard Block/Pivot/Pivot Block/Pond/Hive Group/Other] req, is_group:Check, parent_production_unit:Link[Production Unit], lft/rgt/old_parent (standard tree), area_ha:Float, plant_count:Int, geojson:Long Text, cost_center:Link[Cost Center], avocado_block_code:Data, status:Select[Active/Fallow/Retired] default Active, company:Link[Company] |
| Production Operation | `OP-.#####`, title_field operation_name | crop:Link[Production Crop] req, operation_name:Data req, category:Select[Planting/Field Care/Nutrition/Spray/Irrigation/Harvest/Husbandry/Other], work_uom:Link[UOM], default_rate:Currency, is_harvest:Check |
| Production Protocol | `field:protocol_name` | protocol_name:Data req, crop:Link[Production Crop] req, item:Link[Item], steps:Table[Production Protocol Step] |
| Production Protocol Step (child) | — | operation:Link[Production Operation] req, day_offset:Int req, repeat_every_days:Int, repeat_count:Int default 1, planned_qty:Float, note:Data |
| Production Crop Cycle | `CYC-.YYYY.-.####`, title_field title | title:Data (set `"{unit} · {item or crop}"`), unit:Link[Production Unit] req, crop:Link[Production Crop] (fetch_from unit.crop), item:Link[Item], cycle_type:Select (same options as above), start_date:Date req, expected_harvest_start:Date, expected_harvest_end:Date, protocol:Link[Production Protocol], status:Select[Planned/Active/Harvesting/Closed] default Active, area_ha:Float (fetch_from unit.area_ha), plant_count:Int, previous_cycle:Link[Production Crop Cycle], notes:Small Text |
| Production Plan | `PLAN-.YYYY.-.#####` | farm:Link[Farm], crop:Link[Production Crop] req, plan_year:Int req, plan_week:Int req, week_start:Date ro, week_end:Date ro, company:Link[Company], tasks:Table[Production Plan Task], notes:Small Text |
| Production Plan Task (child) | — | unit:Link[Production Unit] req, cycle:Link[Production Crop Cycle], operation:Link[Production Operation] req, operation_name:Data (fetch_from operation.operation_name), planned_qty:Float, uom:Link[UOM], rate:Currency, due_date:Date req, supervisor:Link[Employee], status:Select[Open/In Progress/Done/Partly Done/Skipped] default Open, started_at:Datetime, completed_at:Datetime, done_qty:Float ro, deviation:Select[\n/Late/Partial/Skipped] ro, protocol_ref:Data ro, note:Small Text |
| Value Adder Work | `VAW-.YYYY.-.#####`, **is_submittable** | work_date:Date req, employee:Link[Employee] req, employee_name:Data (fetch), plan:Link[Production Plan], plan_task:Data, unit:Link[Production Unit] req, crop:Link[Production Crop], cycle:Link[Production Crop Cycle], operation:Link[Production Operation] req, qty:Float req, uom:Link[UOM], hours:Float, rate:Currency, pay_value:Currency ro, cost_center:Link[Cost Center], company:Link[Company], unplanned:Check ro, amended_from |
| Production Harvest | `HRV-.YYYY.-.#####` | harvest_date:Date req, unit:Link[Production Unit] req, crop:Link[Production Crop], cycle:Link[Production Crop Cycle], item:Link[Item], qty:Float req, uom:Link[UOM], grade:Data, price_per_uom:Currency, value:Currency ro |
| Yield Sample | `YS-.YYYY.-.#####` | sample_date:Date req, unit:Link[Production Unit] req, crop:Link[Production Crop], cycle:Link[Production Crop Cycle], growth_stage:Data, sample_basis:Select[Plants/Trees/Square Metres] req, sample_size:Float req, sampled_yield:Float req, uom:Link[UOM], unit_population:Float, est_unit_yield:Float ro |
| Production Forecast | `FC-.YYYY.-.#####` | unit:Link[Production Unit] req, crop:Link[Production Crop], cycle:Link[Production Crop Cycle], season:Int, source:Select[Sample/Manual/History], uom:Link[UOM], weeks:Table[Production Forecast Week], total_expected:Float ro |
| Production Forecast Week (child) | — | week_start:Date req, iso_year:Int ro, iso_week:Int ro, expected_qty:Float |
| Buyer Commitment | `BC-.YYYY.-.#####` | customer:Link[Customer] req, crop:Link[Production Crop] req, item:Link[Item], week_start:Date req, iso_year:Int ro, iso_week:Int ro, committed_qty:Float req, uom:Link[UOM], price_per_uom:Currency, status:Select[Open/Confirmed/Delivered/Cancelled] default Open |
| Production Settings (single) | — | company:Link[Company], late_tolerance_days:Int default 1, cost_center_parent:Link[Cost Center] |

Controllers stay empty (`pass`) in this task. Task 3 fills them in.

- [ ] **Step 1:** Write `test_doctypes.py::TestDoctypes.test_all_doctypes_exist`. For each doctype name above, assert `frappe.db.table_exists(name)` for non-singles, and `frappe.get_meta(name).is_submittable == 1` only for Value Adder Work. Assert that `frappe.get_meta("Production Unit").is_tree` is truthy and that `frappe.db.exists("Role", r)` holds for the 3 roles.
- [ ] **Step 2:** Run it and expect FAIL.
- [ ] **Step 3:** Create the JSONs. Copy the style of `upande_production/avocado_yield/doctype/avocado_yield_block/avocado_yield_block.json` (module `Production`, `"custom": 0`) and the empty controllers. Then run `bench --site mutara.local migrate`.
- [ ] **Step 4:** Run the test and expect PASS.
- [ ] **Step 5:** Commit: `Add Production module doctypes, roles and settings`.

### Task 2: Envelope + logic helpers (pure, unit-tested)

**Files:**
- Create: `upande_production/production/logic/__init__.py`, `weeks.py`, `deviation.py`, `pay.py`
- Create: `upande_production/api/envelope.py`
- Test: `upande_production/production/tests/test_logic_pure.py`

**Interfaces — Produces:**
- `weeks.iso_week_bounds(year: int, week: int) -> tuple[date, date]` (Monday, Sunday)
- `weeks.iso_of(d: date | str) -> tuple[int, int]` returns (iso_year, iso_week)
- `deviation.task_deviation(status: str, due_date, completed_at, planned_qty: float, done_qty: float, tolerance_days: int) -> str` returns `""`, `"Late"`, `"Partial"` or `"Skipped"`. Order: Skipped status → "Skipped". Partly Done, or Done with `planned_qty > 0 and done_qty < planned_qty` → "Partial". Done/Partly Done with `completed_at.date() > due_date + tolerance_days` → "Late" (Partial wins over Late). Open or In Progress → "".
- `pay.pay_value(qty: float, rate: float) -> float` returns `round(qty*rate, 2)`, with None treated as 0
- `envelope.run(fn) -> decorator`: wraps a whitelisted function. `frappe.PermissionError` → `{"error": str}` with no rollback. Any other Exception → rollback, `frappe.log_error`, `{"error": str(e)}`. `frappe.ValidationError` → `{"error": message}` with no log.
- `envelope.as_dict(v) -> dict | list`: json.loads when given a str

- [ ] **Step 1:** Write the tests:
  - `test_iso_week_bounds_53`: `iso_week_bounds(2026,53) == (date(2026,12,28), date(2027,1,3))` and `iso_week_bounds(2027,1)[0] == date(2027,1,4)`.
  - `test_iso_of`: `iso_of("2027-01-02") == (2026,53)`.
  - `test_deviation_cases`:
    - `("Skipped", …) -> "Skipped"`
    - `("Done", due 2026-10-20, completed 2026-10-22 08:00, 10, 10, 1) -> "Late"`
    - `("Done", due 2026-10-20, completed 2026-10-21, 10, 10, 1) -> ""`
    - `("Done", …, 10, 6, 1) -> "Partial"`
    - `("Open", …) -> ""`
  - `test_pay_value`: `pay_value(12.5, 40) == 500.0` and `pay_value(None, 40) == 0`.
- [ ] **Step 2:** Run and expect FAIL. **Step 3:** Implement. **Step 4:** Expect PASS. **Step 5:** Commit: `Add week, deviation, pay helpers and endpoint envelope`.

### Task 3: Domain logic and controllers

**Files:**
- Create: `upande_production/production/logic/units.py`, `plans.py`, `work.py`
- Modify: the controllers of Production Unit, Production Crop Cycle, Production Plan, Value Adder Work, Production Harvest, Yield Sample, Production Forecast, Buyer Commitment
- Test: `upande_production/production/tests/test_logic_domain.py` (IntegrationTestCase; it creates its own crop `Test Crop` / key `test-crop`, farm, units, employees, operation and Item, and rolls back)

**Interfaces — Consumes:** Task 2 helpers. **Produces:**
- `units.ensure_unit_cost_center(unit) -> str`: unit is a doc or name. Creates the Cost Center when it's missing. Its parent is chosen in this order:
  1. the parent unit's CC (made a group if needed);
  2. a crop group CC named `"{crop_name} - {abbr}"` under `Production Settings.cost_center_parent`;
  3. the company root.
  Group units get `is_group=1`. It sets `unit.cost_center` via `db_set` and returns the name. Called from the Production Unit `after_insert` hook and from `on_update` when cost_center is blank.
- `units.subtree(unit_name: str) -> list[str]`: the unit plus its descendants (lft/rgt).
- `plans.get_or_create_plan(crop: str, farm: str | None, year: int, week: int) -> Document`: unique on (crop, farm, plan_year, plan_week). The Plan's `validate` sets week_start/week_end, sets company from Settings, and recomputes each task's `deviation` using the `late_tolerance_days` setting and the task's `done_qty`. It throws on a duplicate (crop, farm, year, week).
- `plans.generate_week(plan_name: str) -> int`. Algorithm: for each cycle with status in (Active, Harvesting), a matching crop, a unit whose farm matches (or plan.farm empty), and a protocol, take each step and each k in `range(repeat_count or 1)`. The due date is `start_date + day_offset + k*(repeat_every_days or 0)`. If the due date falls inside the plan week and no task has `protocol_ref == f"{cycle}:{step.name}:{k}"`, append a task with operation, planned_qty, uom = the operation's work_uom, rate = the operation's default_rate, status Open and that protocol_ref. Return the count appended.
- `work.record_task_work(plan: str, task: str, status: str, entries: list[dict], note: str = "", work_date: str | None = None) -> dict`:
  - Each entry is `{employee, qty, hours?}`. Each one inserts and **submits** a Value Adder Work, copying unit/crop/cycle/operation/uom/rate from the task. `work_date` defaults to today.
  - Then it sets the task's `done_qty` to the sum of submitted VAW `qty` for (plan, plan_task) and sets the status.
  - `started_at` is set the first time status becomes In Progress, Done or Partly Done. `completed_at` = now for Done, Partly Done or Skipped, and None for Open.
  - It saves the plan and returns `{"task": <row dict>, "work": [names]}`.
  - An invalid status throws `ValidationError`, as does an entry whose qty is ≤ 0.
- `work.record_unplanned_work(unit, operation, entries, work_date, note="") -> list[str]`: VAWs with `unplanned=1` and no plan.
- Controllers:
  - **Value Adder Work validate:** rate defaults to the operation's default_rate. Sets pay_value, crop from unit, cost_center from unit (calling ensure), company from Settings, and `unplanned = not plan_task`.
  - **Production Harvest validate:** price defaults to the latest Buyer Commitment price for crop+item, else 0. `value = qty*price`.
  - **Yield Sample validate:** `unit_population` defaults to unit.plant_count, or area_ha*10000 for Square Metres. `est_unit_yield = sampled_yield / sample_size * unit_population`, guarded for 0.
  - **Production Forecast validate:** fills iso_year/iso_week per row and `total_expected`.
  - **Buyer Commitment validate:** sets iso fields.
  - **Crop Cycle validate:** sets the title and crop from unit.

- [ ] **Step 1:** Write the tests:
  - `test_unit_cost_center_tree`: pivot (group) + 2 blocks. Each block CC's parent equals the pivot's CC, and the pivot CC is a group.
  - `test_generate_week_idempotent`: protocol step day_offset 3, repeat every 7, ×4. A cycle starting the Monday of week W−1 has a step due Thursday of W−1 and one due Thursday of W. The first `generate_week` returns 1, the second returns 0.
  - `test_record_twice_sums_not_duplicates`: record 6 then 4 on a task with planned 10. done_qty is 10, there are 2 VAWs, and their pay_value equals qty×rate.
  - `test_status_only_creates_no_work`: `record_task_work(..., "In Progress", [])` creates 0 VAWs and sets started_at.
  - `test_late_flag_on_plan_save`: a task with due date 3 days ago marked Done today with tolerance 1 has deviation "Late".
  - `test_sample_estimate`: 10 trees sampled, 50 kg, population 400 → est 2000.
- [ ] **Step 2:** Run and expect FAIL. **Step 3:** Implement. **Step 4:** Expect PASS. **Step 5:** Commit: `Production domain logic: unit cost centres, week plans, value adder work`.

### Task 4: Desk API for the frontend

**Files:**
- Create: `upande_production/api/production.py`, `upande_production/production/logic/analytics.py`
- Test: `upande_production/production/tests/test_api.py`

**Interfaces — Consumes:** Tasks 2–3. **Produces:** every function is `@frappe.whitelist(methods=["POST"])` wrapped by `run`. Path: `upande_production.api.production.<name>`. Args are JSON. Pay rule: `can_see_pay = roles ∩ {Production Manager, Production Supervisor, System Manager, Administrator}`. When it's false, every `rate`/`pay_value`/`labour` money field is `None`.
- `get_bootstrap() -> {crops:[{name, crop_key, accent_color, icon_key, unit_label, parent_unit_label, sub_unit_label, yield_uom}], farms:[name], can_see_pay, can_plan, can_manage}`, with crops sorted by sort_order.
- `get_overview(crop) -> {tiles:{active_cycles, tasks_total, tasks_done, done_pct, deviations, labour_cost_mtd, forecast_next4, committed_next4, harvest_qty_season}, blocks:[{unit, unit_type, parent, area_ha, cycle, item, tasks_open, labour_cost_season, harvest_qty_season}]}` (the "season" is the current calendar year; the current week comes from today).
- `list_units(crop) -> {units:[{name, unit_type, parent, is_group, area_ha, plant_count, cost_center, status, current_cycle, item, has_geojson}]}`
- `get_unit(name) -> {unit:{…, geojson}, cycles:[…], recent_work:[…≤20]}`
- `list_cycles(crop, unit=None, status=None) -> {cycles:[{name, title, unit, item, cycle_type, start_date, expected_harvest_start, expected_harvest_end, protocol, status, area_ha, previous_cycle}]}`
- `save_cycle(data) -> {name}` (inserts, or updates when `data.name` is set)
- `get_plan(crop, farm, year, week) -> {plan: name|None, week_start, week_end, tasks:[{name, unit, cycle, operation, operation_name, planned_qty, done_qty, uom, rate, due_date, supervisor, supervisor_name, status, deviation, protocol_ref, note, work:[{name, employee, employee_name, qty, hours, pay_value}]}]}`
- `save_plan_tasks(crop, farm, year, week, tasks) -> {name}`: upserts rows by `name`. Rows without a name are appended. Nothing is deleted except rows passed with `"_delete": 1`.
- `generate_plan_week(crop, farm, year, week) -> {name, created}`
- `record_task_work(plan, task, status, entries, note="", work_date=None) -> {task, work}`
- `list_value_adders() -> {people:[{name, employee_name, image}]}` (Employees with designation "Value Adder" and status Active)
- `value_adder_summary(crop, from_date, to_date, group_by) -> {rows:[{key, label, qty, hours, pay_value, entries}], total_pay}`, where group_by is employee, day or unit (submitted VAWs only)
- `block_costs(crop, from_date, to_date) -> {rows:[{unit, unit_type, parent, is_group, area_ha, labour, inputs, total_cost, cost_per_ha, harvest_qty, revenue, margin}]}`:
  - labour is the sum of VAW pay_value over the unit's subtree;
  - inputs is the sum of GL Entry `debit - credit` where cost_center is in the subtree's CCs, `is_cancelled=0`, and the account root_type is Expense;
  - revenue is the sum of Production Harvest value over the subtree;
  - groups roll up their children.
- `deviations(crop, from_date, to_date) -> {rows:[{kind, unit, operation_name, due_date, plan, detail}]}`. kind is one of Late, Partial, Skipped, Unplanned or Missed. "Missed" means a protocol occurrence for an active cycle that was due in [from, min(to, yesterday)] with no task carrying its protocol_ref.
- `forecast_summary(crop, from_date, to_date) -> {uom, weeks:[{iso_year, iso_week, week_start, forecast, actual, committed, error_pct}], units:[{unit, forecast, actual, error_pct}], seasons:[{year, actual}]}`. `error_pct = (actual-forecast)/forecast*100` when forecast > 0, else None.
- `list_samples(crop, unit=None)`, `save_sample(data)`, `save_harvest(data)`, `list_harvests(crop, from_date, to_date)`, `list_commitments(crop)`, `save_commitment(data)`, `list_operations(crop)`, `save_operation(data)`, `list_protocols(crop)` — each returns `{rows:[…]}` or `{name}`.

- [ ] **Step 1:** Write the tests:
  - `test_endpoints_empty_crop`: a crop with nothing gives an empty `blocks`/`units`/`cycles`/`rows` list from each read endpoint, and `get_plan` returns `plan None, tasks []`.
  - `test_block_costs_rollup_and_zero`: a pivot with 2 blocks, VAW pay 100 on one block, a JE of 50 on the other block's CC. The pivot row has labour 100 and inputs 50, and the 1st block has inputs 0.
  - `test_viewer_gets_no_pay`: as a user with only Production Viewer, `get_plan` work entries have pay_value None, and `value_adder_summary` total_pay is None.
  - `test_missed_protocol_deviation`: a protocol occurrence due 3 days ago with no task appears as kind "Missed".
  - `test_forecast_error_pct`: forecast 100 and harvest 80 in one week gives error_pct -20.0.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit: `Desk API for the production frontend`.

### Task 5: Mobile API

**Files:** Create `upande_production/mobile/__init__.py`, `upande_production/mobile/api.py`. Test: `upande_production/production/tests/test_mobile_api.py`

**Interfaces — Consumes:** Task 3 logic and Task 4 read helpers (call the Python functions directly). **Produces:** mona style: `data = frappe.request.get_json() or {}`, and the result goes in `frappe.response['data']` (`{"error": …}` on failure). All are `@frappe.whitelist()`:
- `productionListCrops()`
- `productionListUnits({crop})`
- `productionGetWeekPlan({crop, farm, year?, week?})` (defaults to the current ISO week)
- `productionUpdateTask({plan, task, status, entries:[{employee, qty, hours}], note})`
- `productionRecordUnplannedWork({unit, operation, entries, work_date, note})`
- `productionRecordHarvest({unit, cycle?, item?, qty, uom?, grade?, harvest_date?})`
- `productionRecordSample({unit, cycle?, sample_basis, sample_size, sampled_yield, growth_stage?, sample_date?})`
- `productionListValueAdders()`
- `productionListOperations({crop})`

- [ ] **Step 1:** Test `test_update_task_via_mobile`: monkeypatch `frappe.request` with an object whose `get_json()` returns the payload. Call `productionUpdateTask`, then assert `frappe.response['data']['task']['status'] == "Done"` and that one VAW exists. Test `test_bad_status_returns_error`: `'error' in frappe.response['data']`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** Commit: `Mobile API for field capture`.

### Task 6: Demo seed

**Files:** Create `upande_production/production/demo/__init__.py`, `upande_production/production/demo/seed.py`, `upande_production/production/demo/config.py`

**Interfaces — Consumes:** Tasks 1–3. **Produces:** `seed.run(reset: bool = False) -> dict` (counts per doctype). It is idempotent: it creates rows only when they're missing, using natural keys. Run it with `bench --site mutara.local execute upande_production.production.demo.seed.run`.

`config.py` holds ONE dict, `DEMO`, with every invented figure:
- **Farm:** `Mutara` (core Farm, company Mutara).
- **Crops:**

  | Crop | crop_key | accent | icon_key | parent_unit_label / unit_label / sub_unit_label | yield_uom | sort_order |
  |---|---|---|---|---|---|---|
  | Avocado | avocado | #3f7d3a | avocado | — / Block / Row | Kg | 1 |
  | Fruits & Vegetables | fruits-vegetables | #c0662b | vegetables | Pivot / Block / Bed | Kg | 2 |
  | Aquaculture | aquaculture | #2b6f9e | fish | — / Pond / — | Kg | 3 |
  | Apiary | apiary | #c99a1b | hive | — / Hive Group / Hive | Kg | 4 |

- **Avocado units:** `Avocado Block A` (6.5 ha, 1,040 trees, Hass, `avocado_block_code` "A") and `Avocado Block B` (5.2 ha, 832 trees, Fuerte+Hass, code "B"). Also create matching `Avocado Yield Block` records (block_code A/B, farm "Mutara").
- **F&V:** pivots `Pivot 1`–`Pivot 4` of 24, 22, 21 and 20 ha (87 ha total), each split into 4 equal slice blocks named `P1-B1`…`P4-B4`. Crops by pivot:
  - P1: potatoes (Shangi) and cabbages (Gloria F1)
  - P2: onions (Red Bombay) and potatoes
  - P3: cabbages and onions
  - P4: passion fruit (Purple), as perennial Season cycles
  
  Every annual block has one Closed previous cycle (for rotation) and one Active cycle.
- **Aquaculture:** `Pond 1`–`Pond 4` (0.1 ha each). **Apiary:** `Hive Group North` and `Hive Group South` (400 hives each, as plant_count).
- **Items:** stock Items in item group "Products" (create the group if it's missing) for Hass Avocado, Fuerte Avocado, Potatoes, Cabbage, Onion, Passion Fruit, Tilapia and Honey (UOM Kg).
- **Operations + rates (KES)** per crop:
  - **Avocado:** Pruning (trees, 25), Fertiliser Application (trees, 10), Irrigation Check (ha, 150), Weeding (ha, 1,200), Fruit Count (trees, 5), Harvest Picking (crates, 30, is_harvest).
  - **F&V:** Land Preparation (ha, 2,500), Planting (beds, 60), Weeding (beds, 40), Top Dressing (beds, 35), Spraying (ha, 600), Harvest (crates, 25, is_harvest), Passion Pruning (plants, 8).
  - **Aquaculture:** Stocking (fingerlings ×1000, 300), Feeding (kg, 5), Water Quality Check (ponds, 100), Harvest (kg, 10, is_harvest).
  - **Apiary:** Hive Inspection (hives, 20), Treatment (hives, 30), Honey Harvest (kg, 40, is_harvest).
- **Protocols:**
  - Avocado season: Pruning d0; Fertiliser d14 ×4 every 30; Irrigation Check d0 ×26 every 7; Fruit Count d60.
  - Potato: Land Prep d−7, Planting d0, Weeding d21 ×2 every 21, Top Dressing d30, Spraying d14 ×6 every 10, Harvest d100.
  - Cabbage: Planting d0, Weeding d20, Top Dressing d28, Spraying d10 ×5 every 12, Harvest d85.
  - Onion: Planting d0, Weeding d25 ×3 every 20, Spraying d15 ×6 every 14, Harvest d120.
  - Passion: Passion Pruning d0 ×4 every 90, Spraying d0 ×12 every 30, Harvest d0 ×26 every 14.
  - Pond cycle: Stocking d0, Feeding d0 ×26 every 7, Water Quality Check d0 ×26 every 7, Harvest d180.
  - Hive season: Hive Inspection d0 ×12 every 14, Treatment d30, Honey Harvest d90.
- **Value adders:** 24 Employees (Kenyan names, company Mutara, employment_type Casual (create it if missing), designation "Value Adder" (create it), status Active). Also 3 supervisors with designation "Production Supervisor".
- **Users:** add Production Manager to Administrator and to every existing `@upande.com` user on the site.
- **Plans:** for the 4 ISO weeks ending the current week, for every crop, call `generate_week`. Past-week tasks:
  - ~80% Done (1–3 value adders each, qty around planned_qty);
  - ~8% Done but completed 2–3 days after due (Late);
  - ~6% Partly Done;
  - ~6% Skipped.
  
  Current-week tasks are a mix of Open, In Progress and Done. Use `random.Random(2026)` for determinism.
- **Harvests:** use the cycles' harvest windows within the last 6 weeks, plus avocado harvest picking in the last 3 weeks, with prices: avocado 120/kg, potato 45, cabbage 30, onion 70, passion 110, tilapia 400, honey 900.
- **Yield samples:** 3 per active F&V block and 2 per avocado block.
- **Forecasts:** 12 weeks (past 6 and next 6) per harvesting unit, so that actual vs forecast differs by ±5–25%.
- **Buyer commitments:** 2 customers (create "Twiga Foods" and "Kakuzi Export"), 6 future weeks for potatoes/avocado/passion.
- **Input costs:** one Journal Entry per F&V block and avocado block with 2–3 lines. Debit an Expense account from Mutara's chart (`Cost of Goods Sold - MUT` or the first non-group Expense account), set the line cost_center to the block CC, credit `Cash - MUT`, and submit. Amounts are KES 15,000–90,000 per block.
- **Avocado:** 2 Avocado Fruit Count rows per block and 1 Avocado Production Forecast per block for the current season (expected_kg ~ trees × 60, price_per_kg 120).

- [ ] **Step 1:** Run the seed twice and check that the second run's counts show 0 created. Then assert by hand in `bench --site mutara.local console`:
  - `frappe.db.count("Production Unit") == 2+4+16+4+2` (28; pivots are groups);
  - a Production Plan exists for each crop for the current week;
  - `api.production.block_costs("Fruits & Vegetables", …)` has non-zero labour and inputs for `Pivot 1`.
- [ ] **Step 2:** Commit: `Demo seed for Mutara`.

### Task 7: Frontend shell + www page

**Files:**
- Create `frontend/` by copying `/mnt/data/code/frappe16-mutara/apps/upande_livestock/frontend`, **without** `node_modules`, `src/pages/*`, `src/components/{feeding,stock,health,events,culling,disposal,animals,herds,settings}` or the livestock-specific `src/lib/*` (keep `frappe.ts`, `utils.ts`, `splash.ts`, `router.ts` (rewritten), `use-save-shortcut.ts`, `components/ui/*`, `Toast.tsx`, `Loading.tsx`, `PageShell.tsx`, `ScrollTable.tsx`, `Figure.tsx`, `DatePicker.tsx`, `RefreshButton.tsx`, `SidebarUser.tsx`, `AppSidebar.tsx` (rewritten), `index.css`, `main.tsx`, `test-setup.ts`).
- Create `upande_production/www/production_app.py` + `production_app.html` (port of `livestock_app.*`: global `window.PRODUCTION`, root id `production-root`, title "Upande Production").
- Modify `frontend/vite.config.ts`: base `/assets/upande_production/dist/`, outDir `../upande_production/public/dist`, file names `production-[hash]`, port 5175.
- Modify `frontend/package.json`: name `upande-production-frontend`.
- Modify `upande_production/hooks.py`: add the `add_to_apps_screen` entry (name upande_production, title "Production", route `/production_app`) and `website_route_rules` only if one is needed.
- Create `frontend/src/lib/api.ts`: typed wrappers for every Task 4 endpoint, using `call()` from `frappe.ts` with the method prefix `upande_production.api.production.`.
- Create `frontend/src/lib/crops.ts`: a `useCrops()` hook that loads `get_bootstrap` once (module cache) and a `CropContext`.
- Create `frontend/src/components/FilterSelect.tsx` (pill dropdown on Radix popover; the API is `{value, options:{value,label}[], onChange, placeholder}`) and `components/WeekPicker.tsx` (pill: ‹ W44 2026 ›).
- Router `#/<crop_key>/<view>`. The views are `overview`, `blocks`, `cycles`, `plan`, `value-adders`, `costs`, `forecast` and `settings`. The default is the first crop's `overview`.
- The sidebar shows a crop switcher at the top (crop icon in accent colour plus the name) and the view links below. Under Forecast, the avocado crop also shows external links to `/avocado-production`, `/avocado-outlook`, `/avocado-calendar` and `/avocado-maturity`.
- Every page is a stub `<PageShell title=…>` placeholder in this task.

- [ ] **Step 1:** `cd frontend && npm install && npm test` (keep any shell tests that still apply, delete livestock-specific ones) → PASS. Add `src/lib/__tests__/router.test.ts`: `parseRoute("#/fruits-vegetables/plan")` returns `{crop:"fruits-vegetables", view:"plan"}`, and `parseRoute("")` returns `{crop:null, view:"overview"}`.
- [ ] **Step 2:** `npm run build`, then from the bench run `bench build --app upande_production` (or simply rely on public/dist), then `curl -sk -o /dev/null -w '%{http_code}' https://mutara.132.145.18.63.nip.io/production_app` gives 200 (or 302 to login when unauthenticated, which is acceptable).
- [ ] **Step 3:** Commit: `React shell for /production_app`.

### Task 8: Frontend pages (three parallel slices after Task 7)

All slices consume `lib/api.ts` and the shell components. Each page shows skeletons while loading, an empty state, error toasts that carry the server's `error` text unchanged, and uses no native selects or date inputs in filter rows.

**8a — Overview, Blocks, Cycles** (`src/pages/Overview.tsx`, `Blocks.tsx`, `Cycles.tsx`)
- Overview: a tile row with active cycles, week done %, deviations, labour MTD (hidden when `!can_see_pay`), harvest this season, and forecast vs committed for the next 4 weeks. Below it, a block table.
- Blocks: a tree table (parent unit → blocks) with area, current cycle/item, status and cost centre. Clicking a row opens a drawer (`get_unit`) with its cycles and recent work.
- Cycles: a list with a status FilterSelect, a unit FilterSelect and a "New cycle" dialog (unit, item, type, start, harvest window, protocol). The rotation history per unit shows in the Blocks drawer.

**8b — Weekly Plan, Value Adders** (`src/pages/Plan.tsx`, `ValueAdders.tsx`, `components/plan/*`)
- Plan:
  - The header has a WeekPicker and a Farm FilterSelect, plus "Generate from protocols" (`generate_plan_week`) and "Add task" buttons, all gated by `can_plan`.
  - Tasks are grouped by unit. Each task row shows operation, planned → done qty + uom, due date, a status pill and a deviation badge (Late = amber, Partial = blue, Skipped = grey).
  - Clicking a row opens a **Tick-off dialog**: a status segmented control (Open/In Progress/Done/Partly Done/Skipped), a list of value adders already recorded, and an "Add value adder" row (a searchable picker over `list_value_adders`, qty, hours). It shows a live pay preview (qty × rate) when `can_see_pay`, plus a note. Save calls `record_task_work`.
- Value Adders: a group-by FilterSelect (Person/Day/Block), a date-range pill, a table of qty, hours, pay and entries with a total, and a CSV export button (client-side).

**8c — Block Costs, Forecast, Settings** (`src/pages/Costs.tsx`, `Forecast.tsx`, `Settings.tsx`)
- Costs: a date-range pill and a table with group rows (pivots) expandable to blocks. Columns: area, labour, inputs, total, cost/ha, harvest qty, revenue, margin (red when negative). A horizontal bar chart of margin per block (plain SVG, no strip accents).
- Forecast:
  - a weekly forecast vs actual vs committed chart (SVG lines and bars, with a "today" marker) and a per-unit accuracy table (error % coloured);
  - a seasons trend (one bar per year);
  - tabs for **Samples** (list plus a "New sample" dialog) and **Commitments** (list plus a "New commitment" dialog);
  - for avocado, the links to teddy's pages.
- Settings: tabs for **Operations & rates** (an inline-editable table calling `save_operation`) and **Protocols** (read-only list with steps). Managers only; others see a read-only view.

For each slice:
- [ ] **Step 1:** Add one vitest per page that renders with mocked `api` responses (an empty and a populated case) and asserts a key figure or the empty-state text.
- [ ] **Step 2:** `npm test` PASS, then `npm run build` PASS.
- [ ] **Step 3:** Commit: `Production pages: <slice>`.

### Task 9: Livestock production to-do (docs only)

**Files:** in `/mnt/data/code/frappe16-mutara/apps/upande_livestock` on branch `mutara-beef`, create `docs/todo/production.md`. It lists the "Production Forecasting: Livestock" scope verbatim from the spec intro (weight gain & output forecasting, buyer-commitment planning, herd productivity trend, forecast accuracy plan vs actual) for the other session. Commit: `Add livestock production to-do`. Do not push.

### Task 10: Integrate, seed, verify, review

- [ ] Merge the slices. Run `bench --site mutara.local migrate`, the seed, `npm run build`, `bench build --app upande_production` and `bench --site mutara.local clear-cache`. Restart the bench web and workers via `sudo supervisorctl restart frappe16-mutara-web: frappe16-mutara-workers:` (bench processes only).
- [ ] Run the full app test suite: `bench --site mutara.local run-tests --app upande_production`. All production tests must pass. Report the pre-existing avocado tests separately.
- [ ] Browser check (Playwright) as Administrator at `https://mutara.132.145.18.63.nip.io/production_app`. For each crop, visit every view: no console errors, no 500s, and the figures are non-empty for avocado and F&V. Tick off one task end to end and confirm that done qty and value adder pay update.
- [ ] Opus whole-branch review, then fix the findings.
- [ ] Check `git log main..mutara --format=%B | grep -ci co-authored-by` gives 0, and check author identities.
