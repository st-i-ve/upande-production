# Establishment costs, week-based protocols, flowering cycles and break-even

Date: 2026-10-28. Builds on `2026-10-29-varieties-stages-rules-design.md` (varieties, stages,
activity rules) and the earlier specs in this folder; their working rules apply (Sonnet builders,
Opus review, desk app on the SCP design, crop-scoped routes, no Co-Authored-By trailer).

## Intent (user)

- Know what it cost to **set up a block** before planting (capital / land preparation), so that one
  day we can make sure the block **breaks even**. Break-even is worked out **per block** and **per
  crop per farm**.
- A crop protocol is built from the **variety** as a template and holds three lists of activities:
  **capital**, **key (critical checkpoint)** and **cultural**. Planting and harvesting are the two
  end points; some crops also end with uprooting / clearing.
- Key activities happen in a **specific week** (e.g. bending in week 7). Cultural activities are
  either **every N weeks** or **as needed**, and have buffer periods: e.g. spraying must not start
  until 2 weeks after harvest and must stop 3 weeks before harvest.
- Flowering crops: time to first flowering, and for crops harvested more than once, time to
  **re-flower after harvest**. Harvest interval per variety. Recorded cycles must match the protocol;
  when they don't, the **manager is flagged** (nobody is blocked).
- Dry matter testing is switched on per crop, on the fruit or the tuber.
- Every production activity has a **colour**; the map shows which activity a block is going through.

## Decisions (user)

- Capital costs are **desk only**: per block, per capital activity, the cash spent.
- Capital activities (seed list, editable): Bush clearing, Single ripping, Cross ripping, Disc
  harrowing, Marking of ridges, Ridge-line ripping, Ridging, Fertiliser application (basal),
  Irrigation system installation, Windbreak planting.
- Field activities (seed list, editable): Planting, Harvesting, Uprooting / clearing, Mulching,
  Seedling support (staking), Irrigating, Fertigating, Fertiliser application, Drenching, Weeding,
  Soil management, Pest management, Dry matter testing, Gap filling, Bending.
- Use the word **variety** for plants (breeds/strains stay as varieties of the fish crop).
- Key activities: a **week number** column, not before/after harvest. Rows listed in week order;
  the table carries a description telling the user to list them by week.
- Cultural activities: an **Interval / As needed** column and an **interval weeks** column that is
  empty for As needed. Two buffer columns with their agricultural names (below).
- A cycle out of line with the protocol is **flagged to the manager only**.
- **Blocks planted before the system get an opening balance**: a one-off historical setup cost and
  value recovered to date. Break-even continues from there.
- **Each key activity row has a `repeats` column**: `First cycle only` (e.g. planting, gap filling)
  or `Every cycle` (e.g. bending). For later cycles of a repeat crop, Every-cycle rows count from
  that cycle's start.
- **PHI is entered in days**, as chemical labels give it, and is checked before every pick, so for
  continuous crops spraying fits between picks. The establishment period stays in weeks.
- Break-even per block and per crop per farm.

## Calls made by me (check these)

1. **Buffer columns** on cultural activities:
   - **Establishment period (weeks)** — earliest start, counted from planting for the first cycle,
     and from the end of the previous harvest for later cycles of a repeat-harvest crop (the
     "post-harvest interval"). This is the user's "planting buffer".
   - **Pre-harvest interval, PHI (days)** — the activity must stop this many days before the
     expected harvest start and, once harvesting has begun, before every next expected pick
     (last pick + harvest interval). This is the user's "harvest buffer". Units are the user's
     decision.
   - Enforcement (user's decision): **both buffers Warn, never Block**. The agronomist makes the
     call: a reason is required and the breach is flagged in Approvals. Both reuse the rule engine
     and its UI.
2. **Week numbers count from the cycle start**: planting for the first cycle, end of the previous
   harvest for later cycles of a repeat crop. Week 1 = the first 7 days.
3. Extra items the user did not list but agreed are worth having (from the playback): **Planting
   material** (seedlings / seed tubers) as a capital activity; **shared capital costs** split across
   several blocks **by area**; gap filling records the **number of plants replaced**; dry matter has
   a **target %** per crop/variety that marks a block ready to pick; a **removal / uprooting cost**
   at end of life counts against the same break-even.
4. **Weeks from flowering to harvest** is a variety field, so first harvest = planting + weeks to
   first flowering + weeks flowering → harvest (not typed twice). For non-flowering crops the user
   types weeks to first harvest directly.
5. Capital costs are a **record**, not a GL posting (the user said desk only, "how much cash was
   spent"). If finance also books the same spend as an expense on the block's cost centre it would
   be counted twice in break-even; the break-even page excludes GL entries flagged as capital (see
   Break-even) and the builder documents this in Settings help text.
6. Dry matter tests are entered on the **desk** (and exposed in the mobile API for later); no new
   mobile screen in this round.
7. Break-even covers **every crop whose harvests write Production Harvest**: avocado and F&V crate
   batches, honey harvests and fish harvests all do already. **Recovered** = Production Harvest
   value (the builder makes sure every path fills `value`: qty × the item's valuation rate, else the
   latest buyer price, as `harvest.py` already prices the receipt). GL entries of **Harvesting**
   stock entries are excluded from running costs, so the harvest isn't counted twice.
8. **The variety stages stay the one timeline.** The new variety week fields generate or check the
   stages. Expected flowering is the Flowering stage start, and expected harvest start is the
   harvest stage start (`stages.harvest_start`, which the rule engine already uses).
   `actual_flowering_date` / `actual_harvest_start` on the cycle are written as stage actuals, so
   one record shifts the later stages. **Key-activity weeks count from the cycle start and don't
   move when flowering is late.** `anchor_stage` on old steps converts to a fixed week using the
   variety's planned stage start. Existing avocado season cycles get `cycle_no` in the order of
   their `previous_cycle` chain (no chain → 1). Their start date is unchanged.
9. **Break-even is shown only to users who can see pay** (it includes labour pay, so any figure
   reveals it). Other users don't see the page.

## Data model

### Production Operation (existing — shown in the UI as "Production Activity")
- `activity_type` Select: `Capital` / `Planting` / `Key activity` / `Cultural` / `Harvesting` /
  `Uprooting` (default Cultural). `is_harvest` stays and is set for Harvesting.
- `color` Color (reqd for map use; seed gives each a distinct colour from the app palette).
- Existing `category` (Spraying/Weeding/…) stays — the rule engine uses it.
- Seed the two lists above per crop (avocado, F&V; apiary / aquaculture get their own sensible
  capital lists: e.g. pond excavation, liner, inlet/outlet; hive stands, hives).

### Production Crop (existing)
- `dry_matter_testing` Check; `dry_matter_on` Select `Fruit` / `Tuber` (depends on the check);
  `dry_matter_target_pct` Float (default; a variety may override).

### Production Variety (existing — the protocol template)
- `lifespan_years` Float (perennials; empty = one cycle).
- `harvest_pattern` Select `Once` / `Continuous` / `Interval`; `harvest_interval_weeks` Int
  (shown unless Once — e.g. passion fruit 1–2, avocado ~52).
- `is_flowering` Check; when ticked: `weeks_to_first_flowering` Int, `weeks_flowering_to_harvest`
  Int, and — only when `harvest_pattern` ≠ Once — `weeks_to_reflower_after_harvest` Int.
- `weeks_to_first_harvest` Int (typed for non-flowering; computed and read-only for flowering);
  `harvest_window_weeks` Int.
- `plants_per_m2` Float (primary; feeds the forecast). Existing `plants_per_ha`,
  `days_to_first_harvest`, `harvest_window_days` become **derived** (×10 000, ×7) so current code
  keeps working; a patch fills the new week/m² fields from the existing values.
- `dry_matter_target_pct` Float (optional override of the crop's).
- `stages` (existing) unchanged.

### Production Protocol (existing) — three tables replace `steps`
- `capital_activities` Table **Production Protocol Capital Activity**: `operation` (Capital type),
  `description` Small Text, `budget_per_ha` Currency (optional, for planned vs actual).
- `key_activities` Table **Production Protocol Key Activity**: `operation`, `week` Int (reqd, ≥ 1),
  `repeats` Select `First cycle only` / `Every cycle` (default Every cycle; the patch sets Planting
  and Gap filling to First cycle only), `planned_qty` Float, `description` Small Text. Table description: *"List key activities in the
  order of their week."* On save the rows are validated (a row with a lower week after a higher one
  is a validation error naming the rows; no silent re-sort).
- `cultural_activities` Table **Production Protocol Cultural Activity**: `operation`,
  `schedule` Select `Interval` / `As needed` (reqd), `interval_weeks` Int (reqd for Interval, must be
  empty for As needed), `establishment_period_weeks` Int, `pre_harvest_interval_days` Int,
  `planned_qty` Float, `description` Small Text.
- Header fields copied from the variety when the variety is chosen (template): lifespan, harvest
  pattern/interval, flowering weeks, plants per m², dry matter target — shown read-only on the
  protocol with a link to the variety (the variety stays the source of truth).
- Existing `steps` table: kept hidden for history; a **patch** converts every protocol's steps:
  a step with `repeat_every_days` → Cultural Interval (`interval_weeks` = round(days/7), at least 1;
  establishment = week of its first `day_offset`); otherwise → Key activity
  (`week` = day_offset // 7 + 1); `anchor_stage` steps convert relative to that stage's start week.
  Protocol versioning/approval (Draft → Pending → Active) is unchanged; the converted protocols keep
  their status.

### Block Establishment Cost (new, module Production, submittable, desk only)
- `crop` Link Production Crop (reqd), `farm` Link Farm, `posting_date` Date (reqd),
  `operation` Link Production Operation (Capital or Uprooting type, reqd), `amount` Currency (reqd),
  `supplier` Link Supplier (optional) / `paid_to` Data, `reference` Data (invoice/receipt no.),
  `note` Small Text, attachments allowed.
- `blocks` Table **Block Establishment Cost Split**: `unit` Link Production Unit, `area_ha` Float
  (fetched), `share_pct` Float, `amount` Currency. Split method Select `By area` (default) /
  `Manual`. One row = the whole amount on one block. Shares must total 100 %.
- Group units may be chosen (the cost is split over its leaf blocks by area).

### Block Opening Balance (new, one per block)
- `unit` Link Production Unit (unique), `crop`, `as_of_date` Date (reqd), `setup_cost` Currency,
  `running_costs_to_date` Currency, `value_recovered_to_date` Currency, `planted_on` Date, `note`.
  Break-even adds these figures, then counts system records only after `as_of_date`.

### Production Crop Cycle (existing)
- `expected_flowering_date` Date, `actual_flowering_date` Date, `actual_harvest_start` Date,
  `actual_harvest_end` Date, `cycle_no` Int (1 = from planting).
- `protocol_flags` Small Text (read-only, computed), `flag_count` Int.

### Dry Matter Test (new)
- `unit`, `cycle`, `crop`, `variety` (fetched), `test_date`, `tested_on` (Fruit / Tuber, from the
  crop), `samples` Table (`sample_no`, `dry_matter_pct`), `avg_pct` (computed), `target_pct`
  (fetched), `ready` Check (avg ≥ target), `tested_by`.

### Production Settings
- `cycle_flag_tolerance_weeks` Int (default 2).

## Behaviour

- **Weekly plan generation** (`production/logic/plans.py`, used by desk and mobile) reads the new
  tables: a key activity is due in the plan week that contains cycle start + (week − 1) × 7 days;
  an Interval cultural activity is due every `interval_weeks` from the end of its establishment
  period, and is **not generated** inside the PHI (days) before the expected harvest start or the next expected pick;
  a key activity marked First cycle only is generated only in cycle 1;
  As-needed activities are never generated (supervisors add them). Capital activities are never
  generated.
- **Buffers are enforced by the rule engine** (`rules.check`): protocol cultural rows become
  implicit rules for that cycle — Not before establishment period (Warn) and Not within PHI days
  before harvest — both Warn (the agronomist decides). They apply to add task, tick-off/record work, approvals and protocol
  check, desk and mobile, exactly like Production Activity Rules (same breach payload).
- **Cycle chain** for repeat-harvest varieties: cycle 1 starts at planting; expected flowering =
  start + weeks to first flowering; expected harvest start = flowering + weeks flowering → harvest
  (or start + weeks to first harvest). When a cycle is Closed (its harvest end recorded), the
  system **proposes** the next cycle (status Planned, `previous_cycle` set, `cycle_no` + 1) starting
  at the harvest end, expected flowering = start + weeks to re-flower, harvest = flowering + weeks
  flowering → harvest, same protocol family's Active version. A recorded actual date shifts the
  later expected dates (as stage actuals do today). Lifespan reached → no proposal; the block shows
  "due for uprooting".
- **Protocol flags (manager only)**: on save and nightly, compare each Active/Harvesting cycle's
  actual flowering / harvest start / harvest end with expected; a difference over the tolerance, or
  an expected date passed with no actual recorded, adds a flag ("Block A flowered 3 weeks late",
  "Block C harvest due 2 weeks ago, nothing recorded"). Flags show on Overview ("Off protocol"
  card), Cycles (badge per cycle) and the Blocks page. Never blocks anyone.
- **Gap filling**: recording work for the Gap filling activity takes qty in **Plants**; the block
  shows plants replaced to date; plant count is unchanged.
- **Dry matter**: a test below target shows amber, at/above target green with "ready to pick"; the
  latest result shows on Blocks, the Map popup and the Forecast block rows.
- **Map colours**: the Coverage Map can colour each block by the **activity it is going through**
  (the activity of the most recent approved/pending work or in-progress task in the selected week;
  ties → the latest), with a legend of activity colours. Activity colours also tag rows on the
  Plan and Approvals.
- **Break-even** (new logic `production/logic/breakeven.py`, page "Break-even" per crop):
  - Per block: **invested** = establishment costs (its share) + running costs since the first
    establishment cost (approved labour pay + GL expense on its cost centre, excluding entries of
    an account marked capital in Production Settings `capital_accounts`) + uprooting cost;
    **recovered** = sum of Production Harvest value; balance; % recovered; **break-even date**
    (the date cumulative value first ≥ cumulative cost) or, if not yet, a **projected** date from
    the forecast (expected harvest kg × price) or, without a forecast, from the trailing 12-month
    net margin; years to break-even.
  - Per crop per farm: the same summed over the farm's blocks of that crop, plus a cumulative
    cost-vs-value chart over time with the crossing point.
  - Pay figures stay hidden from users who cannot see pay (existing `_pay` rule).

## UI (desk app; SCP design)

- **Settings → Activities**: the activity list with type, category and colour picker.
- **Settings → Varieties**: the template fields above with the show/hide rules (flowering fields
  only when flowering; re-flower and interval only when harvested more than once).
- **Protocols**: three sections (Capital, Key activities by week, Cultural with Interval/As needed,
  interval weeks, establishment period weeks, PHI days), and the key-activity table has a Repeats column. Column headers use the agricultural names with a
  short hint ("weeks after planting / last harvest", "days before harvest").
- **Establishment costs**: a page per crop (with an Opening balance tab for old blocks) to list/add costs (block picker incl. multi-block split
  by area), totals per block and per activity, budget vs actual where a budget is set.
- **Break-even**: page per crop (block table + farm summary + cumulative chart).
- **Cycles**: expected vs actual flowering / harvest markers on the Gantt, flags, "propose next
  cycle" result, cycle number.
- **Overview**: "Off protocol" card; **Blocks**: dry matter, plants replaced, flags.
- **Coverage Map**: "Colour by activity" mode with legend.
- Frappe desk forms for the new doctypes exist but the manager works in the app.

## Mobile

No new screens. Generation and buffers flow through the existing supervisor endpoints (week plan,
add task, tick-off, protocol check) and their breach handling. `SUPERVISOR_API.md` documents the
new buffer breach messages and a `dryMatterTests` read endpoint.

## Demo data

Extend the seed config: activity types/colours, capital lists per crop, establishment costs for
every demo block (realistic KES per ha, incl. one shared irrigation install split across blocks),
variety template fields (Hass/Fuerte flowering, interval harvest, re-flower weeks; passion fruit
continuous; potatoes/onion/cabbage once), converted protocols with key/cultural rows and buffers,
dry matter tests for avocado blocks, and actual flowering dates that produce at least one flag.

## Tests

Backend: patch conversion, generation from the three tables, buffer enforcement (Block/Warn), cycle
chain proposal, flags with tolerance, establishment cost split, break-even (actual and projected
dates, capital-account exclusion, pay hidden). Desk vitest for the new pages and show/hide rules.

## Addendum 2026-10-29: maturity, flowering patterns, block cost centre, harvest store, ERP budget

### Decisions (user)
- **Everything done on a block is costed to its cost centre**: fertiliser, chemicals and other inputs
  issued against the block (SCP's chemical plan already issues stock with the cost centre named like
  the block's warehouse). The block's cost view is where the manager finds out what is happening on
  a block and whether it is working.
- **Labour = casual Value Adders' pay figures only** (recorded per worker). Payroll is a different
  system and never enters here; no GL for labour.
- **Users pick the store** when a harvest batch closes; the stock entry keeps the block's cost centre.
- **Blocks have ERP budgets** (ERPNext Budget on the block's cost centre).
- **Maturity per variety**: the week the plant is mature for its first official harvest (avocado
  2–3 years, passion fruit some months).
- **Flowering**: the user asked for a perspective; agreed design below.

### Calls made by me (check these)
1. **Flowering pattern** on the variety (shown when flowering): `Seasonal` or `Interval`.
   - Seasonal (avocado): table **flowering seasons** — season name (Main / Off-season), start month,
     weeks flowering → harvest, share of the season's crop %. Expected flowering of a cycle = the 1st
     of its season's start month. The first season of a block = the first season start on/after
     planting + weeks to maturity. Each season is one cycle; closing it proposes the next season (by
     calendar) as the next cycle.
   - Interval (passion fruit): weeks to first flowering (from planting), **flowering interval
     (weeks)**, weeks flowering → harvest. Next cycle's flowering = previous flowering + interval.
   - Replaces `weeks_to_reflower_after_harvest` (kept hidden; a patch moves values across).
2. **Juvenile**: cycles whose expected harvest falls before planting + weeks to maturity are marked
   juvenile: no yield expected in forecasts and break-even projection; their key/cultural activities
   still plan.
3. **Flags for seasonal varieties** compare actual flowering with the season start (tolerance as
   before). This removes the "first flowering-anchored cycle is never checked" exception for them.
4. **Block ↔ warehouse**: Production Unit gains `warehouse` (the block's warehouse, as SCP uses).
   A **block links check** (Settings and Blocks) lists every leaf block whose cost centre is missing,
   whose warehouse is missing, or whose warehouse name ≠ cost centre name (SCP's chemical plan would
   then charge a different cost centre).
5. **Harvest store**: Harvest Batch `warehouse` is chosen by the user (desk and the mobile "mark
   ready" step); default = the last store used for that farm, else Production Settings'
   harvest warehouse. Stores offered = non-group warehouses of the company that aren't block
   warehouses.
6. **ERP budget**: block budget = sum of the submitted ERPNext Budget account amounts against the
   block's cost centre for the current fiscal year. Setup Costs shows it against setup + running
   spend for that year; the protocol's `budget_per_ha` stays as a fallback when no ERP budget exists.
7. **Block cost breakdown** (the "what is happening on this block" view, in Block Costs per block):
   labour by activity (pay, qty, workers), inputs by item (Stock Entry issues on the cost centre:
   item, qty, UOM, amount, per ha — e.g. fertiliser kg/ha), other expenses by account, each over the
   chosen period, plus budget vs actual. Planned protocol quantities are shown next to actual input
   quantities where the operation's item is known (else omitted).
