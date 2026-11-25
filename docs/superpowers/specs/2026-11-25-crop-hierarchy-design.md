# Crop hierarchy: farm sections, crop groups, crops, sub-crops, varieties

Date: 2026-11-25. App: upande_production, branch `mutara` (local site mutara.local first). This round lands on
`mutara` only; `main` (no Field Crop code there) and `marginpar` get it as a later port. The Field Crop commits are
already on `origin/mutara` but no site other than mutara.local has migrated them: keep the live deploy on hold.

## Why
The crop list is muddled. Today "Fruits & Vegetables" is a crop with Onion, Potato and the rest wedged under it as
"Field Crops", Avocado sits beside it at the same level, and flowers (Margin Par) live in a separate flat "Crop Type"
list. An agronomist cannot read it, varieties do not hang off a real crop, and there is nowhere proper for
roses (Standard / Spray), summer flowers or a future coffee or tea. We need one agronomically correct structure that
every client branch can use, without breaking what works: shared pivots, per-section pages, crop cycles, the phone.

## The model: three separate things

1. **Farm section** (what `Production Crop` is today, kept as is): a part of the farm with its own land, team, pages
   and access. Owns Production Units (blocks, pivots), its menu (Plan, Cycles, Irrigation, Grading…), colour, unit
   labels (Pivot / Block / Bed) and all of today's section settings. Examples: Avocado, Fruits & Vegetables (the
   pivot farm), Apiary, Aquaculture. On Margin Par later: the flower farm.
2. **Crop classification** (new): the agronomist's tree.
   **Crop Group** (nested, any depth, grouping only) → **Crop** (the species) → **Sub-crop** (optional) → **Variety**.
3. **Crop cycle** joins them: *where* (a unit, hence its section) and *what* (crop, sub-crop, variety).

The two are independent on purpose: passion fruit is a Fruit Crop agronomically but grows on the Fruits & Vegetables
pivots, rotating with onions and potatoes on the same land.

### The classification tree (standard groups, created on every site)

```
Floriculture
├─ Rose                         crop
│  ├─ Standard rose             sub-crop → varieties
│  └─ Spray rose                sub-crop → varieties
└─ Summer Flowers               group (not a crop: each flower has its own crop cycles)
   ├─ Gypsophila, Statice, …    crops → varieties
Fruit Crops
├─ Avocado                      crop → Hass, Fuerte
└─ Passion Fruit                crop → Purple, Sweet Yellow
Vegetable Crops
├─ Onion                        crop → Red Creole, Red Pinoy F1
├─ Potato                       crop → Shangi, Markies, Dutch Robjin
└─ Cabbage                      crop → Gloria F1, Copenhagen Market
Plantation Crops
└─ Coffee                       crop → SL28, Ruiru 11, Batian   (tea later)
Fodder Crops
└─ Maize                        crop → H513   (Napier, lucerne later)
```

Only the six groups (Floriculture, Summer Flowers, Fruit Crops, Vegetable Crops, Plantation Crops, Fodder Crops)
are created on every site. Crops are created per site from what the farm grows (Mutara: Avocado, Passion Fruit,
Onion, Potato, Cabbage, Maize). No Rose, flowers or Coffee on Mutara.

### Rules
- A **group** holds groups and/or crops. Nothing else: no settings, no cycles. Used for menus, filters, totals and
  (later) access.
- A **crop** is the species. It always sits directly in one group. It carries: group, scientific name (optional),
  product item, harvest unit (Kg, Pieces, Stems…), colour, enabled. Crop cycles, protocols, harvests and varieties
  point at a crop.
- A **sub-crop** is optional and divides one crop into kinds grown or sold differently (Standard / Spray rose). It
  can override the crop's product item and harvest unit; everything else comes from its crop.
- A **variety** belongs to exactly one crop, and to one sub-crop of that crop when the crop has sub-crops (then the
  sub-crop is required on the variety).
- Records that name a variety take crop and sub-crop from it; they may not disagree with it.

## Record types

| Doctype | Status | Fields |
|---|---|---|
| `Crop Group` | new, tree (NestedSet) | group_name (autoname), parent_crop_group, is_group (1 on every record, so any group can take sub-groups; crops are a separate doctype), sort_order, description |
| `Crop Species` | **rename of `Field Crop`** | crop_name (autoname), crop_group (Link Crop Group, reqd), scientific_name, product (Item), harvest_uom (UOM), color, enabled. Drop `production_crop` (a crop is not tied to one section; which sections use a crop comes from their varieties) |
| `Sub Crop` | new | sub_crop_name (autoname), crop (Link Crop Species, reqd), product (Item), harvest_uom (UOM), enabled |
| `Production Crop` | unchanged doctype, relabelled "Farm Section" in our UI | as today |
| `Production Variety` | changed | `field_crop` → `crop_species`; new `sub_crop`; `crop` (section) stays **required as today**: a variety belongs to one section and one crop, so every section-based picker, query and inherited section setting (dry matter, count sizes, grades) keeps working unchanged. A crop grown in two sections gets its variety records per section |

Naming: `Field Crop` was never deployed to any live site, so renaming it now costs only local data. "Field Crop" is
also the agronomist's name for cereals/pulses/forage and would read wrongly for roses. Never use "Crop Type" (exists
on Kaitet live) or "Crop" (ERPNext agriculture). `Crop Group`, `Crop Species`, `Sub Crop` are unused on the
Mutara, Margin Par and Kaitet benches (checked).

### Fields renamed on the records that carry the crop
`field_crop` → `crop_species` (and a new `sub_crop` beside it) on: Buyer Commitment, Crop Forecast, Harvest Batch,
Harvest Grading Log, Production Crop Cycle, Production Harvest, Production Protocol, Production Variety, Yield Sample.
`sub_crop` is fetched from the variety where there is one; on Production Protocol it is optional (a protocol can be
for the whole crop or for one sub-crop).

## What moves (migration, one patch, idempotent)
Runs on every site after `add_field_crops` (which stays in patches.txt so live gets the same history).

1. Create the six standard Crop Groups if missing.
2. `Field Crop` → `Crop Species` (doctype rename with its records), field renames above (rename_field, data kept).
3. Give each existing crop a group: Avocado/Passion Fruit → Fruit Crops; Onion/Potato/Cabbage → Vegetable Crops;
   Maize → Fodder Crops. Any other crop: from a small name map; unknown → left without group and listed in the patch
   log for a manager to set (crop_group reqd is enforced on save, not in the patch).
4. **Avocado becomes a crop too**: create Crop Species "Avocado" (Fruit Crops, product = the avocado item, unit Kg),
   set it on the Avocado varieties (Hass, Fuerte), protocols, cycles, harvests, forecasts, samples of the Avocado
   section. Same rule for any section whose varieties have no crop yet but which is clearly a single crop (only
   Avocado on Mutara). Apiary and Aquaculture are skipped.
5. Nothing is deleted. The "Fruits & Vegetables" section keeps its name, units and pages.

Live (mutara.fsn.frappe.cloud) never ran `add_field_crops`; on deploy both patches run in order and land directly in
the new structure. **Hold the live deploy of `mutara` until this is built.** Daniel's stray Production Crop "Onion" on
live (a section, wrongly made as a crop) is handled by hand after deploy: if nothing links to it, delete it; if
something does, move those records to the Fruits & Vegetables section with crop Onion, then delete. Ask the user
before deleting.

## When a section shows the crop
Replaces today's `has_field_crops(section)` switch (which keyed on `Field Crop.production_crop`).
- A section's crops = the distinct `crop_species` of its enabled varieties (`crops_of(section)`).
- **More than one crop** (Fruits & Vegetables): behaves as F&V does today with Field Crops: crop picker shown,
  crop required on cycles, per-crop totals, crop columns in the cycle upload template.
- **Exactly one crop** (Avocado): the crop is filled in silently from the variety (or the only crop) on every record
  and never shown or asked for; the Avocado pages do not change.
- **No crop** (Apiary, Aquaculture, a silage section whose varieties have no crop): no crop handling at all, as today.
- The same function serves backend validation (`require_on_cycle`, section checks, `stamp`, `forecast_by_crop`,
  upload template) and the bootstrap value the frontend's `hasFieldCrops()` reads (renamed `hasCrops()`).

## Screens

### Desk (frontend/)
- **Settings → Crops tab** (today's Field Crops panel) becomes the classification editor: the group tree on the
  left, crops of the selected group on the right, sub-crops inside a crop, add/edit/disable each. Managers edit,
  others read.
- **Crop pickers** everywhere a field crop is picked today (Add/New/Edit cycle, variety dialog, protocols, grading,
  forecast, commitments, samples): pick **crop**, then **sub-crop** when that crop has any, then variety. The crop
  list is grouped by Crop Group (option headers), and filtered to crops that have varieties or cycles in the
  current section when there are any, else all crops.
- **Totals**: wherever totals are split by crop today (CropTotals, manager report, forecast, grading, overview), add
  a group roll-up line per group (sum only when every crop in the group shares a unit; otherwise per unit). Sub-crop
  shown as "Rose · Spray rose" where present.
- Labels: "Field crop" → "Crop" everywhere. The Link to Production Crop is labelled **"Section"** (not "Crop") in the
  doctype JSONs too (about 24 doctypes, so ERPNext desk forms, list filters and reports agree), and in the desk and
  phone; only "Crop" means the species.
- The Crops tab variety dialog asks for section as well as crop (variety keeps its section).

### Phone (upande-production, branch `mutara`)
- Rename the `field_crop` keys it reads to `crop_species`, show "Crop · Sub-crop · Variety" on plan tasks and
  harvest, harvest unit from sub-crop else crop. Unpushed commit fe2b9b9 is reworked, not shipped as is.

## Goals
- One agronomically correct tree, the same on every client branch.
- Shared land keeps working: a unit belongs to a section; any crop can be grown on it in turn.
- Every variety maps to crop (and sub-crop); reports total by crop and by group.
- Existing local data moves without loss; live gets it on its next deploy with no manual data step except Daniel's
  stray "Onion".

## Non-goals (this round)
- Animal production (Apiary, Aquaculture): untouched, stays as sections with no classification.
- Moving section settings (dry matter, crates, grades, count sizes, picker rates…) down to the crop. They stay on
  the section. A later round can move species-specific ones.
- Access by group (e.g. a manager for all Vegetable Crops). Access stays by section, as today.
- Porting Margin Par's flowers (`Crop Type` on branch `marginpar`) onto this model. The target mapping is written
  below; doing it is a separate job on that branch.
- Renaming the "Fruits & Vegetables" section (e.g. to "Pivot Farm"). Possible later as a label/rename; not needed.

## Anti-goals (would be a failure even if it works)
- A unit (pivot/block) tied to one crop, so onions and potatoes can no longer rotate on the same pivot.
- A "Summer Flowers" or "Fruits & Vegetables" record acting as a crop with cycles.
- Two places to pick the same thing (section-level crop and species both meaning "crop" in the UI).
- Data loss in the move, or a live deploy that needs hand-fixing of hundreds of records.

## Margin Par mapping (for later)
`Crop Type` "Rose" → Crop Species Rose + Sub Crop "Standard rose"; "Spray Rose" → same crop, Sub Crop "Spray rose";
each summer flower type → its own Crop Species under the Summer Flowers group.

## Approaches considered
- **A. Each species becomes a `Production Crop`.** Rejected: Production Crop is a farm section with its own land,
  pages and unit labels; units belong to exactly one. Onion, Potato and Cabbage would each need their own pivots and
  their own desk section, breaking shared land.
- **B. Make `Production Crop` a tree holding groups and crops.** Rejected: every screen and the 24 record types
  linking it would have to tell groups from crops; more work and risk, and it still mixes section with species.
- **C. Keep sections, add the classification beside them (chosen, user approved 2026-11-25).** Sections stay as
  they work today; the species record (ex Field Crop) becomes the real crop under a Crop Group tree, with optional
  sub-crops. Cycles say where (unit → section) and what (crop → sub-crop → variety).

## Decided with the user
- Groups: Floriculture, Fruit Crops, Vegetable Crops, Plantation Crops, Fodder Crops; Summer Flowers is a group
  inside Floriculture, not a crop; coffee (and later tea) in Plantation Crops; Avocado is a crop in Fruit Crops.
- Mapping is always crop → (sub-crop) → variety; sub-crop is a division of one crop like Standard / Spray rose.
- Sections stay separate from the classification. Animal production comes later.

## Calls made by the designer (check these)
- Doctype names `Crop Group`, `Crop Species`, `Sub Crop`; renaming `Field Crop` and `field_crop` now (never deployed).
- Section settings stay on the section this round.
- Crop Group is a tree so Summer Flowers can nest; only six standard groups are seeded.
- Group roll-up totals only add up crops that share a unit.

- A variety keeps its section (required); crops per section come from varieties.
- Single-crop sections (Avocado) fill the crop silently and keep their pages unchanged; the picker appears only
  where a section has more than one crop.
- The section link is labelled "Section" in the doctype JSONs as well as our screens.
- This round is `mutara` only; port to `main` and `marginpar` later.

## Left to the builder
- Patch internals, rename mechanics, the name map for unknown crops, exact UI layout of the Crops tab, test layout.
- Tests: patch on a copy of mutara.local data (counts before/after per doctype, no record left with a variety whose
  crop disagrees), variety/sub-crop validation, picker filtering, group totals, phone types. Run tests one module at
  a time on mutara.local; back up before migrate.
