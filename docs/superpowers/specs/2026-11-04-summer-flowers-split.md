# Splitting upande_summer_flowers into the three apps (Margin Par)

Date: 2026-11-04. User decision: strip `upande_summer_flowers` and place everything under
upande_production, upande_crop_material_planning and upande_propagation, exactly like the
upande_agriculture split (`2026-11-04-agriculture-split.md` — same rules). Goal of this phase: the three
apps installed together mirror summer_flowers `live` functionally, **and the data adds up** on
marginpar.local (the real live data is loaded there). Cleaning comes after.

Source (read-only, never edit, never install): `/mnt/data/code/frappe16-marginpar/apps/upande_summer_flowers`,
branch `live` @ 11e8f71 (origin git@github.com:Jimmypaps001/upande_summer_flowers.git). It matches live's 61
doctypes; the repo is slightly ahead (new fields on Crop Protocol Version, Summer Flower Production Plan,
Summer Flower Plan Block — take the repo version).

## Doctype map (names + fieldnames identical; D = parent, C = child, S = single)

**upande_crop_material_planning** — module "Upande Crop Material Planning"
D Summer Flower Market Demand, C Summer Flower Demand Week, C Summer Flower Demand Grade,
D Summer Flower Production Plan, C Summer Flower Plan Block, C Summer Flower Plan Month, C Summer Flower Plan Week,
D Summer Flower Season Plan, C Summer Flower Season Planting,
D Summer Flower Budget, C Summer Flower Budget Fiscal Year, C Summer Flower Budget Month,
D Block Production Budget, C Block Production Budget Category, C Block Production Budget Line,
D Summer Flower Procurement Plan, C Summer Flower Purchase Allocation, C Summer Flower TC Price Band,
D Material Route, C Material Route Stage, D Material Stage, C Crop Material Stage, C Planting Material Requirement,
D Summer Flower Grade, C Summer Flower Handover Wave, C Summer Flower Stage Lead.
Code: planning_api, planning, plan_sheet, plan_space, cohort_solver, simplex, explain, lifecycle_sim, sourcing,
tc_supply, demand_import, valuation, material_request, route_methods, route_backfill, crop_routes, stages;
reports summer_flower_plan_space; www summer-flowers-planning; workflow "Summer Flower Production Plan Approval".

**upande_propagation** — module "Upande Propagation"
D Summer Flower Propagation Plan, C Summer Flower Propagation Week, C Summer Flower Propagation Source,
C Summer Flower Propagation Intake, C Summer Flower Propagation Allocation, D Summer Flower Propagation Actual,
D Summer Flower Motherstock Plan, C Summer Flower Motherstock Week, C Summer Flower Motherstock Cycle,
C Summer Flower Motherstock Generation, D Summer Flower Motherstock Batch.
Code: propagation_solver, propagation_actuals, propagation_feed, motherstock_sim, trough_actuals, trough_plan,
plant_receipt + plant_issue (bought-in plant material: PO/PR/PI hooks, inspection gate),
setup/propagation_units (Warehouse Type "Propagation Unit"), setup/plant_quality.

**upande_production** — module "Crop Production"
D Planting Calendar, C Planting Calendar Bed, C Planting Calendar Flush,
D Field Activity, C Crop Field Activity (summer_flowers' own; ours is Field Operation — both coexist),
D Crop Protocol Version, C Crop Protocol Way, C Crop Protocol Way Stage,
D Summer Flower Protocol, C Summer Flower Protocol Flush, C Summer Flower Protocol Grade,
C Summer Flower Protocol Lift, C Summer Flower Second Way,
C Crop Cycle Weekly Target, D Bed Work Order, C Bed Work Progress,
D Block Change Request, C Block Change Result, C Block Change Source, C Block Area Revision, C Block Bed,
C Summer Flower Growth Stage, S Summer Flower Settings, C Summer Flower Approver Role.
Code: crop_cycle (its SummerFlowerCropCycle merges into production's Crop Cycle controller), crop_cycle_api,
crop_cycle_ops, crop_protocol (+ protocol_merge, protocol_split, route_ways), bed + bed_naming + block
(Bed/Block hooks, autoname, Bed class override), root_line, operations_api, delivery_confirmation, settings,
customization_check, tours (+ tour_data), api.py & mobile/api.py field endpoints; doctype_js (Crop Protocol,
Crop Cycle), block_list.js, sf_calendar.js, sf_walkthrough.js; reports crop_protocol_yield,
summer_flower_planting_slippage; www summer-flowers-overview, summer-flowers-flow, crop-cycles; workflows
"Planting Calendar Approval", "Crop Protocol Approval"; roles Agriculture Manager / Agriculture User; the custom
fields in summer_flowers/custom/*.json (Bed, Block, Crop Cycle, Crop Protocol, Farm, Item, Seedling Request,
Market Demand, Material Request(+Item), Purchase Order(+Item), Purchase Receipt Item, Purchase Invoice Item) go
to whichever app owns the behaviour that uses them (most to production; MR/PO/PR/PI ones with plant_receipt to
propagation; Market Demand's with planning).

Grey areas: a module used by two apps stays in the lowest app in the dependency chain (production) and the
others import it — dependency direction is one way: core ← production ← planning / propagation. Decide, write
it down in your report.

## Rules (same as the agriculture split, plus)
1. Old paths keep working: `override_whitelisted_methods` for every `upande_summer_flowers.*` whitelisted
   method you take; www routes keep their URLs; reports keep their names.
2. Ownership patch (pre_model_sync) per app: module "Summer Flowers" → the app's module for its doctypes,
   Workflows, Reports, Workspace, Custom HTML Block; no-op when absent. On marginpar.local those doctypes
   exist as **custom DocTypes (custom=1)** mirrored from live with real data: the patch must also set
   `custom = 0` so the app's JSON adopts the existing tables. NEVER delete a mirror doctype (it drops the
   table and the data).
3. No `upande_summer_flowers` imports when done. Tests move with their code.
4. UI follows `2026-11-04-legacy-pages-and-frontends.md`: legacy www pages and the Summer Flowers
   Navigation block stay reachable; React pages in each app's SCP-style frontend; workspaces only links.
5. Data must add up: after migrate on marginpar.local, every live record still opens, counts unchanged, and
   the app's own pages (and the summer-flowers www pages) compute the same figures as live.

## Production port status (end of session, 2026-11-04)

Branch `marginpar`. marginpar.local is migrated and consistent; nothing is half-applied.

**Done**
- Package `upande_production/summer_flowers/` (module names as in the source): settings, planning, stages, crop_routes,
  route_methods, route_ways, valuation, crop_protocol, protocol_merge, protocol_split, crop_cycle (SummerFlowerCropCycle,
  registered through `override_doctype_class`, gated on `custom_is_summer_flower_cycle`), crop_cycle_api, crop_cycle_ops,
  bed (class override), bed_naming, block, root_line, operations_api, delivery_confirmation, customization_check, tours,
  api, lifecycle_sim, sourcing, tc_supply, simplex, cohort_solver; `protocol_math` (plants per bed, saleable, establishment,
  size_planting, lifted out of the planning doctype so production owns it).
- `summer_flowers/upstream/`: lazy forwarders for the few things production reaches that planning/propagation own
  (planning_api, trough_plan, plant_receipt, plant_issue, and the production/procurement/propagation/motherstock plan
  controllers). Nothing imports a sibling at load time.
- The 24 production doctypes (JSON from the repo `live` version, so Crop Protocol Version has the repo fields and methods
  `weeks_tc_to_first_cut()`, `ramp_ratios()`), module "Crop Production", under `crop_production/doctype/`.
  `patches/take_over_from_upande_summer_flowers` (pre_model_sync) flips module and `custom = 0`; on marginpar.local all
  records survived (43 planting calendars, 46 protocol versions, 6 field activities, 111 crop field activities, ...).
- hooks: doc_events (Crop Protocol, Block, Bed), before/after_migrate, doctype_js, list js, app_include_js, workflows,
  roles, and `SUMMER_FLOWERS_OVERRIDES` (old `upande_summer_flowers.*` whitelisted paths -> new). Custom fields and
  property setters for Crop Cycle, Crop Protocol, Bed, Block, Farm, Item ship under `crop_production/custom/`.
- www pages crop-cycles, summer-flowers-flow, summer-flowers-overview and the two reports are ported (overview renders
  real data). Field endpoints from `mobile/api.py` are in `mobile/summer_flowers_api.py`.
- React: Blocks & Beds, Crop Cycles, Overview, Farm Map (layout fallback: Block/Bed carry no geometry on live data),
  Planting Calendars, Protocol Versions, Crop Protocols; item names instead of codes.
- Checked: Crop Cycle re-save leaves plants, area, beds and weekly targets identical on 40 real cycles (only the derived
  title and plant age move). Protocol `before_validate`+`validate` give identical results to the original code on 35 real
  protocols (in-process comparison against the read-only source).
- Tests: `crop_production/tests/test_summer_flowers_port.py` (protocol math, week helpers, every old path resolves, hooks
  resolve, ownership patch guard). Empty doctype test stubs removed (they pull ERPNext master data and break the runner
  on live data). Test helpers made to work on the live schema (crop_type mandatory, a farm with beds and zones).

**Left**
- `www/summer-flowers-planning` is planning's; `test_simulation_parity` imports planning_api (planning's).
- Source patches (`upande_summer_flowers/patches`) not ported: live data is already past them. Only `merge_protocol_onto_crop_protocol`
  logic lives on, in `protocol_merge.after_migrate`.
- tours: `tours.sync_form_tours` ported.
- Not verified: Block Change Request flows (no records), delivery_confirmation, root_line against live
  plans, the mobile endpoints, the three doctype JS files in a browser.
- Block.farm on live data disagrees with some cycle names (Bondet vs Kariki Nanyuki); the cycle title follows the block.

**Update 2026-11-05**
- Crop Protocol re-save guard (`crop_protocol.is_unedited_resave`): a save that changes no value (fields and child rows compared with
  `get_doc_before_save`) skips before_validate, validate, the status reset and the approval snapshot. A real edit, a workflow move or the
  explicit Recalculate (`flags.sf_force_recompute`) runs the old path unchanged. Proof on marginpar.local: 35 protocols re-saved in a rolled-back
  transaction, 0 changed.
- Out-of-date flag: `recompute_diff` runs the derivation against a savepoint and rolls it back (writes nothing). Endpoints
  `crop_protocol.out_of_date_protocols`, `protocol_recompute_diff`, `recalculate`. Orange intro plus Recalculate button on the form
  (`public/js/crop_protocol_stale.js`), "Out of date" badge with the diff in the React Crop Protocols page. 32 of 32 summer flower
  protocols are out of date on this data; the rest of the 35 are not summer flower protocols.
- Navigation: "Summer Flowers Navigation" Custom HTML Block (links only: React pages, legacy www pages, doctype lists) in the fixtures, and a
  standard "Summer Flowers" workspace (`crop_production/workspace/summer_flowers`) holding only that block. The old "Summer Flowers
  Planning" workspace never existed on marginpar.local, so there was nothing to flip. Planning-owned lists are not linked from here.
- Optional schema: Crop Cycle on live has no company, number_of_beds, replanting_logs, uprooting_logs. `crop_cycle_api.have_fields` and
  `cycle_company` read only what exists and take the company from the farm. Bed Work Order uses the cycle's `uproot_log`, logs replanting
  only where a table exists, and cancel returns plants and bed statuses exactly once (bed statuses are stashed in a Comment).
  Supplier propagator fields and Material Request custom_request_type are read only when present.
- Tests: whole `upande_production` suite passes on marginpar.local; new tests for the guard, the diff and Bed Work Order.

**Cleaning phase 2026-11-05**
- `summer_flowers/cleanup.refresh_protocols(apply=False, names=None)`: dry run returns the per-protocol diff; `apply=True` recomputes and saves each
  protocol keeping its workflow status, and for an Approved protocol whose inputs moved against its snapshot writes a fresh Crop Protocol Version
  through `approve()` with change reason "data refresh" (the protocol's own reason is put back). A protocol with a missing link target (e.g. a
  deleted Approved By user), or whose snapshot is refused, is skipped and reported (savepoint rollback), never fatal.
  Run: `bench --site X execute upande_production.summer_flowers.cleanup.refresh_protocols --kwargs "{'apply': True}"`.
- Comparator fixes found on the way (a freshly approved protocol still "differed" from its own snapshot and fell back to Draft on recompute):
  `_comparable` treats None/''/0 as blank, ignores `__unsaved`-style row keys, and applies the snapshot's 5% cutting_reject default;
  `align_flush_pinch` derives `weeks_from_pinch` on the protocol's flush rows the way the version does.
- marginpar.local result: 32 protocols; 18 refreshed and 8 Approved ones got a v+1 snapshot "data refresh" (all statuses
  unchanged); a second apply after the comparator fixes refreshed 15 more without new snapshots. 14 remain out of date (all skipped, none crashed): 3 with a deleted
  Approved By user (110402-Carzan Ks, 120907-Carzan Mr, Dahlia-Carzan Ks); 11 Approved Aster protocols with no grade allocation (approval
  refuses; fill the grade allocation, then rerun).
- Protocol title: `before_validate` falls back to protocol_name when no variety title can be derived; the form JS falls back to the doc name so
  the sidebar header no longer reads "undefined" for a protocol saved before the title existed.
- `install.before_install` / `after_install` hooks (see the runbook, step 3).
- Test leak: `upande_crop_material_planning/tests/test_budget.py` tearDown (and the twin in upande_agriculture) calls `frappe.db.commit()` with the
  fixture Crop Cycle (variety TEST-BUDGET-VARIETY) still in the transaction. Not ours to edit; production's own `frappe.db.commit()` in test_plan
  and test_todo_helpers (which could commit other pending fixtures) were removed.
