# Weekly plan tasks: change date, postpone, delete

Date: 2026-11-25. Branch: upande_production `mutara`. Approved by the user in conversation ("go on with the tasks design").

## Why
Field plans slip: rain, a missing input, a crew pulled elsewhere. Today a planned task can only be added; the Plan
page has no way to move or remove one, and the server lets anyone with Work Plan write (supervisors included) delete
rows through `save_plan_tasks` with no reason and no trace. Managers want named people to move, postpone or drop a
task, with the slip still visible in reports and a record of every delete.

## Goals
- Change a task's date within its week.
- Postpone a task to a later date, in this or a later week, with a reason; the slip stays visible (deviation Late).
- Delete a task from its week, with a reason, logged on the week's plan.
- A permission decides who may do these three; the server enforces it, not only the screen.

## Non-goals
- No manager-approval step for a postpone (the user asked for a permission, not an approval).
- No phone editing of dates (supervisors see the new date on their next sync).
- Cycle change/delete approval is a separate design (piece 1).

## Anti-goals
- Pay records must never lose their task: a task with labour work recorded can't be deleted.
- A postpone must not hide the delay: the first planned date is kept and reports show Late.

## Approaches
1. **Role "Production Plan Editor" (chosen).** Managers (MANAGE_ROLES) always may; the role is given person by
   person through role profiles. Frappe-native, per user, works with the existing role fixtures.
2. Settings tick box "supervisors may reschedule": all-or-nothing across supervisors. Dropped.
3. Manager approval of each postpone (Pending → Approved, like labour work): slower, not what was asked. Dropped.

## Design
**Permission.** New Role `Production Plan Editor` (added to the Role fixture filter in hooks.py).
`RESCHEDULE_ROLES = {"Production Plan Editor"} | MANAGE_ROLES` in logic/settings.py. Bootstrap gains
`can_reschedule`. The existing `_delete` path in `save_plan_tasks` and any `due_date` change on a saved row are
refused (PermissionError) for users without one of those roles; adding new tasks is unchanged.

**New fields on Work Plan Task:** `original_due_date` (Date, read-only; set the first time the date moves),
`postpone_count` (Int, read-only), `postpone_reason` (Small Text), `postponed_by` (Link User, read-only),
`postponed_on` (Datetime, read-only).

**Endpoints (api/production.py, POST, all check the permission):**
- `move_plan_task(plan, task, new_date)` — same ISO week only; runs the activity rules like a date edit does
  (`_task_rules` with override_reason passthrough). Sets `original_due_date` if empty. Not counted as a postpone.
- `postpone_plan_task(plan, task, new_date, reason, override_reason=None)` — reason required; new_date after the
  current due_date. Same week: change the date on the row. Later week: the row moves to that week's plan
  (`plans.get_or_create_plan` for the same crop/farm). Stamps original_due_date (if empty), postpone_count+1,
  reason, by, on; deviation = Late. **A task with labour work recorded** (any Casual Labour Work with docstatus < 2
  on that plan_task) stays where it is and keeps its work: it becomes Partly Done, and a new task for the
  remaining quantity (planned_qty − done_qty − pending_qty, minimum 0 → refuse when nothing remains) is created on
  the new date, carrying the postpone stamps. Status Done/Skipped tasks can't be postponed.
- `delete_plan_task(plan, task, reason)` — reason required. Refused when labour work is recorded against the task
  (message points to Skip). Otherwise the row is removed and a Comment is added on the Production Work Plan:
  "Deleted task <operation_name> on <unit>, due <date>: <reason>" (comment_by = the user).
- `save_plan_tasks` keeps working for add/edit, but its `_delete` and `due_date` changes route through the same
  permission and labour-work checks (no back door).

**Desk (Plan page, Tasks view).** Each task row gets a small actions menu, shown only when `boot.can_reschedule`:
Change date, Postpone, Delete. Each opens our own themed dialog (date picker limited to the week for Change date;
date + required reason for Postpone; required reason + confirmation for Delete). A Warn rule result asks for an
override reason the same way AddTaskDialog does (RuleFlow). Rows show a small "Postponed ×N from <date>" note with
the reason on hover. Delete is hidden (with Skip suggested) on tasks that have work.

**Reports.** Postponed tasks carry deviation Late, so the existing deviation reporting shows them.

## Left to the builder
Exact menu placement and dialog wording; test layout (one test module for the endpoints, vitest for the dialogs).

## Rules
No Claude attribution in commits. Never touch MariaDB directly. Backup before migrate; restart only
frappe16-mutara-* supervisor groups; run tests one module at a time on mutara.local.
