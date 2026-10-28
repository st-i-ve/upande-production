# Varieties, growth stages and activity rules

Date: 2026-10-29. Follows the other specs in this folder (approvals, protocol versions, crop logs,
harvesting, mobile supervisor). Their working rules apply.

## Intent (user)

Crops have different varieties/breeds; each variety has its own protocol, which leads to different
crop cycles. Each crop goes through growth stages, and stages restrict activities — e.g. weeding
can't happen in a given stage/week, spraying must not happen in the 2–3 weeks before harvest.
These must be in place across planning and recording, desk and mobile.

## Decisions

- Hierarchy: **Crop → product → variety**. A variety is its own **stock Item** (so the Harvesting
  stock entry, costs and yields are per variety). Avocado: Hass, Fuerte. F&V: per product.
  Aquaculture: strains on Pond Stocking. Apiary: no cycles (unchanged).
- A breach of a stage rule is handled **per rule**: `Block` (refused) or `Warn` (allowed with a
  reason, flagged to the manager in Approvals).
- **Seed realistic demo data** (Kenyan varieties, stage lengths, rules) in one config dict, swappable
  later. Examples: potatoes Shangi / Dutch Robjin / Markies; cabbage Gloria F1 / Copenhagen Market;
  onion Red Creole / Red Pinoy F1; passion fruit Purple / Sweet Yellow; avocado Hass / Fuerte;
  tilapia GIFT / Nile (local).

## Data model (exact — both backend builders code against these names)

### Production Variety (new, module Production, autoname `field:variety_name`)
- `variety_name` Data (unique), `crop` Link Production Crop (reqd), `product` Link Item (the product,
  e.g. Potatoes) , `item` Link Item (reqd — the variety's own stock item, e.g. "Potatoes - Shangi";
  created by the seed when missing, under the product's item group, stock uom Kg),
- `days_to_first_harvest` Int, `harvest_window_days` Int, `expected_yield_per_ha` Float,
  `expected_yield_per_plant` Float, `plants_per_ha` Float, `default_protocol` Link Production Protocol,
  `stage_anchor` Select (Planting / Flowering / Stocking; default Planting),
- `stages` Table **Production Variety Stage**, `enabled` Check (default 1), `notes` Small Text.

### Production Variety Stage (child)
- `stage` Data (e.g. "Tuber initiation"), `start_day` Int (days from the anchor), `length_days` Int,
  `is_harvest` Check (the harvest stage), `description` Small Text. Ordered by `idx`.

### Production Activity Rule (new, autoname `PAR-.#####`)
- Scope (most specific wins; all that match apply): `crop` Link Production Crop (reqd),
  `variety` Link Production Variety (optional), `stage` Data (optional; must be a stage name of the
  variety/crop),
- `operation` Link Production Operation (optional) and/or `operation_category` Select
  (Spraying / Weeding / Fertilising / Irrigation / Harvesting / Pruning / Feeding / Other) — the rule
  applies to the operation or to every operation of that category,
- `rule_type` Select: `Not in stage` | `Only in stage` | `Not within days before harvest` |
  `Not within days after operation`,
- `days` Int (for the "within days" types), `other_operation` Link Production Operation /
  `other_category` Select (same options) for "after operation",
- `enforcement` Select `Block` | `Warn` (reqd), `reason` Small Text (shown to the user), `enabled` Check.
- Production Operation gains `category` Select (same options as `operation_category`).

### Changes to existing doctypes
- **Production Crop Cycle**: `variety` Link Production Variety; `current_stage` Data (read-only,
  computed); `stage_actuals` Table **Production Cycle Stage Actual** (`stage` Data, `actual_date`
  Date, `note` Small Text). `item` follows the variety's item. The cycle's protocol must belong to the
  same variety (or to the product with no variety) — otherwise refused. Expected harvest start/end
  default from the variety (days_to_first_harvest, harvest_window_days) when not set.
- **Production Protocol**: `variety` Link Production Variety (optional; product-level when empty).
  **Production Protocol Step**: `anchor_stage` Data (optional) — when set, `day_offset` counts from
  that stage's start instead of the cycle start.
- **Production Plan Task**: `rule_status` Select (OK / Warn / Block), `rule_notes` Small Text,
  `override_reason` Small Text. **Value Adder Work**: `rule_status`, `rule_notes`, `override_reason`
  (same names).
- **Pond Stocking**: `strain` Link Production Variety (crop Aquaculture) in addition to `species`;
  stages anchored on Stocking.

## Behaviour

- **Stage of a cycle on a date**: from the variety's stages and the anchor date (cycle start, or the
  stage actuals — a recorded actual stage date shifts that stage and the later ones by the same
  delta). `current_stage` refreshes on save and nightly.
- **Rule engine** (`production/logic/rules.py`): `check(cycle_or_unit, operation, on_date, other=None)`
  → list of breaches `{rule, rule_type, enforcement, message}`; "before harvest" uses the cycle's
  expected harvest start (or the harvest stage start); "after operation" looks at approved/pending
  work and planned tasks of the other operation on the same unit.
- **Enforced** in: plan generation from protocols (skip Block, mark Warn), add task (desk + mobile),
  tick-off / record work (Block refused; Warn needs `override_reason`), approvals (breaches shown on
  the card), protocol version approval (steps that would land in a forbidden stage/window for the
  variety are listed before the manager approves).
- **Protocol per variety**: when a cycle is created/changed, its protocol defaults to the variety's
  Active protocol (`default_protocol` family → its Active version), falling back to the product's.

## UI

- Desk app: Settings → Varieties (stages timeline editor) and Activity Rules; Crop Cycles shows
  variety + current stage (stage band on the Gantt); Blocks/Coverage Map show stage; filters by
  variety on Cycles, Forecast, Block Costs; Plan/Approvals show rule flags + override reasons;
  protocol check per block lists rule breaches.
- Mobile: stage chip on blocks/tasks; add task / tick-off show breaches (Block = can't save, Warn =
  reason required).

## Data fixes

Every existing cycle gets a variety and its variety's Active protocol (incl. the 12 F&V cycles with
none; Fuerte gets its own protocol); current stage computed; seeded rules include pre-harvest
intervals for spraying (avocado 21 d, potatoes 14 d, cabbage 14 d, onion 14 d, passion 7 d), no
weeding in bulking/tuber initiation for potatoes, no feeding 24 h before fish harvest.
