# Labour pay in production, and Work Management as a jigsaw piece

Date: 2026-11-16. Branches: upande_production `mutara-labour-pay` (from `mutara`); ghost-mann/upande_work_management `mutara` (from `master`).

## Goal
Production holds the labour basics on its own. When the `work_management` app (WM) is installed, production
detects it and drives WM's full chain, so WM's controls and payroll are an added layer, not a second system.
Every value that was hard-coded is keyed in on a settings page.

## Two modes
`Production Settings.labour_mode`: **Automatic** (default: use WM when installed) or **Built-in only**.
`labour.wm_active()` = WM in installed apps AND mode is Automatic.

### Built-in (no WM)
1. **Settings — "Labour & Pay" section** (the place to key in values): pay_period (Weekly/Fortnightly/Monthly),
   pay_week_starts_on (weekday), pay_day (weekday), daily_wage (Currency), duplicate_rule (Block/Warn/Off),
   multiple_jobs_per_day (Allow/Warn/Block), attendance_required (Check), attendance_source
   (Production/HRMS Attendance/Both), max_backdate_days (Int, 0 = no limit), pay_reference_prefix (Data).
2. **Rate periods — `Field Operation Rate`**: operation, valid_from, valid_to (blank = open), rate, daily_target, note.
   No overlapping periods per operation. `rate_on(operation, date)`: the period's rate; if the period has no rate
   but a daily target, `daily_wage / daily_target`; else the operation's `default_rate`. Casual Labour Work takes
   its rate from its `work_date` and records `rate_source`. Work already in a pay run never changes rate.
3. **Attendance — `Casual Labour Attendance`**: employee, date, status (Present/Half Day/Absent/On Leave/Off),
   note; one per employee per day. Bulk marking for a crew/day. When attendance_required: work on a day not
   Present/Half Day is blocked; source HRMS reads submitted `Attendance` (if HRMS installed), Both = either.
4. **Duplicate guard**: same employee + work_date + operation + unit (non-cancelled) → duplicate_rule.
   Different jobs the same day → multiple_jobs_per_day. Future dates refused; older than max_backdate_days refused.
5. **Pay run — `Casual Labour Pay Run`** (submittable): company, farm (optional), from_date, to_date, status
   (Draft/Approved/Paid/Cancelled), lines (`Casual Labour Pay Run Line`: employee, employee_name, days, entries,
   amount), totals, payment_reference, paid_on. "Get work" pulls Approved, unpaid work not in another run;
   submit = Approved (locks the work: `Casual Labour Work.pay_run`); "Mark paid" stamps paid/paid_on/
   payroll_reference on every work row; cancel releases. CSV export of lines. Only pay roles.

### With WM (Automatic and installed)
Production stays the screen people use; WM records mirror it and WM's approvals/attendance/payroll run on them.
- **Mapping**: Production Unit.warehouse → WM block (Warehouse); Field Operation.`wm_task` (Link Task, created
  on demand under the farm's WM project from WM Settings' farm rows); Employee is shared.
- **Plan task → WM Planner** (farm, week from/to, block, task, uom, daily target, rate, quantity).
  Name kept in `Work Plan Task.wm_planner` (Data — WM doctypes may not exist, so no Link fields to them).
- **Crew → WM Assigner** on first tick-off for that task (needs the planner approved in WM; otherwise the
  tick-off is refused with "waiting for Work Management approval of <planner>"). `wm_assigner` kept on the task.
- **Ticked-off work → WM Actuals rows** (one Actuals per assignment; one row per person-day). The work row keeps
  `wm_actuals`. Production's own approval step is skipped in this mode; WM's chain decides, and its outcome is
  synced back (doc_events on WM doctypes: approved → Casual Labour Work Approved/submitted; returned → Sent Back).
- **Pay**: built-in pay run hidden; WM payment/Additional Salary/Salary Slip status synced back to
  paid/paid_on/payroll_reference.
- doc_events for WM doctypes in production's hooks are harmless when WM is absent.

## WM `mutara` branch — make Kaitet values settings
- `payroll_pack.TASK_PAY_COMPANY` → Settings `payroll_pack_company` (blank = default_company).
- `rates.LEGACY_DAILY_WAGE`/`KNOWN_DAILY_WAGES` and the 340 fallbacks in api/actuals.py → Settings
  `current_daily_wage` (exists) + new `known_daily_wages` (comma list); no literal wage left in code.
- Literal `'Task Worker'` clauses → Settings `default_worker_employment_type` (default "Task Worker").
- Leave `seed/kaitet.py` (run by hand on Kaitet only). Keep `Employee.custom_farm` identical to upande_kaitet's.
- Tests adjusted; the generated API files are edited on this branch (note for ghost-mann: mirror must follow).

## Rules
No Claude attribution in commits. Never touch MariaDB directly. Backup before migrate; `flock .migrate.lock`;
restart only frappe16-mutara-* supervisor groups.
