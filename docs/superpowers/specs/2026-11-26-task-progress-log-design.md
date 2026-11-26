# Task progress log and once-a-day tick-off

Date: 2026-11-26. Branch: upande_production `mutara`, phone `upande-production` `mutara`. Agreed with the user.

## Why
Weekly tasks run for days; managers want daily progress with notes and photos. The user could not log progress on a
task a second time. User: "use the existing flow but also add the simple log today's progress with a notes field and an
attachment field ... keyboard aware"; "tell the user by a phone message your progress for today has been logged wait
for tomorrow to make another log on the current flow on mobile and go on to build it".

## Goals
1. **Current crew tick-off: once per worker per task per day** (user decision 2026-11-26). A worker already ticked
   off on the same task and work date cannot be entered again; new people can still be added later that day (late
   joiners, a worker who was missed, a second gang). A save where every worker is already logged is refused with
   exactly: "Your progress for today has been logged. Wait for tomorrow to make another log." A mixed save is
   refused whole (nothing written) with "Already logged today on this task: {names}. Remove them and save again, or
   wait for tomorrow." The same worker twice in one save is refused ("{name} is entered twice."). Server-enforced; the
   phone checks first and shows the same messages without calling. A save with no crew entries (status or note only)
   is still allowed the same day.
2. **Log today's progress** (new, any number of times a day): optional quantity done today (task unit), notes
   (multi-line, kept above the keyboard while typing), attachments (camera photo, gallery photo, or a file; several).
3. Progress shows as a timeline per task (date, time, who, quantity, notes, attachment thumbnails/links) on the phone
   task sheet and the desk Plan task panel; task rows show the latest log date.

## Non-goals / anti-goals
- A progress log never creates labour/pay records and never changes done_qty (only approved crew work does).
- Offline logging and photo queueing: the later offline project (it will reuse this form). Online only now.
- No approval of progress logs.

## Design
- New doctype **Task Progress Log** (autoname `TPL-.YYYY.-.#####`): `plan` (Link Production Work Plan, reqd),
  `task` (Data, the Work Plan Task row name, reqd), `unit`, `operation`, `crop` (fetched/copied from the task),
  `log_date` (Date, default today), `logged_at` (Datetime), `logged_by` (Link User), `qty` (Float), `uom` (Link UOM),
  `notes` (Small Text), `attachments` (Table → new child **Task Progress Attachment**: `file_url` (Attach), `file_name`,
  `is_image` (Check)). Read for Production Supervisor / Assistant Manager / Manager / Viewer; create for supervisor,
  assistant, manager. Respect crop_allowed and the awaiting-task visibility (no logs on tasks the user cannot see;
  logging on an awaiting task is refused like recording work).
- Logic `production/logic/progress.py`: `log_progress(plan, task, notes=None, qty=None, log_date=None, files=None)`
  (files = list of already-uploaded file URLs; at least one of notes/qty/files required; qty ≥ 0; log_date not in the
  future), `list_progress(plan, task) -> list[dict]` newest first, `latest_by_task(plan) -> {task: date}`.
- Attachments upload through Frappe's standard `upload_file` (private files), attached to the log after it is created
  (or uploaded first and linked by URL; builder's choice, but files must end up attached to the log doc).
- Endpoints: desk `api/production.py` `log_task_progress`, `list_task_progress`; phone `mobile/progress.py`
  `productionLogProgress`, `productionListProgress` (capability: `plan_tick_off` or `plan_manage` or `plan_approve`).
  `get_plan` and phone task lists carry `last_progress_on`.
- Same-day rule lives in `work.record_task_work` (built-in labour path and WM path alike).

## Left to the builder
Exact layout and copy beyond the fixed message; image compression (keep photos reasonable, e.g. ≤ 1600 px long edge).
Claude's calls: same-day rule keyed on the task's existing Casual Labour Work (docstatus < 2) with the same work_date;
progress logs unlimited per day.

## Rules
No Claude attribution in commits. Never touch MariaDB directly. Backup before migrate; flock .migrate.lock; restart only
frappe16-mutara-web:frappe16-mutara-frappe-web; tests one module at a time; desk bundle in its own commit; phone repo
commits not pushed; new native deps via `npx expo install` (note they need a new APK build).
