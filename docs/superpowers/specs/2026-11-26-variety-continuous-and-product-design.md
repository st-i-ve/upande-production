# Production Variety: continuous harvest and product (design note)

User decisions, 2026-11-26: "one cycle till removal, and yes remove product".

## A. Continuous harvest is one cycle until removal

- `harvest_pattern` keeps its options: Once, Continuous, Interval.
- A Continuous variety does not use `harvest_window_days`, `harvest_window_weeks` or `harvest_interval_weeks`.
  The variety form hides them (`depends_on`), the desk dialog and panel hide them, and saving a Continuous variety
  clears them so a stale value never leaks into a cycle.
- A Continuous cycle's `expected_harvest_start` is worked out as today (first harvest). Its `expected_harvest_end`
  stays empty (open) unless the variety has `lifespan_years`, in which case it is the cycle start plus the lifespan.
  Every place that set the end from the window (`cycle_chain._sync_expected_harvest`, `cycle_chain.propose_next`,
  `stages.apply_variety_defaults`) goes through one helper in `stages.py`.
- Only Interval proposes a next cycle. `cycle_chain.cycle_number` and `propose_next` treat Continuous like Once.
  A closed Continuous cycle whose lifespan is reached is still marked `due_for_uprooting`.
- Forecast and calendar: a Continuous cycle harvests every week from `expected_harvest_start` until it is closed or
  its lifespan ends; with an open end that is up to the horizon. In the pick schedule
  (`schedule.harvest_context`) a Continuous variety therefore reports a one-week pick interval, so the pre-harvest
  interval rules stay in force for as long as the cycle runs. The Cycles page already counts an open-ended,
  unclosed cycle as running.

## B. Production Variety no longer has a Product

- The product of a variety comes from its sub-crop (`Production Sub Crop.product`), else its field crop
  (`Production Field Crop.product`). One helper, `field_crops.product_of_variety(variety) -> str | None`, answers it.
- A pre-model-sync patch copies each variety's old product into its sub-crop (when the variety has one) or its field
  crop, only where that target has no product. A different existing product is never overwritten; the conflict is
  logged. Changes are logged.
- Callers move to the helper or to the field crop / sub-crop product: `api/varieties.py`, `api/flowers.py`,
  `logic/field_crops.py` (finding a field crop by item), `logic/stages.py` (protocol fallback, `product_item`),
  the Margin Par setup, the demo seeds, the desk (no Product picker; the field crop's product is shown read-only).
- Older patches that read the column (`crop_hierarchy`, `add_field_crops` via `create_from_varieties`) are guarded
  with `frappe.db.has_column` so a fresh install does not break.
