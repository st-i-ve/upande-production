# Supervisors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Production Supervisor records feeding every supervisor dropdown; overseer + shared per-activity supervisors per block per week with task routing and shared visibility; Supervisors and Casual Labourers pages in the Scouts card style.
**Spec:** `docs/superpowers/specs/2026-11-26-supervisors-design.md`

## Global Constraints
- Doctype `Production Supervisor`, autoname `field:employee`. Assignment field `category` (Select: blank + Field Operation categories). Field Operation category options gain `Mulching`.
- Stored supervisor values remain Employee ids everywhere.
- Visibility rule exactly as spec Goal 4; routing as Goal 3.
- No Claude attribution. bench/ORM only; `cd /mnt/data/code/frappe16-mutara && bench --site mutara.local backup && flock .migrate.lock bench --site mutara.local migrate`; restart only `frappe16-mutara-web:frappe16-mutara-frappe-web`; Python tests one module at a time; desk bundle commit alone; don't commit .gitignore/Trash/; don't alter site data except via the patch.

## Review Focus
- Existing assignments (no category) keep working as overseer rows; existing tasks keep their supervisor.
- A supervisor removed/inactive no longer appears in dropdowns but old records still display their name.
- Two sharers: both see the task on the phone; a third supervisor on another block does not.
- Category assigned but its supervisor inactive → falls back to overseer? (rule: inactive supervisors are ignored in routing).
- Avocado-only managers still only see their crops on the Supervisors page.

### Task 1: Production Supervisor record, dropdowns, Mulching, patch
Files: new doctype `production/doctype/production_supervisor/`; patch `patches/create_production_supervisors.py` (+ patches.txt); `production/logic/supervisors.py` (`candidates()` → active Production Supervisors; `supervisor_options(crop=None) -> list[dict]`); Casual Labourer `supervisor` link filter / query; `api/production.py` and `api/labourers.py` endpoints that feed supervisor pickers use `supervisor_options`; field_operation.json category options + Mulching. Test `production/tests/test_supervisor_records.py`.
- [ ] Tests: patch creates records for used employees (idempotent); candidates only active supervisors; inactive excluded; saving a casual labourer with a non-supervisor employee refused ("Choose a Production Supervisor."); Mulching accepted on an operation; perms (manager create/write; supervisor read own).
- [ ] RED → implement → migrate → run test_supervisor_records, test_supervisor_plan, test_labourers (if present) → commit.

### Task 2: Per-activity assignments, routing, shared visibility
Files: production_supervisor_assignment.json (+category; uniqueness unit+week+category+supervisor), `production/logic/supervisors.py` (get_week/save_week/copy_week rows carry category; `route(plan_task_row, by_key) -> employee|None`; `fill_plan_tasks` uses route; `visible_task_filter(emp, crop, year, week)` or a python `visible_to(emp, tasks, assignments)` helper; `my_assignments` returns categories), `mobile/api.py` `_scope` users: apply shared visibility in the three task queries (week plan, plan list counts, plan detail), `api/production.py` supervisor-plan endpoints pass category rows. Test `production/tests/test_supervisor_plan.py` (extend).
- [ ] Tests: overseer only → all tasks to overseer; category rows → spraying task to first sharer, weeding falls back to overseer; both sharers see the spraying task on the phone, the overseer does not see it when a category supervisor exists (unless hand-set), a stranger sees nothing; inactive category supervisor ignored → overseer; copy_week copies categories; old rows (blank category) behave as overseer.
- [ ] RED → implement → migrate → run test_supervisor_plan, test_mobile_api, test_approval_chain, test_task_progress → commit.

### Task 3: Desk — supervisor plan editor with categories
Files: `frontend/src/components/plan/SupervisorPlanView.tsx` (+ api types): per block an Overseer picker and an "Add activity" list (category + one or more supervisors); pickers fed by supervisor options; copy last week unchanged. Other supervisor pickers (AddTaskDialog, labourer dialogs) use the supervisor options endpoint. Tests: extend the SupervisorPlanView tests.
- [ ] Failing vitest → implement → vitest + `npx tsc -b` → commit source → build → commit dist alone → restart.

### Task 4: Desk — Supervisors page (Scouts card style)
Files: new `frontend/src/pages/Supervisors.tsx` + components under `frontend/src/components/supervisors/`; route + nav entry; backend `api/supervisors.py` (`list_supervisors(crop=None, year=None, week=None)` with KPIs; `get_supervisor(employee, crop, year, week)` detail: blocks+categories this week, casual labourers (Casual Labourer.supervisor = employee), task counts); manager-only create/edit dialog for Production Supervisor (photo from Employee). Model look and structure on `/mnt/data/code/frappe16-mutara/apps/upande_scp/frontend/src/pages/Scouts.tsx`. Tests: python `test_supervisor_records` (api), vitest page test.
- [ ] Failing tests → implement → tests + tsc → commit source → build → commit dist → restart.

### Task 5: Desk — Casual Labourers page in the card style
Files: `frontend/src/pages/CasualLabourers.tsx`, `frontend/src/components/casuallabourers/*` (card grid with photo + RosterView KPIs; keep filters, add/edit, roster actions, export); filter by supervisor (dropdown of supervisors). Tests: update CasualLabourers tests.
- [ ] Failing vitest → implement → tests + tsc → commit → build → commit dist → restart.
