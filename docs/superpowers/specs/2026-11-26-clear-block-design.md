# Clear block

Date: 2026-11-26. Branch `mutara`. User: "yes build the clear block".

## Why
A block is uprooted or cleared and will be replanted. Today the only way to end its cycles in one go is retiring the
block (it disappears for good); closing cycles one by one can propose a next cycle for repeat crops.

## Design
- Action **Clear block** on a block (desk: Blocks page and the cycle panel menu). Inputs: date (not in the future,
  not before the earliest running cycle's start), reason (Select: Uprooted / Crop failed / Replanting / Other),
  note (required when Other).
- Effect (one transaction, `production/logic/clear_block.py` `clear_block(unit, on_date, reason, note=None)`):
  - Every Active/Harvesting cycle on the block → Closed, `actual_harvest_end` = on_date if empty, new cycle fields
    `closed_on` (Date), `close_reason` (Select as above), `close_note` (Small Text). No successor is proposed.
  - Planned cycles on the block: deleted when nothing is recorded against them (`recorded_in`), else Closed with the
    same reason.
  - Open / In Progress Work Plan Tasks on the block with due_date ≥ on_date → Skipped with note
    "Block cleared {date}: {reason}". Recorded work, harvests and logs stay.
  - Production Unit status → Fallow (new field `cleared_on`). Creating a new cycle on a Fallow block sets it back to
    Active.
  - Pending cycle change requests for those cycles → Rejected with note "Block cleared".
- Who: managers apply directly. Supervisors and assistant managers create a request; reuse Production Cycle Change
  Request with action **Clear block** (new action value; `cycle` = any running cycle of the block, payload
  {unit, on_date, reason, note}); approve runs clear_block. One pending clear request per block.
- Retired blocks can't be cleared; a block with no running or planned cycle can't be cleared ("Nothing to clear").
- Endpoints (api/cycle_setup.py, POST, @run): `clear_block(unit, on_date, reason, note=None)` → manager:
  `{"cleared": {...counts}}`, others: `{"request": name, "pending": true}`; `clear_block_preview(unit)` → what
  would close/delete/skip.
- Desk: dialog shows the preview (cycles to close, planned to remove, tasks to skip), then confirm; Approvals →
  Cycle changes shows Clear block requests.

## Rules
No Claude attribution. bench/ORM only; backup before migrate; flock .migrate.lock; restart only the mutara web group;
tests one module at a time; desk bundle in its own commit.
