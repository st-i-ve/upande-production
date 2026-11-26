# Capital costs move from the protocol to the block (server side)

Decision (2026-11-26): "remove the capital cost from the protocol, link it to the block based on the
cycle that is running on a block". Capital budgets live on the block.

## 1. Protocols hold no capital
- `Production Protocol.capital_activities` (table of Production Protocol Capital Activity) is removed.
  A protocol holds only key and cultural activities.
- `validate_tables` refuses any capital rows; `logic/protocols.py` (template, copy, new version, diff,
  save_draft) and `api.list_protocols` no longer carry the table. Capital-type operations are still
  refused inside key and cultural rows.
- The `Production Protocol Capital Activity` doctype and its stored rows stay (history, and the patch
  reads them). Nothing is deleted.
- `convert_protocol_steps`: steps whose operation is Capital are no longer written anywhere (they used
  to become capital rows); it must not touch a field that no longer exists.
- Demo seed: capital budgets are written to the crop's blocks instead of the protocol.

## 2. Block capital budget
New child doctype **Production Unit Capital Budget**, table `capital_budget` on Production Unit:
`operation` (Link Field Operation, Capital activity_type only), `basis` (Per ha / Total), `amount`
(Currency), `note` (Small Text). Only a block (non-group) may carry rows; an operation appears once.
Effective budget per operation = `amount x unit area_ha` when Per ha, else `amount`.

## 3. Establishment cost belongs to a cycle
`Block Establishment Cost Split` gains `cycle` (Link Production Crop Cycle, read only), set on validate
to the cycle running on that unit on the parent's `posting_date`: status Active, Harvesting or Closed,
`start_date <= date` and (not Closed, or `closed_on` / `actual_harvest_end` >= date). With several the
newest `start_date` wins; none gives an empty cycle.

## 4. Patch `capital_costs_to_blocks` (post_model_sync)
Runs after model sync because it writes the new child table and the new `cycle` column; the old table
is not dropped by a sync, so it is still readable. For each Active protocol's capital rows it writes a
Per ha budget row on every non-group, non-retired unit of that protocol's crop (when the protocol has a
field crop or variety, only units running a cycle on that protocol or variety), skipping operations the
unit already budgets, and prints what it did. Then it fills `cycle` on existing split rows by rule 3.

## 5. Logic and API
- `logic/establishment.capital_activities(crop)` and the per-unit summary read block budgets, no
  protocol lookup. Summaries also give spend per cycle (unit -> cycle -> operation amounts).
- `api/establishment`: existing names kept; added `get_unit_capital_budget(unit)`,
  `save_unit_capital_budget(unit, rows)` (managers) and `cycle_capital_costs(cycle)`.
