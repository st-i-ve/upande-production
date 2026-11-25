# Plan Task Change Date / Postpone / Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let managers and holders of a new "Production Plan Editor" role change a weekly task's date, postpone it (with a reason, kept visible as Late) or delete it (with a reason, logged), enforced on the server.

**Architecture:** A new logic module `production/logic/task_schedule.py` holds the rules (permission, labour-work guard, same-week move, cross-week postpone with remainder split, logged delete). Thin whitelisted endpoints in `api/production.py` call it; `save_plan_tasks` routes its delete/date-change paths through the same guards. The desk Plan page gets a per-row actions menu and three themed dialogs.

**Tech Stack:** Frappe v16 (Python, IntegrationTestCase), React + TypeScript + Vite + vitest (frontend/).

**Spec:** `docs/superpowers/specs/2026-11-25-plan-task-reschedule-design.md`

## Global Constraints

- Role name exactly `Production Plan Editor`; `RESCHEDULE_ROLES = {"Production Plan Editor"} | MANAGE_ROLES` (MANAGE_ROLES = Production Manager, System Manager, Avocado Production Manager); Administrator always allowed.
- New Work Plan Task fields, exactly: `original_due_date` (Date, read_only), `postpone_count` (Int, read_only, default 0), `postpone_reason` (Small Text), `postponed_by` (Link User, read_only), `postponed_on` (Datetime, read_only).
- "Labour work recorded" = any `Casual Labour Work` with `plan_task` = the task name and `docstatus < 2`.
- Postponed tasks get `deviation = "Late"`. Done/Skipped tasks cannot be postponed. Same-week date change is not a postpone (postpone_count unchanged) but sets `original_due_date` if empty.
- Delete adds a Comment on the Production Work Plan: `Deleted task {operation_name} on {unit}, due {due_date}: {reason}`.
- Permission failures raise `frappe.PermissionError`; rule failures reuse `_task_rules` / `rules.enforce` (Block / Warn + override_reason).
- No Claude attribution in commits (no Co-Authored-By, no "Generated with"). Never touch MariaDB directly; bench/ORM only. Backup before migrate. Restart only `frappe16-mutara-web:frappe16-mutara-frappe-web`. Run Python tests one module at a time on mutara.local. Whole-file commits; desk bundle rebuild goes in its own commit. Do not commit `.gitignore` or `Trash/`.

## Review Focus

- Supervisor without the role calling `save_plan_tasks` with `_delete` or a changed `due_date` → refused (no back door).
- Postponing a Partly Done task across weeks → original keeps its labour work and becomes Partly Done; remainder task appears in the new week; pay records untouched.
- Postponing into a week whose plan does not exist yet → plan created for the same crop and farm.
- Postpone with nothing left to do (done+pending ≥ planned) on a task with work → refused with a clear message.
- Change date picker on the desk cannot pick outside the task's week; server also refuses.

---

### Task 1: Role, fields, permission and the save_plan_tasks guard

**Files:**
- Modify: `upande_production/fixtures/role.json` (add role), `upande_production/hooks.py` (Role fixture filter list)
- Modify: `upande_production/production/doctype/work_plan_task/work_plan_task.json` (5 fields, after `note`)
- Modify: `upande_production/production/logic/settings.py` (RESCHEDULE_ROLES, `can_reschedule()`)
- Modify: `upande_production/api/production.py` (`get_bootstrap` adds `can_reschedule`; `get_plan` returns the 5 new fields; `save_plan_tasks` guard)
- Create: `upande_production/production/logic/task_schedule.py` (only `require_reschedule()` and `has_work(task)` in this task)
- Test: `upande_production/production/tests/test_plan_task_schedule.py`

**Interfaces:**
- Produces: `settings.can_reschedule() -> bool`; `task_schedule.require_reschedule() -> None` (raises frappe.PermissionError "You are not permitted to change or delete planned tasks."); `task_schedule.has_work(task_name: str) -> bool`; bootstrap key `can_reschedule: bool`; get_plan task dicts carry the 5 new fields.

- [ ] **Step 1: Write failing tests** in `test_plan_task_schedule.py` (fixtures modelled on `test_supervisor_plan.py` setUpClass: farm, crop, op, two units, users for manager / supervisor / supervisor+`Production Plan Editor`; use `use_builtin_labour`). Tests:
  - `test_bootstrap_flag`: as manager `get_bootstrap()["can_reschedule"]` is True; as plain supervisor False; as supervisor with Plan Editor True.
  - `test_supervisor_cannot_delete_via_save`: plain supervisor calls `desk.save_plan_tasks(..., tasks=[{"name": t, "_delete": 1}])` → result is an error envelope (dict with `"error"`) and the row still exists.
  - `test_supervisor_cannot_redate_via_save`: same with `{"name": t, "due_date": <other day same week>}` → error, date unchanged.
  - `test_editor_can_redate_via_save`: Plan Editor supervisor → succeeds; `original_due_date` set to the old date.
  - `test_save_refuses_delete_with_work`: manager, task with one Casual Labour Work (docstatus 0) → error mentioning Skip; row kept.
  - `test_adding_tasks_unchanged`: plain supervisor can still add a new task.
- [ ] **Step 2: Run** `cd /mnt/data/code/frappe16-mutara && bench --site mutara.local run-tests --module upande_production.production.tests.test_plan_task_schedule` — expect failures (missing role/fields).
- [ ] **Step 3: Implement.** Role JSON + hooks filter; fields; backup then migrate: `bench --site mutara.local backup && flock .migrate.lock bench --site mutara.local migrate`. In `save_plan_tasks`: for `_delete` rows call `require_reschedule()` and refuse when `has_work(name)` ("Work is recorded against this task; mark it Skipped instead."); for a saved row whose `due_date` changes call `require_reschedule()` and set `original_due_date` if empty. get_plan field list + the 5 fields.
- [ ] **Step 4: Run the module again** — all pass.
- [ ] **Step 5: Commit** the listed files (message without attribution).

### Task 2: move / postpone / delete logic and endpoints

**Files:**
- Modify: `upande_production/production/logic/task_schedule.py`
- Modify: `upande_production/api/production.py` (3 endpoints)
- Test: `upande_production/production/tests/test_plan_task_schedule.py` (append)

**Interfaces:**
- Consumes: Task 1's `require_reschedule`, `has_work`; `plans.get_or_create_plan(crop, farm, year, week)`; `weeks.iso_of(date)`; `api.production._task_rules(vals, override_reason, exclude_task)`.
- Produces (logic): `move_task(plan: str, task: str, new_date: str, override_reason: str|None=None) -> dict`, `postpone_task(plan, task, new_date, reason, override_reason=None) -> dict` returning `{"plan": <plan of the moved/new task>, "task": <its name>, "split": bool}`, `delete_task(plan, task, reason) -> dict` returning `{"deleted": task}`.
- Produces (API, POST, `@run`, each `_need("Production Work Plan","write")`): `move_plan_task(plan, task, new_date, override_reason=None)`, `postpone_plan_task(plan, task, new_date, reason, override_reason=None)`, `delete_plan_task(plan, task, reason)`.

Rules the code must follow (from the spec):
- move: new_date in the same ISO week as the plan (else ValidationError "Pick a day in the same week; use Postpone to move it later."); run `_task_rules`; stamp original_due_date if empty; postpone_count unchanged.
- postpone: reason required (strip); new_date > current due_date; status Done/Skipped refused. No work → same week: update date; other week: remove row from old plan and append a copy (all fields except name/parent/idx/parentfield/parenttype) to `get_or_create_plan(plan.crop, plan.farm, *iso_of(new_date))`. With work → original row status "Partly Done", stays; remainder = planned_qty − done_qty − pending_qty; ≤ 0 → ValidationError "Nothing is left to do on this task."; new task on new_date (target plan as above) with planned_qty = remainder, status Open, same unit/cycle/operation/uom/rate/supervisor. Both cases stamp on the moved/new task: original_due_date (old due_date if empty, else kept), postpone_count + 1, postpone_reason, postponed_by = session user, postponed_on = now, deviation "Late". Run `_task_rules` for the new date.
- delete: reason required; `has_work` → ValidationError with Skip hint; remove row, save plan, add Comment (Global Constraints wording).
- All three call `require_reschedule()` first.

- [ ] **Step 1: Write failing tests**: `test_move_same_week`, `test_move_other_week_refused`, `test_postpone_same_week_stamps`, `test_postpone_next_week_moves_row` (new plan created for same crop/farm, row gone from old plan, deviation Late, postpone_count 1), `test_postpone_twice_counts_2_keeps_first_date`, `test_postpone_with_work_splits` (planned 10, one labour work qty 4 approved/docstatus 1 via direct insert with done_qty set → original Partly Done with its work; new task planned 6), `test_postpone_nothing_left_refused`, `test_postpone_done_refused`, `test_postpone_requires_reason`, `test_delete_logs_comment`, `test_delete_with_work_refused`, `test_plain_supervisor_refused_on_all_three`.
- [ ] **Step 2: Run the module** — new tests fail.
- [ ] **Step 3: Implement** logic + endpoints.
- [ ] **Step 4: Run the module** — all pass. Also run `upande_production.production.tests.test_supervisor_plan` and `upande_production.production.tests.test_rules` (one at a time) — still pass.
- [ ] **Step 5: Commit.**

### Task 3: Desk — row actions menu and dialogs

**Files:**
- Modify: `frontend/src/lib/api.ts` (PlanTask gains `original_due_date?`, `postpone_count?`, `postpone_reason?`; Bootstrap gains `can_reschedule: boolean`; `movePlanTask`, `postponePlanTask`, `deletePlanTask` rpc wrappers)
- Create: `frontend/src/components/plan/TaskActions.tsx` (menu button + `ChangeDateDialog`, `PostponeDialog`, `DeleteTaskDialog`)
- Modify: `frontend/src/pages/Plan.tsx` (row `<li>` becomes `flex items-center`; existing row `<button>` gets `flex-1`; `TaskActions` rendered beside it when `boot.can_reschedule`; "Postponed ×N from <date>" note with reason as title when `postpone_count > 0`; reload after an action)
- Test: `frontend/src/components/plan/__tests__/TaskActions.test.tsx`

**Interfaces:**
- Consumes: Task 2 endpoints (names above, args as named); rule envelope handling via `ruleFailure` / `BlockNotice` / `OverrideReasonDialog` exactly as `AddTaskDialog.tsx` does.
- Produces: `TaskActions({ plan, task, weekStart, onDone })`.

Behaviour: menu (Popover) with Change date, Postpone, Delete. Change date: DatePicker limited to weekStart..weekStart+6. Postpone: DatePicker (min = day after due date) + required reason textarea. Delete: required reason + confirm button; when `task.work.length > 0` the Delete item is disabled with title "Work is recorded; mark it Skipped instead". Postpone hidden for Done/Skipped. Errors shown inline in the dialog. Menu button must not be nested inside the row button and needs `aria-label="Task actions"`.

- [ ] **Step 1: Write failing vitest tests** (mock `@/lib/api` like `RuleFlow.test.tsx`): postpone sends `(plan, task, date, reason, null)` and blocks submit with empty reason; Warn envelope opens the override dialog and resends with the reason; delete disabled when task has work; change-date dialog calls `movePlanTask`.
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/components/plan/__tests__/TaskActions.test.tsx` — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** that file plus `src/pages/__tests__/Plan.test.tsx` and `src/pages/__tests__/RuleFlow.test.tsx`; `npx tsc -b` clean.
- [ ] **Step 5: Commit** source files. Then `cd frontend && npm run build` and commit `upande_production/public/dist` alone ("Rebuild desk bundle for plan task actions"). Restart `sudo supervisorctl restart frappe16-mutara-web:frappe16-mutara-frappe-web`.
