# Supervisors and Casual Labourers as people profiles; Pay Runs page removed

Date: 2026-11-27. Branch `mutara`. Approved by the user in conversation ("yes go ahead build it").

## Why
The Supervisors and Casual Labourers pages are card grids. The user wants them like SCP's Personnel pages
(Scouts / Sprayers, `~/stive/code/frappe15/apps/upande_scp/frontend/src/pages/Scouts.tsx`, `Sprayers.tsx`,
`components/people/*`) and Livestock's Animals page (`~/stive/code/frappe15/apps/upande_livestock/frontend/src/pages/Animals.tsx`):
a roster on the left, the picked person's record on the right, benchmarked against the farm, with Compare.

## Design
Layout: roster (search, avatar, name, one status line) at `xl:grid-cols-[minmax(0,300px)_minmax(0,1fr)]`; record on
the right: "Against the farm median" table, score radar (outward is better), flags, "where they worked" share bars,
week-by-week strip, Compare dialog (two people side by side). Date range defaults to the last four weeks. Same crop
(section) scoping and role exposure as today's pages.

**Supervisors** — roster: name, section, blocks/activities this week, Overseer tag. Numbers: tasks assigned, % done on
time, % postponed or late, progress logs per active day, labour sent back, average days from labour recorded to
Checked. Flags: overdue tasks, labour waiting on their check, open task with no progress log for 3+ days. Where:
share of work per block. Weekly: tasks done, logs.

**Casual Labourers** — roster: name, supervisor, last day worked. Numbers: days worked, tasks, output per day
(compared within the same activity), % of work sent back. Flags: sent-back work not yet fixed, absent 14+ days.
Where: per block and per activity. Weekly: days, output. No pay amounts.

**Pay Runs**: the desk page and its menu entry go (one menu serves every section). Labour approval is unchanged.

## Left to the builder
Exact KPI formulas from the data we hold (Work Plan Task, Casual Labour Work, Task Progress Log, Production Supervisor
Assignment), one server endpoint per page, reuse or port of SCP's KpiRadar / CompareDialog / avatar components.
