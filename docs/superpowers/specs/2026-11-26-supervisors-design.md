# Supervisors: records, per-activity block supervisors (shared), people pages

Date: 2026-11-26. Branch `mutara`. Agreed with the user ("shared, go with your pick start development").

## Why
Every Employee shows in supervisor dropdowns; a block has one supervisor a week. The farm works with an overall
overseer per block (e.g. Jane on block 8) plus people in charge of an activity (crop protection: Ruth and Matthew;
mulching: X), falling back to the overseer. Supervisors need their own record and page, and the casual labourers page
should match the SCP Scouts page style. Each supervisor's casual labourers are the base for the later offline download.

## Goals
1. **Production Supervisor** doctype (one per Employee; name = employee id): employee (reqd, unique), employee_name,
   user (from Employee.user_id), image (from Employee), phone (cell_number), farm, crops (Table MultiSelect of
   Production Crop), active (Check, default 1), notes. Every supervisor dropdown in the production app — task supervisor,
   block assignment, casual labourer default supervisor, add-labourers dialog — lists only active Production
   Supervisors. Stored values stay Employee ids (no data migration). A patch creates a Production Supervisor for every
   Employee already used as a supervisor (assignments, plan tasks, casual labourers).
2. **Block assignment per week**: Production Supervisor Assignment gains `category` (Select, blank = overall
   overseer, else a Field Operation category). Per block and week: one overseer row (blank category) and any number of
   rows per category (shared). "Copy last week" copies all rows.
3. **Task routing**: a task's `supervisor` = the first listed supervisor for (block, its operation's category) that
   week, else the overseer; hand-set supervisors stay (today's supervisor_from_plan rule).
4. **Shared visibility**: a supervisor sees (phone "my tasks", my-blocks, plan lists) a task when task.supervisor is
   them, OR they are assigned to the task's block and category that week, OR no one is assigned to that category on
   that block and they are the overseer. Either sharer can tick off.
5. **Field Operation category** gains "Mulching". "Crop protection" = Spraying (label unchanged).
6. **Supervisors page** (desk) in the SCP Scouts page style (upande_scp/frontend/src/pages/Scouts.tsx): a card per
   supervisor with photo, name, phone, KPIs (blocks this week, tasks this week done/open/late, crew size, entries
   pending approval), and a detail view with their blocks/categories this week and their casual labourers.
7. **Casual Labourers page** restyled to the same card style (photo, KPIs from the current RosterView: days worked,
   hit rate, avg vs target, pay where allowed), keeping current filters, add/edit and roster actions.

## Non-goals
- Phone UI changes beyond what the server visibility gives (the phone already filters server-side).
- Offline download (next project).

## Approach (chosen)
Keep Employee as the stored link and add the Production Supervisor record as the registry the dropdowns query —
no migration of existing links, the phone's "my employee" logic unchanged. Pointing every field at the new doctype
was dropped: data conversion and phone changes for no visible gain.

## Left to the builder
Exact KPI layout and copy; where the "Supervisors" nav item sits (next to Casual Labourers).

## Rules
No Claude attribution. bench/ORM only; backup before migrate; flock .migrate.lock; restart only
frappe16-mutara-web:frappe16-mutara-frappe-web; tests one module at a time; desk bundle in its own commit. Custom DocPerm
on this site: make new perms effective (see patches/add_assistant_manager_perms.py). Never name a doctype "Crop".
