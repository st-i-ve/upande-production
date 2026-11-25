# Crop Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the agronomic crop tree (Production Crop Group → Production Field Crop → optional Production Sub Crop → Production Variety) beside the existing farm sections (Production Crop), on branch `mutara`.

**Architecture:** `Production Crop` stays the farm section (land, pages, access). `Field Crop` is renamed `Production Field Crop` (the species) and loses its section link; a new nested `Production Crop Group` classifies crops; a new `Production Sub Crop` divides a crop. A section's crops are derived from its varieties; the crop picker appears only where a section has more than one crop.

**Tech Stack:** Frappe v16 / ERPNext v16 (Python, doctype JSON, patches), React + TypeScript desk bundle (`frontend/`, vitest), React Native phone app (`/home/ubuntu/stive/code/reactnative/upande-production`, jest).

**Spec:** `docs/superpowers/specs/2026-11-25-crop-hierarchy-design.md`

## Global Constraints
- Doctype names exactly: `Production Crop Group`, `Production Field Crop`, `Production Sub Crop`. Never "Crop Type" or "Crop".
- Fieldnames stay `field_crop` (Link → Production Field Crop); new fieldname `sub_crop` (Link → Production Sub Crop); group link fieldname `crop_group`; tree parent `parent_production_crop_group`.
- Standard groups (exact names): Floriculture, Summer Flowers (parent Floriculture), Fruit Crops, Vegetable Crops, Plantation Crops, Fodder Crops.
- Mutara crop → group: Avocado, Passion Fruit → Fruit Crops; Onion, Potato, Cabbage → Vegetable Crops; Maize → Fodder Crops.
- Every Link to Production Crop is labelled "Section" (doctype JSON, desk, phone). "Crop" means only the species.
- Never touch MariaDB directly; bench/ORM only. Back up mutara.local before migrate. Run tests one module at a time on mutara.local. Restart only `frappe16-mutara-web:frappe16-mutara-frappe-web`.
- No Claude attribution in commits. Whole-file commits; the built bundle (`upande_production/public/dist/`) in its own commit.
- Do not push, do not touch live.

## Review Focus
1. Live order: `add_field_crops` then the new patches on a site where `Field Crop` never existed → crops created straight as Production Field Crop, no error. (Task 1 test `test_fresh_site_patch_order`.)
2. Re-running the patches on mutara.local changes nothing the second time. (Task 1 test `test_crop_hierarchy_patch_idempotent`.)
3. Avocado section (one crop): saving a cycle/harvest with no field crop silently fills Avocado; no crop picker in the bootstrap. (Task 2 test `test_single_crop_section_fills_silently`.)
4. A variety of a crop with sub-crops saved without sub-crop → refused; a sub-crop of another crop → refused. (Task 2 tests.)
5. Group totals never add Kg to Pieces. (Task 2 test `test_group_totals_per_unit`, Task 4 vitest.)

---

### Task 1: Doctypes and migration

**Files:**
- Create: `upande_production/production/doctype/production_crop_group/` (json, py NestedSet, `__init__.py`)
- Create: `upande_production/production/doctype/production_sub_crop/` (json, py, `__init__.py`)
- Move: `upande_production/production/doctype/field_crop/` → `production_field_crop/` (json name/module, class `ProductionFieldCrop`)
- Modify: the 9 doctype JSONs with `field_crop` (Buyer Commitment, Crop Forecast, Harvest Batch, Harvest Grading Log, Production Crop Cycle, Production Harvest, Production Protocol, Production Variety, Yield Sample): Link options → Production Field Crop, label "Crop"; add `sub_crop` after it (label "Sub-crop"; `fetch_from: variety.sub_crop` where the doctype has `variety`)
- Modify: all 24 JSONs with a Link to Production Crop: label "Section"; bump `modified`
- Create: `upande_production/patches/rename_field_crop_doctype.py` ([pre_model_sync])
- Modify: `upande_production/patches/add_field_crops.py` (reload `production_field_crop`)
- Create: `upande_production/patches/crop_hierarchy.py` ([post_model_sync], after add_field_crops)
- Test: `upande_production/production/tests/test_crop_hierarchy_migration.py`

**Production Field Crop fields:** crop_name (autoname field), crop_group (Link Production Crop Group, reqd), scientific_name (Data), product (Item), harvest_uom (UOM), color (Color), enabled (Check, default 1). Remove `production_crop`.
**Production Sub Crop fields:** sub_crop_name (autoname field), field_crop (Link Production Field Crop, reqd, in_list_view), product (Item), harvest_uom (UOM), enabled.
**Production Crop Group:** group_name (autoname field), parent_production_crop_group, is_group (default 1), sort_order (Int), description; tree view; perms like Production Crop.

**Interfaces:**
- Produces: `crop_hierarchy.STANDARD_GROUPS: list[tuple[str, str | None]]`, `crop_hierarchy.CROP_GROUPS: dict[str, str]` (crop name lower → group), `crop_hierarchy.execute()`.

- [ ] **Step 1: Write failing tests** — `test_standard_groups_exist` (six groups, Summer Flowers parent Floriculture), `test_mutara_crops_grouped` (each Mutara crop's crop_group per Global Constraints), `test_avocado_is_a_crop` (Production Field Crop "Avocado" exists, Hass and Fuerte have field_crop Avocado, every Avocado-section cycle/protocol has field_crop Avocado), `test_crop_hierarchy_patch_idempotent` (run execute() twice; counts of groups, crops and linked rows unchanged), `test_fresh_site_patch_order` (on a crop created via add_field_crops logic with no Field Crop doctype present the result is a Production Field Crop with a group), `test_section_links_labelled_section` (every Link to Production Crop in module Production has label "Section").
- [ ] **Step 2: Run, expect FAIL** — `bench --site mutara.local run-tests --app upande_production --module upande_production.production.tests.test_crop_hierarchy_migration`
- [ ] **Step 3: Implement** — rename patch: if DocType "Field Crop" exists and "Production Field Crop" does not, `frappe.rename_doc("DocType", "Field Crop", "Production Field Crop", force=True)`. crop_hierarchy: create groups; for each crop without crop_group set from CROP_GROUPS (unknown left empty, printed); create Avocado crop for any section whose crop_key is `avocado` (product = its varieties' common `product`, uom Kg, group Fruit Crops) and fill field_crop on that section's varieties, protocols, cycles, harvests, batches, samples, forecasts, commitments, grading logs where empty (`frappe.db.set_value(..., update_modified=False)`). `logic/field_crops.create_from_varieties` no longer reads/writes `production_crop` (match by name).
- [ ] **Step 4: Back up and migrate** — `bench --site mutara.local backup && bench --site mutara.local migrate`; then run Step 2 command, expect PASS; run `test_field_crops` module, expect PASS after adjusting it to the new names.
- [ ] **Step 5: Commit** — doctypes, patches, tests.

### Task 2: Crop logic

**Files:**
- Modify: `upande_production/production/logic/field_crops.py` (DT = "Production Field Crop")
- Modify: `production_variety.py`, `production_protocol.py`, `production_crop_cycle.py`, `production_harvest.py` validate hooks
- Test: `upande_production/production/tests/test_field_crops.py` (extend)

**Interfaces:**
- Produces:
  - `crops_of(section: str) -> list[str]` — distinct enabled `field_crop` of the section's enabled varieties, sorted.
  - `has_field_crops(section: str) -> bool` — `len(crops_of(section)) > 1`.
  - `only_crop(section: str) -> str | None` — the single crop when exactly one.
  - `list_for(section: str | None, enabled_only=False) -> list[dict]` — rows `{name, crop_name, crop_group, product, harvest_uom, color, enabled, sub_crops: [{name, harvest_uom}]}`; for a section, crops_of(section) when non-empty else all crops.
  - `harvest_uom(field_crop, default=None, sub_crop=None)` — sub-crop's unit, else crop's, else default.
  - `check_variety(doc)` — throws when doc.variety's field_crop/sub_crop disagree with doc's; on Production Variety throws when the crop has enabled sub-crops and `sub_crop` is empty, or `sub_crop` belongs to another crop.
  - `group_totals(rows, qty_key="qty") -> list[dict]` — rows with field_crop, uom, qty → `[{crop_group, uom, qty}]`, one line per (group, unit).
  - `stamp()` keeps its signature; when the record's section has exactly one crop it fills that crop; fills sub_crop from the variety.
  - `check_section` removed (callers use `check_variety`).

- [ ] **Step 1: Failing tests** — `test_single_crop_section_fills_silently` (Avocado cycle saved without field_crop → field_crop "Avocado"; `has_field_crops("Avocado")` is False), `test_fv_section_requires_crop` (F&V cycle without field_crop → ValidationError), `test_variety_needs_sub_crop_when_crop_has_them`, `test_sub_crop_of_other_crop_refused`, `test_record_disagreeing_with_variety_refused`, `test_group_totals_per_unit` (Onion 10 Kg + Potato 5 Kg + Cabbage 3 Pieces → Vegetable Crops 15 Kg and Vegetable Crops 3 Pieces), `test_harvest_uom_prefers_sub_crop`. Test records made in setUp with test-prefixed names, removed in tearDown.
- [ ] **Step 2: Run, expect FAIL** — `bench --site mutara.local run-tests --app upande_production --module upande_production.production.tests.test_field_crops`
- [ ] **Step 3: Implement** the interfaces above; update every caller of `check_section`/`has_field_crops` (grep) to the new meaning.
- [ ] **Step 4: Run the module, expect PASS**; then run the other test modules that import field_crops one at a time (`grep -l field_crops upande_production/production/tests`), expect PASS.
- [ ] **Step 5: Commit.**

### Task 3: API

**Files:**
- Modify: `upande_production/api/field_crops.py`, `upande_production/api/production.py` (`get_bootstrap`)
- Test: `upande_production/production/tests/test_crop_tree_api.py`

**Interfaces:**
- Produces (all whitelisted, envelope as the rest of api/):
  - `get_crop_tree() -> {"groups": [{name, parent, sort_order}], "crops": [list_for rows], }`
  - `save_crop_group(data: dict) -> {name}` — keys name?, group_name, parent, sort_order; managers only.
  - `save_field_crop(data)` — keys name?, crop_name, crop_group, scientific_name, product, harvest_uom, color, enabled (drop production_crop).
  - `save_sub_crop(data) -> {name}` — keys name?, sub_crop_name, field_crop, product, harvest_uom, enabled.
  - `list_field_crops(crop)` keeps its name, returns `list_for(crop)`.
  - Bootstrap per section: `field_crops = list_for(section, True)` limited to crops_of(section), `has_field_crops = int(has_field_crops(section))`; top level adds `crop_groups` (same as get_crop_tree groups).
- [ ] **Step 1: Failing tests** — tree shape, manager-only writes (Production Viewer gets PermissionError), Avocado bootstrap has_field_crops 0, F&V bootstrap lists 5 crops each with crop_group.
- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4: Run, expect PASS.** **Step 5: Commit.**

### Task 4: Desk screens

**Files:**
- Modify: `frontend/src/lib/field-crops-api.ts` (types: `CropGroup {name, parent, sort_order}`, `FieldCrop` + `crop_group`, `scientific_name`, `sub_crops`; `getCropTree`, `saveCropGroup`, `saveSubCrop`), `frontend/src/lib/field-crops.ts` (`cropLabel(fieldCrop, variety, label, subCrop?)` → "Rose · Spray rose (Variety)"; `groupTotals(rows, crops)`)
- Modify: `frontend/src/components/settings/FieldCropsPanel.tsx` → Crops tab: group tree left, crops of selected group right, sub-crops inside a crop; add/edit/disable each; read-only without can_manage
- Modify: crop pickers (`AddCycleDialog`, `NewCycleDialog`, `EditCycleDialog`, `VarietyDialog`, protocol, grading, forecast panels): options grouped by crop group (optgroup headers), sub-crop select shown when the crop has sub-crops; VarietyDialog asks section + crop (+ sub-crop)
- Modify: `CropTotals.tsx` and manager/forecast totals: per-group roll-up lines via `groupTotals`
- Modify: label strings "Field crop" → "Crop"; section links shown as "Section"
- Test: vitest beside each touched component (`__tests__/FieldCropsPanel.test.tsx`, `FieldCropCycle.test.tsx`, `CropTotals.test.tsx`, `field-crops.test.ts`)

- [ ] **Step 1: Failing vitest** — groupTotals keeps Kg and Pieces apart; picker shows sub-crop select only for a crop with sub-crops; Crops tab renders Summer Flowers under Floriculture; Avocado section shows no crop picker.
- [ ] **Step 2: Run `cd frontend && npx vitest run <files>`, expect FAIL.** **Step 3: Implement.** **Step 4: `npx tsc --noEmit && npx vitest run`, expect all PASS.**
- [ ] **Step 5: Commit source;** then `npm run build` and commit `upande_production/public/dist/` alone.

### Task 5: Phone

**Files (repo `/home/ubuntu/stive/code/reactnative/upande-production`, branch `mutara`):**
- Modify: `src/types/index.ts` (`sub_crop?: string | null` beside `field_crop`), `src/services/field-crops.ts` (label "Crop · Sub-crop · Variety", unit from sub-crop else crop), `src/services/planning.ts`, `src/services/harvest-queue.ts`
- Test: `__tests__/fieldCrops.test.ts`
- [ ] **Step 1: Failing jest** — label with and without sub-crop; unit prefers sub-crop. **Step 2: FAIL. Step 3: Implement. Step 4: `npx jest __tests__/fieldCrops.test.ts && npx tsc --noEmit`, PASS. Step 5: Commit** (on top of fe2b9b9).

### Task 6: Verify on mutara.local
- [ ] Restart web; load the desk as Administrator: Settings → Crops shows the six groups and Mutara's six crops; F&V Cycles shows the grouped crop picker; Avocado pages unchanged.
- [ ] Record per-doctype counts of rows with field_crop before/after (from Task 1 backup vs now) in the final report.
