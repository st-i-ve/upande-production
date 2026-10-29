# Establishment costs, week-based protocols, flowering cycles and break-even — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capital/setup costs and opening balances per block, protocols built from the variety template with key (week) and cultural (interval / as needed, establishment period, PHI) activities, flowering-based cycle chains with manager flags, generic dry matter tests, activity colours on the map, and break-even per block and per crop per farm.

**Architecture:** Schema first (Task 1). One scheduling module `production/logic/schedule.py` replaces every reader of the old `steps` table (plans, protocol check, deviations, protocol rule check, protocols API) so the rest of the code asks "what is due for this cycle between two dates". Buffers become implicit rules inside the existing rule engine (`rules.check`), so desk and mobile breach handling is unchanged. Cycle dates stay on the variety stage timeline (`stages.py`). Break-even is a new pure-ish module over existing cost sources (`analytics._labour_by_unit`, `_inputs_by_cc`, Production Harvest).

**Tech Stack:** Frappe v16 / ERPNext (Python, MariaDB), React + Vite + Tailwind + recharts + maplibre (desk app in `frontend/`), vitest.

**Spec:** `docs/superpowers/specs/2026-10-28-establishment-protocol-schedule-breakeven-design.md`

## Global Constraints

- Site `mutara.local` only; never touch other sites or the shared MariaDB beyond it.
- Backend tests: `bench --site mutara.local run-tests --app upande_production` (from `/mnt/data/code/frappe16-mutara`). Desk: `cd frontend && npx vitest run <files>`, `npx tsc -b`, `npm run build`.
- Restart only Mutara web: `sudo -n supervisorctl restart frappe16-mutara-web:frappe16-mutara-frappe-web`. Never `restart all`.
- Commits: author st-i-ve, **no Co-Authored-By trailer**, one commit per task, never chain a commit after failing tests.
- Whitelisted desk APIs: `@frappe.whitelist(methods=["POST"])` + `@run` envelope, as in `api/production.py`. Pay figures go through `_pay(value, can_see_pay)`.
- UI copy in weeks except **PHI in days**. Column headers: "Establishment period (weeks)" hint "weeks after planting / last harvest"; "Pre-harvest interval, PHI (days)" hint "days before harvest". Key table description: "List key activities in the order of their week."
- Both buffers are **Warn** (reason required, flagged in Approvals) — never Block.
- Week N of a cycle = days `[(N-1)*7, N*7)` from the cycle start.
- Seed / demo data stays in one config dict per seed module (swappable later).
- Desk UI follows the SCP design already in the app (PageHeader, pill toolbar, KpiCard, skeletons, toasts, Poppins, crop accent colour).
- Avocado already has dry matter (`Avocado Maturity Test`, `api/avocado.py dry_matter/save_dry_matter`, page `DryMatter`); keep it. The new generic **Dry Matter Test** is for other crops with `dry_matter_testing` on.

## Review Focus

1. A protocol converted by the patch must plan the **same weeks** the old steps did (± the week rounding) — a manager must not see work vanish from the plan. Test: `test_patch_keeps_due_weeks`.
2. A cultural Interval activity with an establishment period longer than the cycle so far, or a cycle with no expected harvest, must not crash generation or the rule engine (no harvest → no PHI check). Test: `test_due_items_without_harvest_date`.
3. Establishment cost on a **group** unit whose leaf blocks have no `area_ha` must refuse with a clear message, not divide by zero. Test: `test_split_group_without_areas_refused`.
4. Break-even for a block with an opening balance must only count system costs/harvests **after** `as_of_date` (no double count). Test: `test_breakeven_opening_balance_no_double_count`.
5. Closing a cycle twice (or re-saving a Closed cycle) must not propose a second next cycle. Test: `test_close_proposes_once`.

---

### Task 1: Schema — new and changed doctypes

**Files:**
- Modify (JSON in `upande_production/production/doctype/<name>/<name>.json`): `field_activity`, `production_crop`, `production_variety`, `production_protocol`, `production_crop_cycle`, `production_settings`
- Create doctypes (module Production, folder per doctype with `.json`, `.py`, `__init__.py`):
  `production_protocol_capital_activity` (istable), `production_protocol_key_activity` (istable), `production_protocol_cultural_activity` (istable), `block_establishment_cost` (submittable), `block_establishment_cost_split` (istable), `block_opening_balance`, `dry_matter_test`, `dry_matter_sample` (istable), `production_capital_account` (istable, one field `account` Link Account)
- Test: `upande_production/production/tests/test_doctypes.py`

Fields exactly as the spec's Data model section, plus:
- Field Activity: `activity_type` Select `Capital\nPlanting\nKey activity\nCultural\nHarvesting\nUprooting` default `Cultural`, in list view; `color` Color.
- Production Crop: `dry_matter_testing` Check; `dry_matter_on` Select `Fruit\nTuber` (`depends_on: dry_matter_testing`); `dry_matter_target_pct` Float (`depends_on: dry_matter_testing`).
- Production Variety: `lifespan_years` Float; `harvest_pattern` Select `Once\nContinuous\nInterval` default `Once`; `harvest_interval_weeks` Int (`depends_on: eval:doc.harvest_pattern!='Once'`); `is_flowering` Check; `weeks_to_first_flowering`, `weeks_flowering_to_harvest` Int (`depends_on: is_flowering`); `weeks_to_reflower_after_harvest` Int (`depends_on: eval:doc.is_flowering && doc.harvest_pattern!='Once'`); `weeks_to_first_harvest` Int (`read_only_depends_on: is_flowering`); `harvest_window_weeks` Int; `plants_per_m2` Float; `dry_matter_target_pct` Float. Existing `plants_per_ha`, `days_to_first_harvest`, `harvest_window_days` become `read_only: 1`.
- Production Protocol: tables `capital_activities`, `key_activities` (with `description` "List key activities in the order of their week."), `cultural_activities`; existing `steps` gets `hidden: 1`. Read-only template fields fetched from variety: `lifespan_years`, `harvest_pattern`, `harvest_interval_weeks`, `is_flowering`, `weeks_to_first_flowering`, `weeks_flowering_to_harvest`, `weeks_to_reflower_after_harvest`, `plants_per_m2` (`fetch_from: variety.<field>`).
- Key activity row: `operation` (reqd), `week` Int (reqd), `repeats` Select `Every cycle\nFirst cycle only` default `Every cycle`, `planned_qty` Float, `description` Small Text.
- Cultural activity row: `operation` (reqd), `schedule` Select `Interval\nAs needed` (reqd), `interval_weeks` Int (label "Interval (weeks)"), `establishment_period_weeks` Int (label "Establishment period (weeks)", description "weeks after planting / last harvest"), `pre_harvest_interval_days` Int (label "Pre-harvest interval, PHI (days)", description "days before harvest"), `planned_qty` Float, `description` Small Text.
- Capital activity row: `operation` (reqd), `description`, `budget_per_ha` Currency.
- Production Crop Cycle: `cycle_no` Int default 1, `expected_flowering_date` Date (read-only), `actual_flowering_date`, `actual_harvest_start`, `actual_harvest_end` Date, `protocol_flags` Small Text (read-only), `flag_count` Int (read-only), `due_for_uprooting` Check (read-only), `proposed_next_cycle` Link Production Crop Cycle (read-only).
- Production Settings: `cycle_flag_tolerance_weeks` Int default 2; `capital_accounts` Table `Production Capital Account`.
- Block Establishment Cost: as spec + `split_method` Select `By area\nManual` default `By area`, `total_area_ha` Float read-only. Split row: `unit` (reqd), `area_ha` (read-only), `share_pct`, `amount` (read-only for By area).
- Block Opening Balance: autoname `field:unit`; fields per spec.
- Dry Matter Test: per spec; `samples` Table `Dry Matter Sample` (`sample_no` Int, `dry_matter_pct` Float).
- Permissions mirror Production Protocol (System Manager, Production Manager full; Production Supervisor read on costs, create on Dry Matter Test).

**Interfaces — Produces:** the doctype and field names above (every later task codes against them).

- [ ] **Step 1: Failing test** `test_new_schema_fields` in `test_doctypes.py`: asserts `frappe.get_meta(dt).has_field(f)` for every (doctype, field) above and that `frappe.db.exists("DocType", dt)` for the 9 new doctypes.
- [ ] **Step 2:** Run tests → FAIL.
- [ ] **Step 3:** Write the JSONs; `bench --site mutara.local migrate`.
- [ ] **Step 4:** Run tests → PASS, and the full suite still passes (the old `steps` table is untouched).
- [ ] **Step 5:** Commit "Schema: activity types and colours, variety template, three protocol tables, establishment costs, opening balances, dry matter tests".

### Task 2: Variety template derivation and protocol validation

**Files:**
- Modify: `production/doctype/production_variety/production_variety.py`, `production/doctype/production_protocol/production_protocol.py`
- Test: `production/tests/test_varieties.py`, `production/tests/test_protocols.py`

**Interfaces — Produces:** `production_variety.derive(doc) -> None` (pure on a dict-like doc), `production_protocol.validate_tables(doc) -> None`.

- [ ] **Step 1: Failing tests:**
  - `test_variety_derives_weeks_and_density`: plants_per_m2=0.0156, is_flowering=1, weeks_to_first_flowering=104, weeks_flowering_to_harvest=36, harvest_window_weeks=12 → `weeks_to_first_harvest==140`, `days_to_first_harvest==980`, `harvest_window_days==84`, `plants_per_ha==156`.
  - `test_variety_clears_hidden_fields`: harvest_pattern=Once with weeks_to_reflower_after_harvest=10 and harvest_interval_weeks=4 → both saved as 0/None; is_flowering=0 → flowering weeks cleared and `weeks_to_first_harvest` kept as typed.
  - `test_key_activities_out_of_week_order_refused`: rows week 7 then week 3 → `frappe.ValidationError` whose message names both rows ("Row 2 (week 3) comes after row 1 (week 7)").
  - `test_cultural_interval_rules`: Interval with no interval_weeks → error; As needed with interval_weeks=2 → error; As needed with none → ok.
  - `test_cycle_protocol_operations_types`: a Capital-type operation in key/cultural rows → error; a non-Capital in capital rows → error.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `derive` (called from `validate`): if flowering, `weeks_to_first_harvest = weeks_to_first_flowering + weeks_flowering_to_harvest`; `days_* = weeks*7`; `plants_per_ha = plants_per_m2*10000` when m2 set (else, if only ha set, `plants_per_m2 = ha/10000`). `validate_tables` in protocol `validate`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit.

### Task 3: Scheduling engine `schedule.py`

**Files:**
- Create: `upande_production/production/logic/schedule.py`
- Test: `production/tests/test_schedule.py` (pure tests use plain dicts; no DB)

**Interfaces — Produces:**
- `cycle_start(cycle_doc) -> date` — `start_date`.
- `week_start(start: date, week: int) -> date` — `start + (week-1)*7`.
- `due_items(cycle_doc, protocol_doc, frm: date, to: date, harvest_start: date|None, picks: list[date] = (), harvest_interval_weeks: int|None = None) -> list[dict]` — every planned occurrence in `[frm, to]`, sorted by date: `{"ref": str, "kind": "key"|"cultural", "operation": str, "due_date": date, "planned_qty": float|None, "note": str|None, "row": str}`.
  - Key row: due `week_start(start, week)`; skipped when `repeats == "First cycle only"` and `cycle_doc.cycle_no > 1`. ref `"{cycle}:{row.name}:k"`.
  - Cultural Interval: first due `week_start(start, establishment_period_weeks + 1)` (establishment 0/None → week 1), then every `interval_weeks*7` days; occurrence k ref `"{cycle}:{row.name}:{k}"`; an occurrence inside the PHI is **not produced** — inside means `0 <= (next_harvest - due).days < pre_harvest_interval_days` where `next_harvest = next_pick(due, harvest_start, picks, harvest_interval_weeks)`.
  - As needed: never produced. Capital rows: never produced.
- `next_pick(on: date, harvest_start, picks, harvest_interval_weeks) -> date|None` — the first expected pick ≥ `on`: `harvest_start` if `on <= harvest_start`; else after the last actual pick `p ≤ on`, `p + interval*7` stepping until ≥ on; `None` when no harvest start.
- `rows_for_check(protocol_doc, operation) -> list[row]` — cultural rows of that operation (used by Task 5).

- [ ] **Step 1: Failing tests** (`test_schedule.py`):
  - `test_key_week_7`: start 2026-01-05, key row week 7 → due 2026-02-16.
  - `test_first_cycle_only_skipped_in_cycle_2`.
  - `test_interval_after_establishment`: interval 2, establishment 3 → dues 2026-01-26, 2026-02-09, …
  - `test_phi_suppresses_last_spray`: harvest_start 2026-03-02, PHI 14 → no occurrence on/after 2026-02-16 and before 2026-03-02; the one on 2026-02-09 kept.
  - `test_continuous_phi_between_picks`: picks every 1 week from 2026-03-02 (interval 1), PHI 3 → a weekly spray due 2026-03-04 kept (next pick 03-09, 5 days), one due 03-07 dropped.
  - `test_as_needed_never_generated`, `test_due_items_without_harvest_date` (no harvest → no PHI filtering, no crash).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5:** Commit.

### Task 4: Convert old protocol steps (patch)

**Files:**
- Create: `upande_production/patches/convert_protocol_steps.py`; add to `patches.txt` `[post_model_sync]`; also `patches/backfill_activity_types.py` (sets `activity_type` from category/is_harvest: Harvesting→Harvesting, name contains "plant"→Planting, else Cultural; assigns distinct colours from `COLORS` list in the patch) and `patches/backfill_variety_weeks.py` (weeks = round(days/7), plants_per_m2 = ha/10000).
- Test: `production/tests/test_protocols.py`

**Interfaces — Consumes:** Task 3 `due_items`, `stages.step_due_date` (old). **Produces:** `convert_protocol_steps.convert(protocol_doc) -> dict` (`{"key": n, "cultural": n}`), idempotent (skips protocols that already have key or cultural rows).

Rules: `repeat_every_days` > 0 and `repeat_count` > 1 → Cultural Interval, `interval_weeks = max(1, round(every/7))`, `establishment_period_weeks = offset_days // 7` where offset_days = the step's day offset from cycle start (for `anchor_stage` steps: the variety's planned stage `start_day` + `day_offset`); otherwise → Key, `week = offset_days // 7 + 1`. Note → description. Key rows sorted by week. Operation "Planting" / "Gap filling" → `repeats = First cycle only`. Old `steps` left in place (hidden).

- [ ] **Step 1: Failing tests:** `test_patch_converts_steps` (a protocol with one repeating and one single step → 1 cultural + 1 key with the values above), `test_patch_idempotent`, `test_patch_keeps_due_weeks` (for every demo protocol and its first cycle, the set of ISO weeks from old `step_due_date` over the next 26 weeks ⊆ the ISO weeks from `due_items` ± 1 week).
- [ ] **Steps 2–4:** FAIL → implement → `bench migrate` → PASS. **Step 5:** Commit.

### Task 5: Rewire every consumer of `steps` to the three tables

**Files:**
- Modify: `production/logic/plans.py` (`generate_week_detail`), `production/logic/analytics.py` (deviations ~l.309–345, protocol check ~l.379–460), `production/logic/rules.py` (`rule_check` ~l.354), `production/logic/protocols.py` (`STEP_FIELDS` → `KEY_FIELDS`, `CULTURAL_FIELDS`, `CAPITAL_FIELDS`; `_row`, `new_version`, `submit_for_approval` (needs ≥1 key or cultural row), `diff` (per table, `"table"` key on each change), `save_draft` (accepts `key_activities`, `cultural_activities`, `capital_activities`)), `api/production.py list_protocols` (return the three tables), `mobile/api.py productionProtocolCheck` (shape unchanged; source via analytics).
- Test: existing `test_protocols.py`, `test_rules.py`, `test_api.py`, `test_mobile_api.py`, `test_coverage.py` updated to build protocols with the new tables.

**Interfaces — Consumes:** `schedule.due_items`, `schedule.next_pick`, `stages.harvest_start`. Picks for a cycle = distinct `harvest_date` of Production Harvest with that cycle. **Produces:** `protocol_ref` format `"{cycle}:{row.name}:{k}"` (unchanged shape), protocols API rows `{..., "key_activities": [...], "cultural_activities": [...], "capital_activities": [...]}`; diff entries `{"table": "key_activities"|"cultural_activities"|"capital_activities", "change", "operation", ...}`.

- [ ] **Step 1:** Update the existing tests to the new tables; add `test_generate_uses_key_and_cultural` (a week containing a key due and a cultural due → 2 tasks, refs as above) and `test_protocol_diff_per_table`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Full backend suite PASS. **Step 5:** Commit.

### Task 6: Buffers in the rule engine (both Warn)

**Files:**
- Modify: `production/logic/rules.py` (`check`, `_context` adds `protocol`, `cycle_start`, `cycle_no`, `picks`, `harvest_interval_weeks`)
- Modify: `mobile/SUPERVISOR_API.md` (buffer breach messages)
- Test: `production/tests/test_rules.py`

**Interfaces — Consumes:** `schedule.rows_for_check`, `schedule.next_pick`. **Produces:** breach dicts `{"rule": "protocol:<row name>", "rule_type": "Establishment period" | "Pre-harvest interval", "enforcement": "Warn", "message": str}` appended to `check()`'s result. Messages: `"Spraying is planned 9 days before harvest; the protocol's pre-harvest interval is 14 days."` and `"Spraying is in week 2; the protocol's establishment period is 3 weeks after planting."` (say "after the last harvest" when `cycle_no > 1`).

- [ ] **Step 1: Failing tests:** `test_phi_breach_warns`, `test_establishment_breach_warns`, `test_buffer_never_blocks` (worst() of those is "Warn"), `test_no_harvest_no_phi`, `test_record_work_inside_phi_needs_reason` (record_task_work without override_reason → RuleBreach Warn; with reason → saved, rule_status Warn).
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 7: Cycle dates, chain and manager flags

**Files:**
- Create: `production/logic/cycle_chain.py`
- Modify: `production/doctype/production_crop_cycle/production_crop_cycle.py` (validate/on_update hooks), `hooks.py` daily scheduler adds `upande_production.production.logic.cycle_chain.refresh_flags_all`
- Test: `production/tests/test_cycle_chain.py`

**Interfaces — Consumes:** `stages.timeline`, `stages.stage_start`, `stages.harvest_start`, `stages.variety_protocol`. **Produces:**
- `sync_actuals(cycle_doc) -> None`: writes `actual_flowering_date` as the stage actual of the variety stage named like "Flower%" and `actual_harvest_start` as the actual of the `is_harvest` stage (upsert in `stage_actuals`); sets `expected_flowering_date` = that stage's start from `stages.timeline`. For cycle_no > 1 of a flowering variety, the flowering stage planned start = start + `weeks_to_reflower_after_harvest`*7.
- `propose_next(cycle_doc) -> str|None`: when `status == "Closed"`, variety `harvest_pattern != "Once"`, `proposed_next_cycle` empty, lifespan not reached (`start of cycle 1 + lifespan_years*365 > next start`) → insert Planned cycle (`previous_cycle`, `cycle_no+1`, unit, crop, variety, protocol = `stages.variety_protocol(variety)`, `start_date = actual_harvest_end or today`), store it in `proposed_next_cycle`; lifespan reached → set `due_for_uprooting = 1`, return None.
- `flags(cycle_doc, today=None) -> list[str]`; `refresh_flags(cycle) -> int` (stores `protocol_flags` joined "\n", `flag_count`); `refresh_flags_all() -> int`. Tolerance `Production Settings.cycle_flag_tolerance_weeks` (default 2). Flags: actual vs expected flowering / harvest start beyond tolerance ("Block A flowered 3 weeks late"); expected date passed by more than tolerance with no actual ("Block C harvest due 2 weeks ago, nothing recorded"). Never raises.
- `api/production.py`: `cycle_flags(crop) -> {"rows": [{"cycle","unit","variety","flags":[...]}]}`; existing cycles API rows gain `cycle_no`, `expected_flowering_date`, `actual_flowering_date`, `actual_harvest_start`, `actual_harvest_end`, `flags`, `due_for_uprooting`, `proposed_next_cycle`.
- Patch `patches/number_cycles.py`: `cycle_no` along the `previous_cycle` chain (no chain → 1).

- [ ] **Step 1: Failing tests:** `test_flowering_actual_shifts_harvest`, `test_flag_late_flowering` (3 weeks late, tolerance 2 → one flag with "3 weeks late"), `test_flag_within_tolerance_none`, `test_flag_missing_actual`, `test_close_proposes_next_with_reflower` (Hass: next start = harvest end, expected flowering = start + reflower weeks), `test_close_proposes_once`, `test_once_variety_no_proposal`, `test_lifespan_marks_uprooting`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 8: Establishment costs and opening balances

**Files:**
- Create: `production/logic/establishment.py`, `api/establishment.py`
- Modify: `production/doctype/block_establishment_cost/block_establishment_cost.py` (validate → `establishment.split(doc)`)
- Test: `production/tests/test_establishment.py`

**Interfaces — Produces:**
- `establishment.leaf_units(unit) -> list[str]`; `split(doc) -> None` (expands group rows into leaf rows, By area → share_pct = area/total*100, amount = round(amount*share,2) with the rounding remainder on the largest row; Manual → shares must sum to 100 ±0.01; any By-area row without area → ValidationError "Block X has no area; enter its area or split manually").
- `establishment.cost_by_unit(units: list[str], to_date=None) -> dict[str, float]` (submitted docs only, includes Uprooting-type rows).
- API (`api/establishment.py`, crop-scoped): `list_costs(crop, farm=None) -> {"rows": [...], "by_unit": [{unit, total, by_activity: [{operation, amount, budget}]}]}`, `save_cost(data) -> {"name"}` (submits), `cancel_cost(name)`, `capital_activities(crop) -> {"rows": [{operation, color, budget_per_ha}]}` (from the crop's Active protocols' capital rows, else all Capital-type operations of the crop), `list_opening_balances(crop)`, `save_opening_balance(data)`. Requires Production Manager (or System Manager) for writes; pay rule not applied (cash spend, not pay).

- [ ] **Step 1: Failing tests:** `test_split_by_area`, `test_split_rounding_sums_to_amount`, `test_manual_split_must_total_100`, `test_split_group_without_areas_refused`, `test_cost_by_unit_counts_submitted_only`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 9: Break-even

**Files:**
- Create: `production/logic/breakeven.py`, `api/breakeven.py`
- Test: `production/tests/test_breakeven.py`

**Interfaces — Consumes:** `establishment.cost_by_unit`, `analytics._labour_by_unit`, `analytics._rollup`, `analytics.crop_units`, Production Harvest (`value`), GL Entry. **Produces:**
- `breakeven.series(cost_events, value_events) -> dict` (pure): events `[(date, amount)]` → `{"points": [{"date", "cost", "value"}] (cumulative, monthly), "invested", "recovered", "balance", "pct_recovered", "break_even_date": date|None}`. Break-even date = first month-end where cumulative value ≥ cumulative cost.
- `breakeven.project(balance, monthly_net) -> date|None` (pure): months = ceil(-balance / monthly_net) when balance < 0 and monthly_net > 0.
- `breakeven.block(unit, can_see_pay) -> dict` and `breakeven.crop(crop, farm, can_see_pay) -> {"blocks": [...], "farm": {...series..., "projected_date", "projection_basis": "forecast"|"trailing_12m"|None}}`.
  - Cost events: opening balance (`setup_cost + running_costs_to_date` at `as_of_date`), establishment costs (posting_date), approved labour pay per month, GL Expense on the block cost centre per month **excluding** `capital_accounts` and GL of Stock Entries with `stock_entry_type = "Harvesting"`; system events only after `as_of_date` when an opening balance exists, else from the first establishment cost.
  - Value events: opening `value_recovered_to_date`, Production Harvest `value` by `harvest_date`. Any Production Harvest with empty value is valued at qty × `harvest.unit_value(item)` (the function `harvest.py` uses for the receipt; expose it if private).
  - Projection: forecast (Production Forecast for the unit/crop, expected kg × unit value per month over the next 12 months, minus the trailing-12-month average monthly cost) when present, else trailing-12-month net.
  - `can_see_pay` false → API raises PermissionError "Break-even includes pay; ask a manager." (page hidden).
- API: `crop_breakeven(crop, farm=None)`.

- [ ] **Step 1: Failing tests:** `test_series_break_even_date`, `test_series_never_breaks_even`, `test_project_months`, `test_breakeven_opening_balance_no_double_count`, `test_harvesting_stock_entry_gl_excluded`, `test_capital_account_excluded`, `test_breakeven_hidden_without_pay`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 10: Generic dry matter tests and gap filling count

**Files:**
- Create: `api/drymatter.py`; Modify `production/doctype/dry_matter_test/dry_matter_test.py`, `mobile/api.py` (`productionDryMatterTests(crop, unit=None)` read endpoint, `{data: [...]}`), `mobile/SUPERVISOR_API.md`
- Modify: `api/production.py` blocks endpoint rows gain `dry_matter: {pct, target, ready, date}|None`, `plants_replaced: int` (sum of approved Value Adder Work qty for operations named "Gap filling" on the unit, uom Plant)
- Test: `production/tests/test_drymatter.py`

**Interfaces — Produces:** `dry_matter_test.validate`: `avg_pct` = mean of samples (2 dp), `target_pct` = variety override or crop default, `ready = avg >= target`, `tested_on` from crop; refuses when crop `dry_matter_testing` is off. API: `list_tests(crop, unit=None)`, `save_test(data) -> {"name","avg_pct","ready"}`, `latest_by_unit(crop) -> dict[unit, {...}]`.

- [ ] **Step 1: Failing tests:** `test_avg_and_ready`, `test_variety_target_overrides_crop`, `test_refused_when_crop_off`, `test_blocks_show_plants_replaced`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 11: Activity colours on the map and plan

**Files:**
- Modify: `api/coverage.py` (each unit gains `activity: {operation, color}|None` = the operation of the latest approved/pending Value Adder Work in the selected week, else the latest In Progress task, else the first Open task due; `legend: [{operation, color}]`), `api/production.py` operations list returns `activity_type`, `color`; plan task rows and approvals rows gain `color`.
- Test: `production/tests/test_coverage.py`

- [ ] **Step 1:** `test_coverage_activity_colour` (work + task on a unit → work's operation and its colour; legend lists it once). **Steps 2–4.** **Step 5:** Commit.

### Task 12: Demo seed

**Files:**
- Create: `production/demo/establishment_seed.py` (config dict `DEMO`); Modify `production/demo/varieties_seed.py` (template fields), `production/demo/seed.py` (activity types/colours, capital and field activity lists per crop), `production/demo/all.py` (run `establishment_seed` after `rules_seed`).

Content: activity lists from the spec's Decisions with types and distinct colours, plus `Planting material` (Capital); apiary capital (Hive stands, Hives, Apiary fencing) and aquaculture capital (Pond excavation, Pond liner, Inlet and outlet works, Aerator installation). Variety templates: Hass (flowering, Interval 52, first flowering 104 wks, flowering→harvest 36, reflower 12, plants_per_m2 0.0156, lifespan 30, DM target 22.5), Fuerte (same, DM 21), Passion Purple/Yellow (flowering, Continuous 1, first flowering 20, flowering→harvest 10, reflower 2, 0.1667, lifespan 3), potatoes/cabbage/onion (Once, non-flowering, weeks to first harvest 14/12/16, 4.0/3.7/40 per m²), tilapia (Once, 26). Potatoes `dry_matter_testing` Tuber target 20; Avocado Fruit 22.5. Protocols: key rows (e.g. Avocado bending wk 7 Every cycle; potatoes earthing-up wk 4, gap filling wk 2 First cycle only) and cultural rows with intervals and buffers (spraying Interval 2, establishment 2, PHI 21 avocado / 14 potatoes, cabbage, onion / 7 passion; weeding Interval 3; irrigating Interval 1; Mulching As needed; Pest management As needed). Establishment costs for every demo block (KES/ha: bush clearing 25 000, single ripping 18 000, cross ripping 15 000, disc harrowing 9 000, marking 4 000, ridge-line ripping 12 000, ridging 10 000, basal fertiliser 30 000, planting material avocado 120 000 / potatoes 90 000, windbreak 8 000), one shared "Irrigation system installation" 2 400 000 split by area across the F&V pivot blocks; opening balances for the mature avocado blocks (as_of 2026-01-01). Dry matter tests for potato slices (3 weeks, rising to target) — avocado keeps its existing maturity tests. Avocado Block A `actual_flowering_date` 3 weeks after expected → one flag.

- [ ] **Step 1:** `bench --site mutara.local execute upande_production.production.demo.all.run` (idempotent) — no errors.
- [ ] **Step 2:** Verify with `bench --site mutara.local console`-free checks via `bench execute`: `breakeven.crop("Avocado", None, True)` has blocks with invested > 0; `cycle_chain.refresh_flags_all()` ≥ 1; generation for the current week creates tasks.
- [ ] **Step 3:** Full backend suite PASS. **Step 4:** Commit.

### Task 13: Desk — Settings: Activities and Variety template

**Files:**
- Modify: `frontend/src/components/settings/OperationsTable.tsx` (columns Type, Colour with a colour input; tab label "Activities & rates"), `frontend/src/pages/Settings.tsx`, the Varieties editor component used under `value="varieties"` (find it from Settings.tsx), `frontend/src/lib/varieties-api.ts` (types for the new fields)
- Test: `frontend/src/pages/__tests__/Settings.test.tsx`

Show/hide rules exactly as Task 1 `depends_on`. Weeks to first harvest is read-only and computed (live, same formula) when flowering.

- [ ] **Step 1: Failing tests:** `shows flowering fields only when flowering`, `hides reflower and interval when harvested once`, `computes weeks to first harvest for flowering`, `activity colour saved`.
- [ ] **Steps 2–4** (`npx vitest run src/pages/__tests__/Settings.test.tsx`). **Step 5:** Commit.

### Task 14: Desk — Protocol editor with three tables

**Files:**
- Modify: `frontend/src/lib/protocols-api.ts` (replace `ProtocolStep` by `KeyActivity`, `CulturalActivity`, `CapitalActivity`; diff entries carry `table`), `frontend/src/components/settings/ProtocolsList.tsx`, `frontend/src/components/approvals/ProtocolDiff.tsx`, `frontend/src/components/plan/ProtocolCheckPanel.tsx`, `frontend/src/components/cycles/NewCycleDialog.tsx` (any `steps` reference), `frontend/src/pages/Plan.tsx`
- Test: `frontend/src/components/settings/__tests__/ProtocolsList.test.tsx` (create), `Approvals.test.tsx`

UI: three sections (Capital activities / Key activities / Cultural activities), each a table with "Add row". Key: Activity, Week, Repeats, Qty, Description; the section shows the description line "List key activities in the order of their week." and highlights an out-of-order row in red before save. Cultural: Activity, Schedule (Interval / As needed), Interval (weeks) — disabled and emptied when As needed —, Establishment period (weeks), Pre-harvest interval, PHI (days), Qty, Description. Capital: Activity (Capital-type only), Budget per ha, Description. The variety's template values show read-only above the tables.

- [ ] **Step 1: Failing tests:** `interval weeks disabled for as needed`, `out of order week highlighted`, `capital picker lists only capital activities`, `diff shows table name`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 15: Desk — Establishment costs and Break-even pages

**Files:**
- Create: `frontend/src/lib/establishment-api.ts`, `frontend/src/lib/breakeven-api.ts`, `frontend/src/pages/Establishment.tsx`, `frontend/src/pages/BreakEven.tsx`
- Modify: `frontend/src/lib/router.ts` (views `establishment`, `break-even`), `frontend/src/lib/nav.ts` (group "Finance" or next to Costs: "Setup costs", "Break-even"; all crops), `frontend/src/App.tsx`
- Test: `frontend/src/pages/__tests__/Establishment.test.tsx`, `BreakEven.test.tsx`

Establishment: KPI cards (Total invested, Per ha, Blocks set up, Budget vs actual), table by block × activity, "Add cost" dialog (date, activity, amount, supplier/paid to, reference, blocks multi-select incl. groups, split By area/Manual with live share preview), tab "Opening balances" (one row per block, editable). Break-even: farm summary KPIs (Invested, Recovered, Balance, % recovered, Break-even / Projected date with basis), cumulative cost vs value line chart (recharts, crossing marked), block table sortable by % recovered; page shows a "Break-even includes pay; ask a manager." empty state on the PermissionError.

- [ ] **Step 1: Failing tests:** `split preview by area`, `opening balance tab saves`, `break-even shows projected date and basis`, `break-even hidden message without pay`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 16: Desk — Cycles, Overview, Blocks, Map, Dry matter

**Files:**
- Modify: `frontend/src/components/cycles/CycleGantt.tsx` (expected vs actual flowering/harvest markers, cycle no, flag badge, "due for uprooting" pill), `frontend/src/pages/Cycles.tsx` (record actual flowering / harvest start / end dialog; shows "Next cycle proposed: …" toast from the save response), `frontend/src/pages/Overview.tsx` ("Off protocol" card listing `cycle_flags`), `frontend/src/pages/Blocks.tsx` (dry matter, plants replaced, flags), `frontend/src/pages/CoverageMap.tsx` ("Colour by activity" toggle + legend), `frontend/src/pages/fruits-vegetables/` new `DryMatterTests.tsx` page for crops with `dry_matter_testing` (nav entry via `ONLY_FOR` driven by the crop setting; avocado keeps `DryMatter`), Plan and Approvals rows get the activity colour dot.
- Test: `Cycles.test.tsx`, `Overview.test.tsx`, `Blocks.test.tsx`, `CoverageMap.test.tsx`, new `DryMatterTests.test.tsx`.

- [ ] **Step 1: Failing tests:** `gantt shows late flowering marker and flag`, `overview off protocol card`, `blocks show dry matter ready`, `map colours by activity with legend`, `dry matter test average and ready badge`.
- [ ] **Steps 2–4.** **Step 5:** Commit.

### Task 17: Integration, build, deploy, verify

- [ ] **Step 1:** `bench --site mutara.local migrate`; full backend suite PASS; `npx tsc -b`, `npx vitest run` all PASS; `npm run build`.
- [ ] **Step 2:** Restart Mutara web only; open each new/changed page in the browser (Playwright) at https://mutara.132.145.18.63.nip.io for avocado and F&V; no console errors except the known Frappe `/undefined`.
- [ ] **Step 3:** Mobile API smoke: week plan for Avocado includes cultural tasks; tick-off of a spray inside the PHI returns a Warn breach.
- [ ] **Step 4:** Opus whole-branch review; fix; commit.

---

## Addendum 2026-10-29 (spec section "Addendum 2026-10-29")

### Task 18: Variety maturity and flowering patterns (backend)

**Files:** `production/doctype/production_variety/*` (+ new istable `production_variety_flowering_season`), `production/logic/cycle_chain.py`, `production/logic/stages.py` (only if needed), `api/varieties.py` (allow-list), `production/logic/protocols.py` (TEMPLATE_FIELDS), new patch `patches/flowering_pattern_from_reflower.py`, forecast/break-even juvenile handling (`production/logic/breakeven.py` projection, forecast code that expects yield per cycle), `production/demo/varieties_seed.py`. Tests: `test_varieties.py`, `test_cycle_chain.py`, `test_breakeven.py`.

**Interfaces — Produces:**
- Variety fields: `weeks_to_maturity` Int; `flowering_pattern` Select `Seasonal\nInterval` (depends_on is_flowering); `flowering_seasons` Table **Production Variety Flowering Season** (`season_name` Data reqd, `start_month` Select `January`…`December` reqd, `weeks_flowering_to_harvest` Int reqd, `crop_share_pct` Float) shown when Seasonal; `flowering_interval_weeks` Int shown when Interval; `weeks_to_first_flowering` shown when Interval; `weeks_to_reflower_after_harvest` hidden. Validation: Seasonal needs ≥1 season, shares total 100 when any share is set; Interval needs interval weeks.
- Cycle field: `flowering_season` Data (read-only), `juvenile` Check (read-only).
- `cycle_chain.expected_flowering(cycle_doc, variety) -> date|None`; `cycle_chain.next_season(variety, after: date) -> (season_row, flowering_date)`; `cycle_chain.first_season_date(planted_on: date, variety) -> date` (first season start ≥ planted_on + maturity weeks). `propose_next` uses them: Seasonal → next season by calendar after this cycle's flowering; Interval → previous flowering + interval weeks; expected harvest start = flowering + that season's/variety's weeks flowering → harvest.
- Juvenile: `cycle_chain.is_juvenile(cycle_doc) -> bool` (expected harvest start < unit planted_on + maturity; planted_on from Block Opening Balance.planted_on or the first cycle's start_date). Break-even projection and forecast skip juvenile cycles' yield.
- Flags: seasonal varieties compare actual flowering with the season start; remove the flowering-anchored first-cycle exception for them.
- Patch: Interval varieties `flowering_interval_weeks` = `harvest_interval_weeks` or reflower + flowering→harvest; avocado demo varieties become Seasonal.
- Seeds: Hass seasons Main (August, 36 wks, 80 %), Off-season (February, 36 wks, 20 %); Fuerte Main (July, 32, 85 %), Off (January, 32, 15 %); maturity Hass/Fuerte 130 weeks; passion Interval: maturity 30, first flowering 20, interval 4, flowering→harvest 10. Re-run seeds idempotently; flags after seeding: only deliberate ones (keep Avocado Block A ~3 weeks late now that seasonal checks apply).

Tests: `test_seasonal_first_season_after_maturity`, `test_seasonal_next_season_by_calendar`, `test_interval_next_flowering`, `test_juvenile_cycle_no_projection_yield`, `test_seasonal_flowering_flag_late`, `test_shares_must_total_100`.

### Task 19: Block warehouse, links check, harvest store, ERP budget, block cost breakdown (backend)

**Files:** `production/doctype/production_unit/production_unit.json` (`warehouse` Link Warehouse), `production/doctype/harvest_batch/*` (warehouse chosen), `production/logic/harvest.py` (`close_batch(team, unit, harvest_date=None, warehouse=None)`, `default_store(farm) -> str`, `stores(company) -> list`), `mobile/harvest.py` (`mark_ready_for_collection(..., warehouse=None)`, new `get_stores(block=None)` → `{"data": [{"name","label"}], "default": str}`; document in `mobile/SUPERVISOR_API.md`), new `production/logic/blockcost.py` + `api/blockcost.py`, `api/production.py` (`block_links(crop)`), `api/establishment.py` (`list_costs` by_unit gains `erp_budget`), tests `test_harvest.py`, new `test_blockcost.py`.

**Interfaces — Produces:**
- `blockcost.links(crop) -> list[{unit, cost_center, warehouse, ok: bool, problems: [str]}]` (problems: "No cost centre", "No warehouse", "Warehouse 'X' and cost centre 'Y' differ — chemicals issued to this block are charged elsewhere"); API `api.production.block_links(crop)` → `{rows}`.
- `blockcost.erp_budget(cost_center, fiscal_year=None) -> float` (submitted Budget docs with `budget_against = "Cost Center"`; sum of Budget Account `budget_amount`).
- `blockcost.breakdown(unit, from_date, to_date, can_see_pay) -> {"unit","area_ha","labour": [{operation, qty_by_uom: [{uom, qty}], workers, pay}], "inputs": [{item_code, item_name, item_group, qty, uom, amount, per_ha, planned_qty}], "other": [{account, amount}], "totals": {labour, inputs, other, total, per_ha}, "budget": {erp_budget, actual_this_fy}}` — inputs from submitted Stock Entry Detail rows with `cost_center = unit.cost_center` and `s_warehouse` set (issues), excluding Harvesting entries; other = GL Expense on the cost centre not from those stock entries and not capital accounts; labour pay hidden via `_pay`. API `api.blockcost.block_breakdown(unit, from_date=None, to_date=None)`.
- Harvest store default: last Harvest Batch warehouse for the farm, else Production Settings `harvest_warehouse`. A block warehouse (one linked from a Production Unit) is refused as a harvest store.

Tests: `test_links_flags_name_mismatch`, `test_erp_budget_sums_cost_center`, `test_breakdown_inputs_from_issues`, `test_breakdown_excludes_harvesting_entries`, `test_close_batch_uses_chosen_store`, `test_default_store_last_used`, `test_block_warehouse_refused_as_store`. Seed: set each demo block's `warehouse` (create `<unit> - MUT` block warehouses under a "Production Blocks - MUT" group if missing, named exactly like the cost centre) and a demo fertiliser + chemical issue per avocado block (Material Issue from the farm store, cost centre = block), and one ERPNext Budget for Avocado Block A's cost centre (current fiscal year) — only if the company has a fiscal year and the needed accounts; otherwise skip with a printed note.

### Task 20: Desk — variety maturity and flowering patterns

**Files:** variety dialog (`frontend/src/components/settings/VarietyDialog.tsx`), `frontend/src/lib/varieties-api.ts`, `CycleGantt.tsx` (season name and "Juvenile" pill), tests in `src/pages/__tests__/Settings.test.tsx`/varieties tests, `Cycles.test.tsx`.
Show/hide exactly as Task 18; seasons table editor (add row, month select, weeks, share %, total shown, warns when ≠ 100). Tests: `seasonal shows seasons table and hides interval`, `interval shows interval weeks`, `season shares total warning`, `gantt shows season and juvenile`.

### Task 21: Desk — block links, store, ERP budget, block cost breakdown

**Files:** `frontend/src/pages/Costs.tsx` (Block Costs: click a block → breakdown drawer/page with Labour by activity, Inputs by item (qty, UOM, amount, per ha, planned), Other by account, totals, budget vs actual), new `frontend/src/lib/blockcost-api.ts`, `frontend/src/pages/Settings.tsx` (new tab "Block links" listing `block_links` with problems), `frontend/src/pages/Blocks.tsx` (warning icon on blocks with link problems), `frontend/src/pages/Establishment.tsx` (ERP budget column when present). Tests: `Costs.test.tsx` (`breakdown lists inputs per ha`), `Settings.test.tsx` (`block links shows mismatch`), `Establishment.test.tsx` (`erp budget shown`).

### Task 22: Mobile — pick the store when marking a batch ready

**Repo:** `/home/ubuntu/stive/code/reactnative/upande-production` (Expo SDK 54, fleet base; see AGENTS.md). Files: `src/services/harvest.ts` (`getStores(ctx)`, `markReadyForCollection(ctx, team_id, warehouse)`), `src/services/harvest-queue.ts` (queue carries the warehouse), the harvesting screen's "mark ready" step (store picker, default from `get_stores`, remembered per farm). Jest tests in `__tests__/`. Commit and push to `main` of `st-i-ve/st-i-ve-upande-production-mobile` (already authorised for that repo), no Co-Authored-By trailer.

### Task 23: Integration
Migrate, full backend suite green alone, desk vitest + tsc + build, restart Mutara web, browser check (Settings varieties/block links, Cycles, Block Costs breakdown, Setup Costs), mobile jest; Opus review of the addendum diff; fix; commit.
