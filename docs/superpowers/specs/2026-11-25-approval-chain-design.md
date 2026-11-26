# Approval chain: assistant managers, plan approval, two-step work approval, cycle change requests

Date: 2026-11-25. Branch: upande_production `mutara`. Agreed with the user in conversation.

## Why
On the farm the **assistant manager** is the middle point: they create and assign the week's tasks, they are the
first to see work done on tasks they assigned, and the **manager** gives the final word — approving the plan before
it reaches supervisors, and the work before it counts (pay, done quantities, protocol compliance). Separately,
crop cycles today change the moment a supervisor saves, and deleting one is only possible in the Frappe form; the
user wants changes and deletes by non-managers to go through a manager. Farms without assistant managers must keep
working as they do now.

## Goals
1. A switch, **Production Settings → "Assistant manager step"** (Check, default off). Off = today's flow for tasks
   and work (cycle change requests apply regardless).
2. Role **Production Assistant Manager**. Every Work Plan Task records **Assigned by** (the user who created it).
3. With the switch on: tasks created by an assistant manager are **Awaiting approval** (not visible to supervisors
   on the phone, no work can be recorded) until a manager **Approves & forwards** them.
4. With the switch on: work on a task assigned by an assistant manager goes **Pending → Checked (assistant manager
   who assigned it) → Approved (manager)**. Only the manager's approval counts: done quantity, pay, and protocol
   compliance (the protocol step registers as done on the work date).
5. **Cycle change requests**: managers edit and delete cycles directly (logged in the cycle's Frappe version
   history, already on). Supervisors and assistant managers raise a request (edit or delete, with a reason) that a
   manager approves, sends back or rejects. The production app gets a Delete action.

## Non-goals
- No second approver for a manager's own cycle edit/delete (user: "managers go straight through").
- No approval for creating cycles (unchanged: supervisors create directly).
- No re-approval when tasks are postponed / re-dated / deleted (the Plan Editor rules of
  2026-11-25-plan-task-reschedule-design.md govern that).
- With Work Management in Automatic mode, work approval stays in Work Management (production's approval step is
  already skipped there); the two-step work approval applies to built-in labour mode only. Plan approval and cycle
  requests still apply.

## Anti-goals
- Unapproved values must never be live on a cycle: a pending edit leaves the cycle exactly as it was.
- Checked-but-not-approved work must not count as done or be payable.
- A supervisor must not be able to bypass the request through the Frappe form/REST or the older `save_cycle`
  endpoint.

## Approaches (chosen: A)
- **A. Change-request record (chosen).** A separate doctype holds the requested values; approving applies them
  through the same code a manager's edit uses. The cycle keeps working while a request waits.
- B. Frappe Workflow on the cycle: the cycle itself would be "pending", so either it freezes or unapproved values
  go live. Dropped.
- C. Draft copy of the cycle (amend-style): two cycles for one block confuse plans, harvests and the next-cycle
  chain. Dropped.
- For tasks and work: extend the app's own statuses (as labour approvals already do) rather than Frappe Workflow,
  because the Approvals page, the phone and the WM bridge all read these statuses directly.

## Design

### Roles and settings
- New Role `Production Assistant Manager` (desk access; Role fixture list in hooks.py). DocType permissions like
  Production Supervisor on Production Work Plan, Casual Labour Work (read/write/create), Production Crop Cycle
  (read/write/create), plus read on the new request doctype and create on it.
- Assistant managers count as plan editors: add the role to `RESCHEDULE_ROLES` and to `PAY_ROLES`-style planning
  checks so `can_plan` is true for them.
- Production Settings: `assistant_manager_step` (Check, label "Assistant manager step", description "Assistant
  managers' tasks need a manager's approval before supervisors see them, and work on them is checked by the
  assistant manager before the manager approves it.").
- `settings.assistant_step_on() -> bool`, `settings.is_assistant_manager(user=None) -> bool`.

### Work Plan Task
New fields: `assigned_by` (Link User, read_only; set on insert of any task from the session user, including
generated protocol tasks), `awaiting_approval` (Check, read_only, default 0), `forwarded_by` (Link User,
read_only), `forwarded_on` (Datetime, read_only).
- On task creation (save_plan_tasks add, generate week, mobile productionAddTask): when the step is on and the
  session user is an assistant manager and not a manager → `awaiting_approval = 1`.
- Existing rows default 0 = already forwarded; nothing changes for old data.
- Supervisors (desk and phone) do not see awaiting tasks: filter `awaiting_approval = 0` in the mobile task lists
  (mobile/api.py task queries) and in `get_plan` for users who are neither managers nor assistant managers.
  Managers and assistant managers see them with an "Awaiting approval" badge.
- Recording work (`work.record_task_work`) on an awaiting task is refused: "This task is waiting for a manager's
  approval."
- Endpoint `forward_plan_tasks(plan, tasks=None)` (managers only): clears `awaiting_approval` on the given rows (all
  awaiting rows of the plan when `tasks` is None), stamps forwarded_by/on. Plan page shows "N awaiting approval ·
  Approve & forward" for managers; per-row approve also allowed. A manager can also delete an awaiting task with
  the existing delete (reason required).
- Work Management mirroring of a task (planner push) happens only once it is forwarded.

### Two-step work approval (built-in labour mode, step on)
- Casual Labour Work `approval_status` options become `Pending / Checked / Approved / Sent Back`. New fields
  `checked_by` (Link User, read_only), `checked_at` (Datetime, read_only).
- A work entry **needs a check** when the step is on and its task's `assigned_by` holds the assistant manager role
  (and is not a manager). Otherwise the chain is today's (manager approves Pending).
- `approvals.check(names)`: only the task's `assigned_by` user moves Pending → Checked (managers do not check;
  they approve). `approvals.approve(names)`: managers; entries that
  need a check must be Checked, others Pending. `send_back(names, note)`: allowed to the assistant manager on
  Pending entries of their tasks, and to managers on Pending/Checked; returns to the supervisor as today.
  `resubmit` puts the entry back to Pending (it is checked again).
- Pending quantity on the task counts Pending + Checked (drafts), done quantity counts only Approved (submitted) —
  this is today's `refresh_task_done` behaviour and must stay so. Protocol compliance (analytics) already reads
  done/approved work, so a protocol activity registers as done only on the manager's approval, on its work date.
- Approvals page: assistant managers see a **To check** list (Pending work on tasks they assigned); managers see
  **To approve** (Checked, plus Pending that needs no check). `approval_counts` returns both counts for the nav
  badge. Each row shows who checked it.

### Cycle change requests
New doctype **Production Cycle Change Request** (autoname `CCR-.YYYY.-.#####`, track_changes):
`cycle` (Link Production Crop Cycle, reqd), `action` (Select Edit/Delete, reqd), `changes` (JSON:
`{fieldname: {"old": ..., "new": ...}}` for display), `payload` (JSON: the data passed to `update_cycle`),
`reason` (Small Text, reqd), `status` (Select Pending/Approved/Sent Back/Rejected, default Pending),
`requested_by` (Link User), `reviewed_by` (Link User), `reviewed_at` (Datetime), `review_note` (Small Text),
`stale` (Check — set at review time when the cycle's current value of a changed field no longer equals `old`).
- **Protected fields** (`cycle_requests.PROTECTED`): unit, crop, field_crop, sub_crop, variety, item, protocol,
  start_date, planting_date, area_ha, plant_count, expected_harvest_start, expected_harvest_end, and status when it
  becomes Closed or Cancelled. Everything else (notes, stages, flowering/harvest actuals, automatic status moves
  Planned→Active→Harvesting) is not protected.
- `update_cycle` API (api/cycle_setup.py): manager → apply directly (today). Non-manager → if the data changes any
  protected field, create a request (reason required, passed as `reason` in data) and return
  `{"request": name, "pending": True}` without touching the cycle; other fields in the same save are applied
  directly only when no protected field changed (otherwise the whole save becomes the request).
- One open request per cycle: refuse a new one while a Pending request exists ("A change to this cycle is already
  waiting for approval.").
- New `delete_cycle(name, reason)` API: manager → `frappe.delete_doc` (the existing `on_trash` handles the planned
  next cycle). Non-manager → Delete request. Refused up front (both paths) when `_recorded_against` the cycle, with
  the message listing what is recorded.
- `approve_cycle_change(name)` (managers): Edit → recompute `stale`; apply `payload` via `cycle_setup.update_cycle`
  with `frappe.flags.cycle_change_request = name` set; Delete → delete as a manager would. Stamps reviewer.
  `send_back_cycle_change(name, note)` and `reject_cycle_change(name, note)` (note required). The requester can
  edit a Sent Back request's payload and resubmit (→ Pending) or withdraw it (Rejected by themselves is fine:
  status Rejected with note "Withdrawn").
- **No back door:** `ProductionCropCycle.validate` (not new docs): if any protected field changed versus
  `get_doc_before_save()` and the user is not a manager and `frappe.flags.cycle_change_request` is not set and
  `frappe.flags.in_demo_seed`/`in_migrate`/`in_install`/`in_patch` are not set → PermissionError "Changes to a
  cycle's setup need a manager's approval; use Edit cycle to send a request." The legacy `save_cycle` endpoint
  (api/production.py) is covered by the same guard. Production Supervisor already has no delete permission;
  Production Assistant Manager gets none either.
- Desk: Edit cycle dialog for non-managers shows a required "Reason for the change" and its button reads "Send for
  approval"; on return shows "Sent to a manager for approval". Cycle rows and the cycle panel show a
  **Change pending** chip (with requester, and old → new on hover). A **Delete** action on the cycle (menu) asks
  for a reason; managers get a confirm, others "Send delete request". Approvals page gets a **Cycle changes** tab
  (managers: Approve / Send back / Reject with note, a stale warning; requesters: their own requests and notes,
  Edit & resubmit / Withdraw). `approval_counts` includes pending cycle changes for managers.

## Settled after the builder check (Claude's calls unless marked)
- **Manager fallback:** "needs a check" is computed live (step on + task's assigned_by is an assistant manager who
  is enabled and still holds the role). A manager may approve a Pending entry that needs a check (assistant away or
  gone); the UI marks it "Not checked" and asks to confirm, and the entry records `checked_by` empty. With the step
  off, Checked entries are approved like Pending ones.
- **Request payload = changed fields only** (the diff of protected and other fields the user changed), applied via
  `update_cycle(name, payload)`, so values that moved since (e.g. an automatic Planned→Active) are not overwritten.
  `stale` is per changed field (current value ≠ `old`); it shows a warning and the manager must tick "Apply
  anyway" — it does not block.
- **Editing a forwarded task:** when an assistant manager (not a manager) changes unit, cycle, operation,
  planned_qty, rate or uom on a forwarded task, it goes back to Awaiting approval (step on). Work already recorded
  stays; new work waits for the forward. Supervisor/notes changes do not re-await. `assigned_by` stays the creator.
- **Checked counts as pending everywhere** a Pending draft counts today: task pending_qty (work.py), overview
  pending entries, the duplicate-entry check (labourers.py), coverage, and wm_bridge's Pending branches all treat
  Checked like Pending.
- **Who raises cycle requests:** every non-manager who can write cycles — Production Supervisor and Production
  Assistant Manager. Both get create on Production Cycle Change Request and read with `if_owner`; managers and
  System Manager read/write all.
- **Pay visibility (user: "yes"):** assistant managers see pay like supervisors do today — rates, pay value and
  unpaid totals on the Plan and Approvals pages (`can_see_pay` true for them).

## Phone (added 2026-11-26, user: "yes add task 7 and the phone approval screens")
- Capabilities (mobile/access.py): new `plan_check` (Production Assistant Manager) and `plan_approve` (managers).
  Assistant managers also get `plan_view` and `plan_manage` (see and add tasks on the phone); not `plan_tick_off`.
- Phone task data carries `awaiting_approval`; awaiting tasks show an **Awaiting manager** pill. Managers get
  **Approve & forward** on an awaiting task and a week bar "N awaiting · Approve & forward" (same server rule as desk).
- Phone work entries know **Checked** (label "Checked", neutral tone).
- **Approvals screen** on the phone (reached from the Plan tab, with a count badge), built like the Sent back screen:
  assistants see **To check** (Check / Send back with note); managers see **To approve** (Approve / Send back with
  note; a Not checked card asks to confirm, then approves with unchecked_ok). Online only, like Sent back. Pay shown
  only when the user can see pay (same server stripping as other phone lists).
- Claude's calls: cycle change approvals stay desk-only; assistants don't tick off work on the phone.

## Left to the builder
Exact UI placement and copy beyond what is stated; whether the assistant-manager queue and the manager queue are
separate tabs or a filter on the Approvals page (keep the page's existing structure); test layout. Calls made by
Claude (not the user): assistant managers' cycle edits need approval; postpones/deletes need no re-approval; sent
back from either step returns to the supervisor; WM mode keeps work approval in WM; no phone approval screens.

## Rules
No Claude attribution in commits. Never touch MariaDB directly. Backup before migrate; `flock .migrate.lock`;
restart only `frappe16-mutara-web:frappe16-mutara-frappe-web`; run tests one module at a time on mutara.local;
desk bundle rebuild in its own commit; don't commit .gitignore or Trash/.
