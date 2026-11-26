# Approval Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assistant managers create and assign tasks that a manager approves and forwards; work on their tasks is checked by them and approved by a manager; supervisors' and assistant managers' cycle setup edits and deletes go through a manager as change requests.

**Architecture:** Settings + role helpers in `production/logic/settings.py`. Task stamping (assigned_by / awaiting) happens once, in `ProductionWorkPlan.validate`, so every creation path (save_plan_tasks, generate week, mobile add, postpone copies) is covered. Two-step work approval extends `production/logic/approvals.py` with a `Checked` status. Cycle change requests live in a new doctype plus `production/logic/cycle_requests.py`; `api/cycle_setup.py` routes non-manager edits there, and `ProductionCropCycle.validate` closes the back door.

**Tech Stack:** Frappe v16 (Python, IntegrationTestCase), React + TypeScript + Vite + vitest (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-11-25-approval-chain-design.md` (read the "Settled after the builder check" section: it binds).

## Global Constraints

- Role name exactly `Production Assistant Manager`. Settings field `assistant_manager_step` (Check, default 0) on Production Settings, label "Assistant manager step".
- Managers = `MANAGE_ROLES` (Production Manager, System Manager, Avocado Production Manager) or Administrator. A user with both a manager role and the assistant role counts as a manager.
- Assistant managers: in `PAY_ROLES` (so `can_see_pay` and `can_plan` are true) and in `RESCHEDULE_ROLES`.
- Work Plan Task new fields: `assigned_by` (Link User, read_only), `awaiting_approval` (Check, read_only, default 0), `forwarded_by` (Link User, read_only), `forwarded_on` (Datetime, read_only).
- Casual Labour Work `approval_status` options `Pending\nChecked\nApproved\nSent Back`; new `checked_by` (Link User, read_only), `checked_at` (Datetime, read_only).
- Messages, verbatim: awaiting task work refused → "This task is waiting for a manager's approval."; second open request → "A change to this cycle is already waiting for approval."; back-door guard → "Changes to a cycle's setup need a manager's approval; use Edit cycle to send a request."
- New doctype **Production Cycle Change Request**, autoname `CCR-.YYYY.-.#####`, track_changes 1, fields exactly as the spec lists.
- `PROTECTED` = unit, crop, field_crop, sub_crop, variety, item, protocol, start_date, planting_date, area_ha, plant_count, expected_harvest_start, expected_harvest_end; plus status when the new value is Closed or Cancelled.
- "Checked" counts as pending (not done, not payable) everywhere "Pending" drafts count today.
- No Claude attribution in commits (no Co-Authored-By, no "Generated with"). Never touch MariaDB directly; bench/ORM only. Backup before migrate: `bench --site mutara.local backup && flock .migrate.lock bench --site mutara.local migrate` (run from `/mnt/data/code/frappe16-mutara`). Restart only `sudo supervisorctl restart frappe16-mutara-web:frappe16-mutara-frappe-web`. Run Python tests one module at a time: `bench --site mutara.local run-tests --module <module>`. Whole-file commits; desk bundle (`upande_production/public/dist`) rebuilt and committed alone. Do not commit `.gitignore` or `Trash/`.

## Review Focus

- Step switched off after tasks were created awaiting → those tasks must not stay hidden forever: with the step off, `awaiting_approval` is ignored by visibility and recording (Task 2 test `test_step_off_ignores_awaiting`).
- Assistant manager who loses the role / is disabled while entries wait for their check → manager can approve them as "Not checked" (Task 3 test `test_manager_approves_unchecked_when_assistant_gone`).
- Supervisor posts protected fields through `frappe.client.save` / `save_cycle` → refused, cycle unchanged (Task 4 test `test_back_door_refused`).
- Automatic status move (Planned→Active by on_update/cycle_chain) or harvest actuals while a request waits → not blocked by the guard, and approving the request does not overwrite them (Task 4 test `test_auto_fields_not_guarded_and_not_overwritten`).
- Delete request on a cycle that gets records after the request was raised → approve refuses with the "recorded against" message (Task 4 test `test_approve_delete_refused_when_recorded`).

---

### Task 1: Role, setting, task stamping

**Files:**
- Modify: `upande_production/fixtures/role.json`, `upande_production/hooks.py` (Role fixture filter)
- Modify: `upande_production/production/doctype/production_settings/production_settings.json` (+ `assistant_manager_step` with the spec's description)
- Modify: `upande_production/production/doctype/work_plan_task/work_plan_task.json` (4 fields after `postponed_on`)
- Modify: `upande_production/production/doctype/production_work_plan/production_work_plan.py` (stamping in validate)
- Modify: `upande_production/production/logic/settings.py`
- Modify: `upande_production/api/production.py` (`get_bootstrap` keys; `get_plan` returns the 4 fields)
- Modify: DocType permissions JSON: Production Work Plan, Casual Labour Work, Production Crop Cycle (read/write/create for the new role, no delete)
- Test: `upande_production/production/tests/test_approval_chain.py` (new; fixtures modelled on `test_plan_task_schedule.py`: farm, crop, op, units, users manager / supervisor / assistant manager; `use_builtin_labour`; a helper to toggle `assistant_manager_step`)

**Interfaces:**
- Produces: `settings.ASSISTANT_ROLE = "Production Assistant Manager"`; `settings.assistant_step_on() -> bool`; `settings.is_assistant_manager(user=None) -> bool` (holds the role, user enabled, and is not a manager); `settings.is_manager_user(user) -> bool` (MANAGE_ROLES for any user, Administrator true). Bootstrap keys `is_assistant_manager: bool`, `assistant_step: bool`. Every new Work Plan Task row gets `assigned_by` = session user when empty; `awaiting_approval = 1` when `assistant_step_on()` and `is_assistant_manager()` for the session user.

- [ ] **Step 1: Write failing tests** `test_bootstrap_flags`, `test_assigned_by_stamped_for_any_creator` (manager adds via `save_plan_tasks` → assigned_by manager, awaiting 0), `test_assistant_task_awaits_when_step_on`, `test_assistant_task_not_awaiting_when_step_off`, `test_generated_tasks_stamped` (`plans.generate_week_detail` as assistant with step on → rows awaiting), `test_assistant_can_plan_and_see_pay` (bootstrap `can_plan` and `can_see_pay` True).
- [ ] **Step 2: Run** the module — fails.
- [ ] **Step 3: Implement.** Stamp in `ProductionWorkPlan.validate` for rows whose `assigned_by` is empty (rows copied by `task_schedule` keep theirs). Backup + migrate.
- [ ] **Step 4: Run** `test_approval_chain`, then `test_plan_task_schedule`, `test_supervisor_plan` (one at a time) — pass.
- [ ] **Step 5: Commit.**

### Task 2: Awaiting tasks — hide, refuse work, forward, re-await, WM

**Files:**
- Modify: `upande_production/api/production.py` (`get_plan` filter; `save_plan_tasks` re-await; new endpoint `forward_plan_tasks`)
- Create: `upande_production/production/logic/task_approval.py`
- Modify: `upande_production/mobile/api.py` (the three task queries near lines 190, 630, 685: add `awaiting_approval: 0` when the step is on and the user is neither manager nor assistant)
- Modify: `upande_production/production/logic/work.py` (`record_task_work` refusal)
- Modify: `upande_production/production/logic/wm_bridge.py` (plan-row sync loop near line 314 skips rows with `awaiting_approval` while the step is on)
- Test: `production/tests/test_approval_chain.py` (append)

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: `task_approval.visible_filter() -> dict` (`{"awaiting_approval": 0}` when step on and user is neither manager nor assistant, else `{}`); `task_approval.forward(plan: str, tasks: list[str] | None) -> dict` returning `{"forwarded": [names]}` (managers only, PermissionError otherwise; clears awaiting, stamps forwarded_by/on, saves the plan so WM sync runs); `task_approval.REAWAIT_FIELDS = ("unit", "cycle", "operation", "planned_qty", "rate", "uom")`. API `forward_plan_tasks(plan, tasks=None)` (POST, `@run`, `_need("Production Work Plan","write")`, `tasks` JSON list or None). `get_plan` tasks carry `awaiting_approval`, `assigned_by`, `forwarded_by`.

- [ ] **Step 1: Write failing tests** `test_supervisor_does_not_see_awaiting` (get_plan and mobile week tasks), `test_manager_and_assistant_see_awaiting`, `test_record_work_on_awaiting_refused` (exact message), `test_forward_all_and_one` (stamps; supervisor then sees it), `test_forward_refused_for_assistant_and_supervisor`, `test_assistant_edit_key_field_reawaits` (forwarded task, assistant changes planned_qty → awaiting 1; changes note → stays 0), `test_manager_edit_does_not_reawait`, `test_step_off_ignores_awaiting`, `test_manager_can_delete_awaiting` (existing delete with reason).
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.** With the step off, nothing filters or refuses on `awaiting_approval`.
- [ ] **Step 4: Run** `test_approval_chain`, `test_plan_task_schedule`, `test_supervisor_plan`, and any `test_wm*` / mobile test modules that exist (one at a time) — pass.
- [ ] **Step 5: Commit.**

### Task 3: Two-step work approval

**Files:**
- Modify: `upande_production/production/doctype/casual_labour_work/casual_labour_work.json` (options + 2 fields)
- Modify: `upande_production/production/logic/approvals.py`, `upande_production/api/approvals.py`
- Modify (Checked = pending): `production/logic/work.py` (`pending_qty`), `api/overview.py:226`, `production/logic/labourers.py:286`, `api/coverage.py:40`, `production/logic/wm_bridge.py` (Pending branches ~437, 550, 562)
- Test: `production/tests/test_approval_chain.py` (append); existing `test_approvals*` modules must still pass

**Interfaces:**
- Consumes: Task 1 helpers; Work Plan Task `assigned_by`.
- Produces: `approvals.needs_check(doc) -> bool` (step on, entry has a plan_task, its task's `assigned_by` is an assistant manager per `is_assistant_manager(user)`); `approvals.check(names) -> {"checked": [...]}` (only the task's `assigned_by`; entries must be Pending; stamps checked_by/at); `approvals.approve(names, unchecked_ok=0)` — managers; an entry that needs a check must be Checked unless `unchecked_ok` truthy (then approved with checked_by empty); entries not needing a check may be Pending or Checked; `send_back(names, note)` — managers on Pending/Checked, the assigning assistant on Pending of their tasks; `resubmit` → Pending and clears checked_by/at. `STATUSES = ("Pending", "Checked", "Approved", "Sent Back")`. `list_approvals(..., status, queue=None)`: `queue="check"` → Pending entries on tasks the session user assigned; `queue="approve"` → Checked plus Pending that need no check (plus, flagged `needs_check: true`, Pending that still need a check, so the manager can approve as Not checked); group dicts gain `needs_check`, `checked_by`, `checked_by_name`, `checked_at`. `approval_counts()` gains `to_check` (session user's queue) and keeps `total` as the manager's to-approve count. API wrappers: `check(names)`, `approve(names, unchecked_ok=0)`, `list_approvals(..., queue=None)`.

- [ ] **Step 1: Write failing tests** `test_work_on_assistant_task_needs_check`, `test_only_assigner_checks` (other assistant / supervisor / manager refused), `test_manager_cannot_approve_unchecked_without_flag`, `test_manager_approves_checked` (done_qty updates, pending_qty drops), `test_checked_counts_as_pending` (task pending_qty includes Checked; done_qty does not), `test_manager_approves_unchecked_when_assistant_gone` (role removed → `needs_check` false → plain approve works) and `test_unchecked_ok_flag`, `test_send_back_from_checked_and_resubmit_clears_check`, `test_manager_task_work_single_step`, `test_step_off_checked_approvable`, `test_queues_and_counts`, `test_protocol_compliance_only_after_approve` (protocol task: analytics compliance shows not done while Checked, done after approve).
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_approval_chain`, then existing approval/labour/work/overview test modules found by `ls production/tests | grep -i "approv\|labour\|work\|overview\|coverage"` (one at a time) — pass.
- [ ] **Step 5: Commit.**

### Task 4: Cycle change requests (backend)

**Files:**
- Create: `upande_production/production/doctype/production_cycle_change_request/` (json, py, `__init__.py`); permissions: Production Supervisor and Production Assistant Manager create + read/write `if_owner`; managers and System Manager full (no delete for non-managers)
- Create: `upande_production/production/logic/cycle_requests.py`
- Modify: `upande_production/api/cycle_setup.py` (route `update_cycle`; endpoints)
- Modify: `upande_production/production/doctype/production_crop_cycle/production_crop_cycle.py` (guard)
- Modify: `upande_production/production/logic/approvals.py` `approval_counts` (`cycle_changes` count for managers)
- Modify: `upande_production/production/logic/cycle_setup.py` `edit_info` (adds `pending_request: {name, requested_by, action, changes} | None`); `api/production.py` `list_cycles` rows gain `pending_request` (name/action/requested_by) 
- Test: `production/tests/test_cycle_requests.py` (new); `test_cycle_setup` must still pass

**Interfaces:**
- Produces (logic): `PROTECTED` (Global Constraints); `diff(doc, data) -> dict` `{field: {"old", "new"}}` of fields in data whose value differs (dates/numbers normalised); `touches_protected(changes, data) -> bool`; `request_edit(name, data, reason) -> {"request": name, "pending": True}`; `request_delete(name, reason)` same shape; `delete_cycle(name, reason) -> {"deleted": name} | {"request": ..., "pending": True}`; `approve(name, apply_anyway=0) -> dict` (Edit: recompute per-field stale; if stale and not apply_anyway → ValidationError listing fields; else apply `payload` via `cycle_setup.update_cycle` with `frappe.flags.cycle_change_request = name`; Delete: refuse when `_recorded_against`, else delete as manager); `send_back(name, note)`, `reject(name, note)` (note required, managers); `resubmit(name, data, reason=None)` (requester, Sent Back → Pending, recomputes changes/payload); `withdraw(name)` (requester, → Rejected, review_note "Withdrawn"); `list_requests(status=None, crop=None) -> list[dict]` (managers all, others own). Payload holds only the changed fields.
- Produces (API in `api/cycle_setup.py`, POST, `@run`): `update_cycle(name, data)` (manager → as today; non-manager with protected change → requires `data["reason"]`, returns request envelope; non-manager without protected change → applied as today), `delete_cycle(name, reason)`, `list_cycle_changes(status=None, crop=None)`, `approve_cycle_change(name, apply_anyway=0)`, `send_back_cycle_change(name, note)`, `reject_cycle_change(name, note)`, `resubmit_cycle_change(name, data, reason=None)`, `withdraw_cycle_change(name)`.
- Guard: `validate` on a non-new cycle raises PermissionError (Global Constraints message) when a PROTECTED field changed vs `get_doc_before_save()` (status only when it becomes Closed/Cancelled) and the session user is not a manager and none of `frappe.flags.cycle_change_request`, `in_demo_seed`, `in_migrate`, `in_install`, `in_patch` is set. System-driven saves (cycle_chain, harvest actuals) must not trip it — they don't change protected fields; if a test proves one does, add a narrowly named flag and say so in the report.

- [ ] **Step 1: Write failing tests** `test_manager_edits_directly`, `test_supervisor_protected_edit_makes_request` (cycle unchanged, request Pending with diff + payload of changed fields only), `test_reason_required`, `test_notes_only_edit_applies_directly`, `test_one_pending_per_cycle` (exact message), `test_approve_applies_payload`, `test_stale_needs_apply_anyway`, `test_send_back_resubmit_withdraw`, `test_reject_needs_note`, `test_delete_manager_direct`, `test_delete_request_then_approve`, `test_delete_refused_when_recorded`, `test_approve_delete_refused_when_recorded`, `test_back_door_refused` (supervisor `frappe.client.save` style `doc.save()` and `api.production.save_cycle`), `test_auto_fields_not_guarded_and_not_overwritten`, `test_requests_visible_to_owner_only`, `test_counts_include_cycle_changes`.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.** Backup + migrate for the new doctype.
- [ ] **Step 4: Run** `test_cycle_requests`, `test_cycle_setup`, and any cycle-chain test module (one at a time) — pass.
- [ ] **Step 5: Commit.**

### Task 5: Desk — Plan approval and two-step Approvals page

**Files:**
- Modify: `frontend/src/lib/api.ts` (Bootstrap `is_assistant_manager`, `assistant_step`; PlanTask `awaiting_approval`, `assigned_by`, `forwarded_by`; `forwardPlanTasks(plan, tasks?)`; `checkWork(names)`; `approve(names, uncheckedOk?)`; `listApprovals` `queue`; ApprovalGroup `needs_check`, `checked_by_name`, `checked_at`; counts `to_check`)
- Modify: `frontend/src/pages/Plan.tsx` (row "Awaiting approval" badge; for managers a header bar "N awaiting approval · Approve & forward" and per-row approve in `TaskActions` menu)
- Modify: `frontend/src/pages/Approvals.tsx`, `frontend/src/components/approvals/ApprovalCard.tsx` (assistant: "To check" queue with Check / Send back; manager: "To approve" queue, cards show "Checked by X" or a "Not checked" tag; approving a Not checked card asks to confirm and sends `uncheckedOk`); sidebar badge uses `to_check` for assistants
- Test: `frontend/src/pages/__tests__/Plan.test.tsx`, `frontend/src/pages/__tests__/Approvals.test.tsx` (extend)

**Interfaces:**
- Consumes: Task 2 and 3 API names and fields above.

Keep the page's existing structure; queues are a segmented toggle or tab on the existing status filter, builder's choice. Use existing themed dialogs (no `window.confirm`).

- [ ] **Step 1: Write failing vitest tests**: awaiting badge shown; manager "Approve & forward" calls `forwardPlanTasks(plan)`; assistant sees "To check" and Check calls `checkWork(names)`; manager approving a Not checked card shows a confirm then calls `approve(names, 1)`; Checked card shows "Checked by".
- [ ] **Step 2: Run** `cd frontend && npx vitest run src/pages/__tests__/Plan.test.tsx src/pages/__tests__/Approvals.test.tsx` — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** those files plus `src/components/plan` and `src/components/approvals` tests; `npx tsc -b` clean.
- [ ] **Step 5: Commit** source. Then `npm run build`, commit `upande_production/public/dist` alone ("Rebuild desk bundle for plan approval and work checks"), restart the web group.

### Task 6: Desk — cycle change requests

**Files:**
- Modify: `frontend/src/lib/cycle-setup-api.ts` (wrappers for every Task 4 endpoint; types `CycleChangeRequest`, `pending_request`)
- Modify: `frontend/src/components/cycles/EditCycleDialog.tsx` (non-managers: required "Reason for the change", button "Send for approval", success "Sent to a manager for approval"; when `pending_request` exists show it and disable sending)
- Create: `frontend/src/components/cycles/DeleteCycleDialog.tsx` (reason required; managers "Delete cycle" confirm; others "Send delete request")
- Modify: `frontend/src/pages/Cycles.tsx` (Delete action in the row/panel menu; "Change pending" chip with requester and old → new on hover)
- Create: `frontend/src/components/approvals/CycleChanges.tsx`; Modify `frontend/src/pages/Approvals.tsx` (a "Cycle changes" tab: managers Approve / Send back / Reject with note, stale warning with "Apply anyway" tick; requesters their own with Edit & resubmit / Withdraw)
- Test: `frontend/src/components/cycles/__tests__/EditCycleDialog.test.tsx` (extend), `frontend/src/components/approvals/__tests__/CycleChanges.test.tsx` (new)

**Interfaces:**
- Consumes: Task 4 API and `edit_info.pending_request`, `list_cycles` `pending_request`, `approval_counts.cycle_changes`.

- [ ] **Step 1: Write failing vitest tests**: non-manager edit requires reason and shows "Send for approval"; request envelope shows the sent message; delete dialog requires reason and calls `deleteCycle`; manager approve on a stale request is disabled until "Apply anyway" is ticked, then calls `approveCycleChange(name, 1)`; reject requires note.
- [ ] **Step 2: Run** those files — fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** them plus `src/pages/__tests__/Cycles.test.tsx` and `Approvals.test.tsx`; `npx tsc -b` clean.
- [ ] **Step 5: Commit** source; rebuild bundle and commit `public/dist` alone ("Rebuild desk bundle for cycle change requests"); restart the web group.

### Task 7: Mobile API for assistant managers, forwarding and approvals

**Files:**
- Modify: `upande_production/mobile/access.py` (capabilities `plan_check`, `plan_approve`; assistant role in `plan_view`, `plan_manage`)
- Modify: `upande_production/mobile/api.py` (`TASK_FIELDS` / `PLAN_TASK_FIELDS` + `awaiting_approval`; get_session_info carries the new capabilities through `capabilities()`)
- Create: `upande_production/mobile/approvals.py` (phone endpoints, same `_run` / `_need` / `_payload` / `_fail` / `_strip_pay` patterns as mobile/api.py)
- Test: `upande_production/production/tests/test_mobile_approvals.py` (new); `test_mobile_api`, `test_mobile_access` must still pass

**Interfaces:**
- Consumes: `approvals.list_approvals(crop, status, ..., queue)`, `approvals.check`, `approvals.approve(names, unchecked_ok)`, `approvals.send_back(names, note)`, `approvals.approval_counts()`, `task_approval.forward(plan, tasks)`.
- Produces (whitelisted, JSON body like other phone endpoints, success `{"status": "success", ...}`): `productionListApprovals` (body `crop`, `queue` "check"|"approve") → `{"status","groups","counts"}` with pay stripped when the user can't see pay; `productionCheckWork` (`names`) ; `productionApproveWork` (`names`, `unchecked_ok`); `productionSendBackWork` (`names`, `note`); `productionForwardTasks` (`plan`, `tasks` optional) ; `productionApprovalCounts` → `{"status","to_check","to_approve"}`. Guards: check needs `plan_check`, approve/forward need `plan_approve`, send back needs either; list "check" needs `plan_check`, "approve" needs `plan_approve`.

- [ ] **Step 1: Write failing tests**: `test_capabilities_per_role` (assistant: plan_view, plan_manage, plan_check true; plan_tick_off, plan_approve false; manager: plan_approve true), `test_phone_tasks_carry_awaiting`, `test_phone_check_then_approve` (entry Pending → Checked → Approved via the endpoints), `test_phone_unchecked_approve_needs_flag`, `test_phone_send_back_needs_note`, `test_phone_forward_manager_only`, `test_phone_lists_strip_pay`, `test_phone_counts`.
- [ ] **Step 2: Run** — fails.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `test_mobile_approvals`, `test_mobile_api`, `test_mobile_access`, `test_approval_chain` (one at a time) — pass.
- [ ] **Step 5: Commit.** Also update `upande_production/mobile/SUPERVISOR_API.md` with the new endpoints.

### Task 8: Phone app — awaiting tasks, forward, Checked, Approvals screen

Repo: `/mnt/data/code/reactnative/upande-production`, branch `mutara` (commit there; do not push).

**Files:**
- Modify: `src/access.ts` (`plan_check`, `plan_approve` in Capabilities and KEYS)
- Modify: `src/services/planning.ts` (ApprovalStatus + `'Checked'`; approvalMeta "Checked"; task `awaiting_approval`; `planningApi.listApprovals(crop, queue)`, `checkWork`, `approveWork(names, uncheckedOk)`, `sendBackWork(names, note)`, `forwardTasks(plan, tasks?)`, `approvalCounts()`)
- Modify: `src/components/plan/TaskCard.tsx`, `TaskSheet.tsx` (Awaiting manager pill; managers' Approve & forward), `app/(tabs)/plan.tsx` (week bar for managers; entry to Approvals with count badge when plan_check or plan_approve)
- Create: `app/plan/approvals.tsx` (modelled on `app/plan/sent-back.tsx`: To check / To approve, select cards, actions, note sheet, Not checked confirm through the app's alert host, online only)
- Test: `__tests__/approvals-test.ts` (service + capability parsing) and extend `__tests__/planning-test.ts`, `__tests__/access.test.ts`

**Interfaces:**
- Consumes: Task 7 endpoint names and shapes exactly.

- [ ] **Step 1: Write failing jest tests**: capability parsing keeps plan_check/plan_approve; approvalMeta("Checked") label "Checked"; unknown status no longer coerces Checked to Pending; listApprovals sends `{crop, queue}`; approveWork sends `unchecked_ok` 1 only when asked; forwardTasks sends plan and tasks.
- [ ] **Step 2: Run** `npx jest __tests__/approvals-test.ts __tests__/planning-test.ts __tests__/access.test.ts` — fails.
- [ ] **Step 3: Implement.** Use the app's own components (Screen, Pill, Button, Sheet, Toast, AppAlertHost); no native Alert.
- [ ] **Step 4: Run** those tests, then the full `npm test` and `npx tsc --noEmit` — pass.
- [ ] **Step 5: Commit** in the phone repo (no attribution).
