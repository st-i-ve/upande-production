# Task Progress Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Once-a-day crew tick-off with a clear message, plus an unlimited "Log today's progress" (qty, notes, attachments) shown as a timeline on phone and desk.
**Architecture:** New Task Progress Log doctype + `production/logic/progress.py`; same-day rule in `work.record_task_work`; thin desk and phone endpoints; desk dialog + timeline; phone sheet + timeline.
**Spec:** `docs/superpowers/specs/2026-11-26-task-progress-log-design.md`

## Global Constraints
- Message verbatim: "Your progress for today has been logged. Wait for tomorrow to make another log."
- Doctype names exactly `Task Progress Log`, child `Task Progress Attachment`; autoname `TPL-.YYYY.-.#####`.
- Progress logs never create Casual Labour Work or change done_qty/pending_qty.
- No Claude attribution in commits. bench/ORM only; backup before migrate (`cd /mnt/data/code/frappe16-mutara && bench --site mutara.local backup && flock .migrate.lock bench --site mutara.local migrate`); restart only `frappe16-mutara-web:frappe16-mutara-frappe-web`; Python tests one module at a time; desk bundle commit alone; phone repo not pushed. If the site has Custom DocPerm for a role, make perms effective (see patches/add_assistant_manager_perms.py).

## Review Focus
- Same-day second crew save on a task refused; next day allowed; status-only same-day save allowed (Task 1 tests).
- Supervisor cannot log progress on a task they cannot see (awaiting with step on, other crop) (Task 1).
- Attachments end up attached to the log and are private (Task 1).
- Keyboard never covers the notes box on the phone (Task 3, manual note in report + component uses the app's keyboard-aware pattern).
- A progress log with nothing in it (no notes, qty, files) refused (Task 1).

### Task 1: Server — doctype, logic, same-day rule, endpoints
Files: new doctypes under `upande_production/production/doctype/task_progress_log/` and `task_progress_attachment/`; create `production/logic/progress.py`; modify `production/logic/work.py`, `api/production.py` (endpoints; `get_plan` adds `last_progress_on`), create `mobile/progress.py`; modify `mobile/api.py` task lists (`last_progress_on`); `mobile/SUPERVISOR_API.md`. Test: `production/tests/test_task_progress.py` (new).
Interfaces produced: `progress.log_progress(plan, task, notes=None, qty=None, log_date=None, files=None) -> dict` (the saved log as dict incl. attachments), `progress.list_progress(plan, task) -> list[dict]`, `progress.latest_by_task(plan) -> dict`; desk `log_task_progress(plan, task, notes=None, qty=None, log_date=None, files=None)`, `list_task_progress(plan, task)` (POST, `@run`); phone `productionLogProgress` (body plan, task, notes, qty, log_date, files[]) → `{"status":"success","log":{...}}`, `productionListProgress` (plan, task) → `{"status":"success","logs":[...]}`. `files` = list of file URLs returned by `/api/method/upload_file`; the logic attaches those File docs to the log (set attached_to_doctype/name) and fills the child table.
- [ ] Failing tests: same_day_second_crew_save_refused (exact message), next_day_allowed, status_only_same_day_allowed, log_progress_notes_only, log_progress_requires_something, log_progress_no_labour_rows (done_qty unchanged, no CLW), log_on_awaiting_refused_for_supervisor, files_attached_to_log, list_newest_first, get_plan_last_progress_on, phone_endpoints_roundtrip.
- [ ] Run (fail) → implement → migrate → run test_task_progress, test_approval_chain, test_mobile_api, test_supervisor_plan → commit.

### Task 2: Desk — Log progress dialog and timeline
Files: `frontend/src/lib/api.ts` (wrappers, PlanTask `last_progress_on`), create `frontend/src/components/plan/LogProgressDialog.tsx` and `ProgressTimeline.tsx`; modify `frontend/src/pages/Plan.tsx` (button in the task panel / TaskActions; timeline in the task detail; "Last log <date>" on the row). Upload files with the existing desk upload helper if one exists (grep `upload_file`), else POST FormData to `/api/method/upload_file` with `is_private=1`. Test: `frontend/src/components/plan/__tests__/LogProgress.test.tsx`.
- [ ] Failing vitest: requires notes/qty/file; sends files' URLs; timeline renders newest first with attachments → implement → vitest + `npx tsc -b` → commit source → `npm run build` → commit dist alone ("Rebuild desk bundle for task progress log") → restart web group.

### Task 3: Phone — Log today's progress, timeline, once-a-day message
Repo `/mnt/data/code/reactnative/upande-production` (branch mutara). Add `expo-image-picker` and `expo-document-picker` with `npx expo install`. Files: `src/services/planning.ts` (logProgress, listProgress, uploadFile via the app's api client multipart; PlanTask `last_progress_on`; same-day pre-check helper `loggedToday(task, workDate)`), create `src/components/plan/LogProgressSheet.tsx` (qty, notes multiline in the app's Sheet with keyboard-aware scrolling — the Sheet already uses KeyboardAvoidingView; ensure the notes input scrolls into view, e.g. react-native-keyboard-aware-scroll-view which is installed; camera / gallery / file buttons; thumbnails; remove), create `src/components/plan/ProgressTimeline.tsx`; modify `src/components/plan/TaskSheet.tsx` (Log today's progress button; timeline; before save, if crew entries and `loggedToday` → show the exact message via the app's alert host and don't call; also map the server's same-day error to that message), `TaskCard.tsx` (latest log date). Images resized/compressed (≤1600 px). Tests: `__tests__/progress-test.ts`.
- [ ] Failing jest: loggedToday logic; payload; message text exact; upload call shape → implement → jest related + full `npm test` + `npx tsc --noEmit` → commit (no push). Report must say a new APK build is needed for the native modules.
