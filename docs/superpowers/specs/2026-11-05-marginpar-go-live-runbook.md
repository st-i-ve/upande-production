# Margin Par go-live runbook: upande_agriculture + upande_summer_flowers -> production / crop material planning / propagation

Date: 2026-11-05. Site: https://marginpar.frappe.cloud (Frappe Cloud). Written from the repos
(`/mnt/data/code/frappe16-marginpar/apps/*`, branch `marginpar`) and the read-only live export
`~/stive/marginpar_live_export_20261104/` (manifest.json, versions.json, schema/, customisation/, ui/).
Nothing in this document has been run against live. Specs: `2026-11-04-agriculture-split.md`,
`2026-11-04-summer-flowers-split.md`, `2026-11-04-legacy-pages-and-frontends.md`.

Terms: SITE = `marginpar.frappe.cloud`; STG = the staging copy of it (restored from a live backup).
Run every command on STG first. Commands are `bench --site SITE ...` on a shell, or the same Python in
Desk > System Console / `bench console` where shown as Python (Frappe Cloud public benches have no shell:
use the dashboard actions and the System Console).

---------------------------------------------------------------------------------------------------

## 0. What live has (from the export) and what changes

Live apps (versions.json): frappe 16.53.0, erpnext 16.52.1, hrms 16.52.0, upande_core, upande_agriculture,
upande_summer_flowers, **upande_propagation (already installed, an older branch)**, upande_ta, upande_hr,
upande_payroll, upande_ats, upande_crm, upande_accounting, upande_asset, frappe_assistant_core 2.5.0, wiki
2.0.0, marginpar_integration.

Modules on live and their doctypes (export `schema/`): Upande Agriculture 34, Summer Flowers 61, Upande
Propagation 44 (includes `Block`, `Seedling Request`, `Crop Type`, `Agriculture Settings`), Upande Core 11
(`Bed`, `Farm`, ...). The brief said 36 agriculture doctypes; the export has 34 (the 36 probably counted two
that live does not have). Use the query in 1.3, not a typed list.

After go-live, ownership is:

| Module (new) | App | Takes |
|---|---|---|
| Crop Production | upande_production | agriculture field-execution doctypes (31, see patch), 24 summer-flower field doctypes, Crop Type, Agriculture Settings |
| Upande Crop Material Planning | upande_crop_material_planning | Production Forecast(+Week), Production Projection, Projection Week, page production_budget, 26 summer-flower planning doctypes, report Summer Flower Plan Space |
| Upande Propagation | upande_propagation | Flower Trial (+3 children), 11 summer-flower propagation/motherstock doctypes |

`Block`, `Seedling Request`, Propagation Batch etc. already are in "Upande Propagation" and stay there.
`Bed`, `Farm` stay in Upande Core.

### Why the local rehearsal order is NOT safe on live

On marginpar.local agriculture was uninstalled first, before the ownership patches existed. That worked only
because the local site was an empty copy. `bench uninstall-app` (Frappe Cloud "Uninstall App") runs
`frappe.installer.remove_app`: for every Module Def of the app it **drops the table of every DocType whose
`module` is that module**, and deletes every Workspace, Report, Page, Web Form and any record with a Link to
that Module Def (this includes Custom Field and Property Setter rows whose `module` is the old module).
On live the tables hold 641 Crop Cycles, 32 Crop Protocols, 62 SF Production Plans, ... If the module of a
DocType row has not been flipped to a new app's module before the removal, the table and its data are gone
(backup restore is the only way back). Therefore on live:

1. install the new apps and migrate first (ownership flips the DocType rows' module);
2. prove that nothing is left in the old modules;
3. only then remove the old apps, and only when step 2's queries return zero.

### Two Frappe behaviours the order depends on (verified in `frappe/installer.py`, `frappe/model/sync.py`)

- **`install-app` does not run the new app's `patches.txt`.** `install_app` calls `sync_for(app)` (imports the
  app's DocType JSON, which already carries the new `module`) and then `set_all_patches_as_completed(app)`,
  i.e. writes every patch of the app into Patch Log without executing it. So on a fresh install of
  production and planning the `take_over_*` patches are logged as done and never run. The JSON import flips
  the DocType module itself, but the extra rows the patches handle (Workspace, Sidebar, Report, Page,
  Custom Field, Property Setter module, `custom=0`) are NOT handled. Fix for production (done): `upande_production`
  has a `before_install` hook (`upande_production.install.before_install`). `install_app` runs before_install BEFORE
  `sync_for` (verified in `frappe/installer.py`: before_install loop, then `add_module_defs`, then `sync_for`, then
  `set_all_patches_as_completed`), so the five pre_model_sync patches (the three renames and both take-overs) run
  before the JSON import and adopt the existing doctypes. An `after_install` hook runs the setup patches that
  `set_all_patches_as_completed` would skip (crop defaults, desktop icon, default bands). Planning has the same pair
  (`upande_crop_material_planning.install.before_install` runs both take-overs without creating its Module Def,
  which `add_module_defs` inserts right after and would refuse as a duplicate; `after_install` sets up the desk
  tile). As a fallback for both, run the patches by hand (they are idempotent), see 3.3. For an app that is **already installed** (propagation)
  `bench migrate` does run the new patches normally.
- **`bench migrate` ends with `remove_orphan_doctypes`:** a standard DocType (custom=0) whose controller
  cannot be found through its module is deleted (the DocType row, not the table). So never migrate a state
  where a doctype's module row points at an app that no longer ships it (see 2.3, Crop Type).
- The production app also lists many `[post_model_sync]` patches (`number_cycles`, `renumber_cycles_by_pattern`,
  `drop_cycles_for_bees_and_fish`, `backfill_*`, `seed_*`, ...). They are Mutara/avocado data patches that
  read `Production Crop Cycle`, `Production Protocol`, etc. On Margin Par they must be logged as completed by
  `install_app`, not executed. Check Patch Log in step 3.2. If a later migrate ever runs them
  (Patch Log row missing) stop and investigate before continuing.

---------------------------------------------------------------------------------------------------

## BLOCKERS (resolve before the window)

1. **upande_crop_material_planning has no GitHub repo.** `git remote -v` is empty; the branch exists only in
   `/mnt/data/code/frappe16-marginpar/apps/upande_crop_material_planning`. Frappe Cloud can only add an app
   from a GitHub repo (public, or private with the FC GitHub app authorised). Create the repo, push branch
   `marginpar`, authorise it for the Frappe Cloud team. Not done here (instruction: no push).
2. **Production and propagation `marginpar` branches** must be pushed too: production has remote `mutara`
   (local Mutara clone) and `origin` st-i-ve/upande-production; propagation origin is
   Jimmypaps001/upande-propagation. Confirm the exact repo/branch FC will pull and that the commit to deploy is
   pushed. Production's working tree currently has uncommitted edits from another agent
   (`crop_protocol.js`, `crop_protocol.py`, `summer_flowers/cleanup.py`): deploy only a committed, tagged sha.
3. **Custom Fields not owned by any new app.** The export has 293 Custom Fields and 37 Property Setters with
   module "Summer Flowers". The production patch re-homes those on Crop Cycle, Crop Protocol, Bed, Block, Farm,
   Item only. These stay in module "Summer Flowers" and would be **deleted by removing upande_summer_flowers**
   (and their columns dropped on the next `bench migrate`/cache sync is not guaranteed, but the field rows go):
   Material Request (7 `custom_sf_*`), Material Request Item (3), Purchase Order (`custom_sf_procurement_plan`),
   Purchase Order Item (3), Purchase Invoice Item (6), Purchase Receipt Item (5), Seedling Request (3),
   plus `Farm-custom_sf_plant_receiving_warehouse` if production's `custom/farm.json` does not carry it.
   Neither propagation nor planning ships a custom JSON for them (only production's `custom/` folder exists).
   Required before step 5: move them (3.4 SQL) to module "Upande Propagation" (they belong to plant
   receiving/procurement), and ship them in the propagation app (fixture or `custom/`) as a follow-up commit.
4. **marginpar_integration cannot be inspected here.** Its repo is not in the bench copy and not in the
   export (the export only shows its Workspace "Marginpar Integrations", module "Marginpar Integration").
   Before step 5 grep it on the Frappe Cloud bench (5.1).
5. **Mark's roses mobile app** (`upande_agriculture.mobile.api.*`) works after removal only through the
   `override_whitelisted_methods` maps. They must be tested on STG with agriculture and summer_flowers
   REMOVED (4.4); a green test while the old apps are still installed proves nothing.

---------------------------------------------------------------------------------------------------

## 1. Pre-flight

### 1.1 Backup (with files)
Frappe Cloud dashboard > Site > Backups > "Schedule a backup now" (tick "with files": public AND private).
Download the DB, public and private archives and keep copies outside FC. Note the backup timestamp.
Also take a bench-group "Restore point": record the current sha of every app in the live bench group
(Bench Group > Apps).

### 1.2 Required apps and versions
- Same Frappe/ERPNext as live: frappe 16.53.0, erpnext 16.52.1, hrms 16.52.0. Do not upgrade them in this window.
- `upande_core` stays (the new apps rely on `Bed`, `Farm`, `Farm Type`; production dependency chain is
  core < production < planning, core < production < propagation).
- Branches: production `marginpar`, planning `marginpar`, propagation `marginpar` (tracks `origin/james`;
  merge `origin/james` again before the window).
- Planning and propagation declare `required_apps = ["upande_production"]`: production installs first.

### 1.3 Record counts (before). Run on SITE and on STG, save the output
Read-only. Counts by module (covers all 34 agriculture, 61 summer-flower and propagation doctypes without a
typed list), plus the named key doctypes and the custom-field/UI inventory.

```python
# Desk > System Console (or bench --site SITE console). Read only.
import json
mods = ("Upande Agriculture", "Summer Flowers", "Upande Propagation", "Upande Core")
rows = frappe.db.sql("select name, module, issingle from tabDocType where module in %s order by module, name", (mods,), as_dict=True)
out = {}
for r in rows:
    if r.issingle:
        out[r.name] = "single"
    elif frappe.db.has_table(r.name):
        out[r.name] = frappe.db.count(r.name)
key = ["Crop Cycle", "Crop Protocol", "Block", "Bed", "Farm", "Crop Type", "Item", "Warehouse",
       "Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Stock Entry"]
for k in key:
    out["KEY " + k] = frappe.db.count(k)
out["_module_of"] = {r.name: r.module for r in rows}
out["_custom_field_by_module"] = dict(frappe.db.sql("select ifnull(module,'(none)'), count(*) from `tabCustom Field` group by module"))
out["_property_setter_by_module"] = dict(frappe.db.sql("select ifnull(module,'(none)'), count(*) from `tabProperty Setter` group by module"))
print(json.dumps(out, indent=1, sort_keys=True))
```
Save as `counts_before.json`. Expected (export 2026-11-04, manifest.json): Crop Cycle 641, Crop Protocol 32,
Crop Protocol Version 46, Block 980, Bed 15363, Farm 9, Crop Type 4, Planting Calendar 43, Field Activity 6,
Summer Flower Production Plan 62, Budget 45, Market Demand 25, Procurement Plan 21, Propagation Plan 22,
Motherstock Plan 7, Season Plan 4, Material Route 15, Material Stage 15, Grade 6, Settings 1, Propagation
Batch 2, Propagation Trough 78, Plant Consignment 1, Seedling Request 1, Scan Location Mapping 2, Agriculture
Settings 1. Others 0. The live numbers will have moved since the export; the baseline is the
one you save now, taken immediately after the backup and with writes stopped (1.5).

Also save these (data that is not a DocType row):
```sql
select module, count(*) from tabWorkspace group by module;
select name, module, app, standard from `tabWorkspace Sidebar`;
select name, module from tabReport where module in ('Upande Agriculture','Summer Flowers','Upande Propagation');
select name, module from tabPage where module in ('Upande Agriculture','Summer Flowers');
select method from `tabScheduled Job Type` where method like 'upande_agriculture%' or method like 'upande_summer_flowers%' or method like 'upande_propagation%';
select name from tabWorkflow where name like '%Summer Flower%' or name like '%Crop Protocol%' or name like '%Planting Calendar%';
select version from `tabInstalled Application` ... -- or: bench --site SITE list-apps
select patch from `tabPatch Log` where patch like 'upande_%' order by creation desc limit 80;   -- save, used in 3.2
```

### 1.4 Staging rehearsal (mandatory)
1. Frappe Cloud: create STG as a new site on a **copy of the live bench group** (same app shas) and restore
   the backup from 1.1 (DB + files). Or restore into a bench group that is identical to live.
2. Run the whole runbook on STG, including 4.4 (old apps removed) and the rollback (7) once.
3. Record the answers to the three open points: (a) did `install-app` log the take_over patches without
   running them (3.2); (b) did the JSON sync flip module on its own; (c) what did 4.x show.
4. Disable outgoing email/SMS/webhooks on STG (Email Account, Notification, Webhook) before testing.

### 1.5 Freeze
Announce a window. Stop writes: tell roses and summer-flower users; pause the Mark mobile app sync if
possible. In the window set Maintenance Mode on live (`bench --site SITE set-maintenance-mode on` or
dashboard > Site Config `maintenance_mode: 1`) only for the install/migrate steps; turn it off for 4.

---------------------------------------------------------------------------------------------------

## 2. Bench group changes on Frappe Cloud

Keep upande_agriculture and upande_summer_flowers in the bench throughout the switch.

### 2.1 Deploy 1: add production and planning
Dashboard > Bench Group > Apps > Add App:
- `upande_production` (repo, branch `marginpar`, commit = the tagged sha).
- `upande_crop_material_planning` (repo from blocker 1, branch `marginpar`).
Do NOT change upande_propagation yet. Start the deploy (builds a new bench; React bundles are committed
under `upande_*/public`, so FC does not need the frontend toolchain).
Do not let FC auto-update the site into the new bench with a migrate in the middle of this: use "Update"
(Site > Updates) only when you are ready for step 3, with a fresh backup. An FC site update runs `bench
migrate` on the existing installed apps; with production and planning merely present (not installed) this is
harmless. Confirm in the update log that no patch of the old apps fails.

### 2.2 Deploy 2: switch propagation to `marginpar`
After step 3.1 to 3.3 (production and planning installed), Bench Group > Apps > upande_propagation >
"Change branch" to `marginpar`, deploy, then Update the site (migrate runs propagation's new patches).

### 2.3 Why propagation is switched second and not together
Live's propagation ships `Crop Type` and `Agriculture Settings` (module Upande Propagation). The new
propagation branch no longer contains them (production owns them). If the new propagation reaches a site
before production is installed, `migrate` finds Crop Type/Agriculture Settings with no controller and
`remove_orphan_doctypes` deletes their DocType rows (tables and Singles values survive, but links break until
production re-creates them). Production first, then propagation, avoids it. Note: between Deploy 1 and
Deploy 2 do not run any migrate: both the old propagation JSON and production's JSON claim Crop Type, and a
migrate would flip its module back and forth.

---------------------------------------------------------------------------------------------------

## 3. Install order, migrate, ownership

### 3.1 Install production, then planning
Dashboard > Site > Apps > Install: `upande_production` first, wait for success, then
`upande_crop_material_planning` (equivalent: `bench --site SITE install-app upande_production` then
`... upande_crop_material_planning`). `install_app` imports each app's JSON (the DocType rows take the new module),
syncs fixtures (workspaces, custom HTML blocks, workflows, roles, custom fields, Scan Location Mapping), the
Module Defs "Crop Production" and "Upande Crop Material Planning", Scheduled Job Types.

Production's fixtures include Roles "Agriculture Manager"/"Agriculture User" (already on live; `sync_fixtures`
updates in place) and 6 Scan Location Mappings (live has 2; fixture upsert: check the 2 are unchanged).

Production's take-over now runs automatically inside this step through its `before_install` hook; its patches are
still logged as done in the Patch Log afterwards (3.2), but they ran. Planning's take-overs run the same way
(its own before_install hook).

### 3.2 Check what ran (Patch Log)
```sql
select patch from `tabPatch Log` where patch like 'upande_production.patches.take_over%' or patch like 'upande_crop_material_planning.patches%';
```
Expected: logged (`install_app` marks them done), and not executed. Treat the ownership state as unverified
until 3.3 has run.

### 3.3 Run the ownership patches by hand (idempotent, no-ops when nothing matches)
The two production lines are a fallback: `before_install` already ran them (then they print nothing and change
nothing). Planning's two are still required.
```bash
bench --site SITE execute upande_production.patches.take_over_from_upande_agriculture.execute
bench --site SITE execute upande_production.patches.take_over_from_upande_summer_flowers.execute
bench --site SITE execute upande_crop_material_planning.patches.v1_0.take_ownership_from_agriculture.execute
bench --site SITE execute upande_crop_material_planning.patches.v1_2.adopt_summer_flowers_planning.execute
```
(Without a shell, the same as `frappe.get_attr("<path>.execute")()` in System Console.) What each does:

| Patch | Effect |
|---|---|
| production `take_over_from_upande_agriculture` | DocType.module -> "Crop Production" for the 31 field-execution doctypes (Greenhouse*, Crop Cycle*, Crop Protocol*, Cut Stage, Bucket Reuse Anomaly, Scan Location Mapping*, Production Plan Form/Task/Variety, Irrigation/Crop Protection Plan Task, Crop Type, Agriculture Settings) when module is "Upande Agriculture" or "Upande Propagation"; Workspaces "Agriculture", "Roses Production" and Workspace Sidebar "Roses Production" -> module "Crop Production", app "upande_production"; Reports attached to those doctypes. Does not touch `custom`. |
| production `take_over_from_upande_summer_flowers` | for the 24 SF field doctypes with module "Summer Flowers": module "Crop Production", `custom=0`; reports Crop Protocol Yield, SF Planting Slippage; `module` of Custom Field and Property Setter rows on Crop Cycle, Crop Protocol, Bed, Block, Farm, Item. Guard: "Field Activity" is flipped only because live's own is module "Summer Flowers"; the renames below never touch it. |
| planning `take_ownership_from_agriculture` | creates Module Def "Upande Crop Material Planning" if missing; Production Forecast, Production Forecast Week, Production Projection, Projection Week and Page production_budget -> that module. |
| planning `adopt_summer_flowers_planning` | the 26 SF planning doctypes (module "Summer Flowers" -> "Upande Crop Material Planning", `custom=0`), Report "Summer Flower Plan Space". Requires the Module Def to exist (3.1 created it). |

Related production patches in `patches.txt` that are guarded on module and must stay no-ops here:
`rename_production_operation_to_field_activity`, `rename_field_activity_to_field_operation` (renames only a
"Field Activity" in module "Production"; live's Field Activity is module "Summer Flowers" and 6 records, left
alone), `rename_forecast_and_plan_task_doctypes` (only module "Production" doctypes).
Check after: live's "Field Activity" still exists, module "Crop Production", count 6; "Field Operation" is a
new empty doctype.

### 3.3b Items the patches do not cover (do these now, SQL in System Console or `bench mariadb`)
The Summer Flowers Workspace (`standard=0`, app upande_summer_flowers) and Sidebar, the Workflows, and the
custom fields from blocker 3:
```sql
-- workspace objects of the old SF app: production ships its own "Summer Flowers" workspace/sidebar (fixture/standard);
-- keep live's rows but make them production's so removing the old app does not delete them
update tabWorkspace set module='Crop Production', app='upande_production' where module='Summer Flowers';
update `tabWorkspace Sidebar` set module='Crop Production', app='upande_production' where module='Summer Flowers';
-- anything else attached to the old modules (Client Script, Print Format, Number Card, Dashboard Chart, Web Form...)
-- is found by the generic query in 3.5; fix those the same way
-- custom fields/property setters with no owner: keep them (blocker 3)
update `tabCustom Field` set module='Upande Propagation'
  where module='Summer Flowers' and dt in ('Material Request','Material Request Item','Purchase Order','Purchase Order Item','Purchase Invoice Item','Purchase Receipt Item','Seedling Request');
update `tabCustom Field` set module='Crop Production' where module='Summer Flowers';   -- Farm etc. leftovers
update `tabProperty Setter` set module='Crop Production' where module='Summer Flowers';
commit;
```
Workflows have no module field: "Crop Protocol Approval" and "Planting Calendar Approval" are shipped by
production, "Summer Flower Production Plan Approval" by planning; fixture sync updates the live rows. Compare
state names/transitions with the live export before and after (`select name from tabWorkflow`).

### 3.4 Migrate
```bash
bench --site SITE migrate
```
(FC: Site > Actions > Migrate.) Runs production's `before_migrate` (`customization_check`: it reports
customisations that would be overwritten; read its output), model sync of all apps (adds columns to the adopted
tables, creates empty Mutara-side doctypes: Production Crop, Production Crop Cycle, ...: expected on Margin Par,
harmless), then `after_migrate`: production `protocol_merge.after_migrate`, `tours.sync_form_tours`; propagation
`install.after_migrate`, `setup.plant_quality.install`, `setup.propagation_units.install` (Warehouse Type
"Propagation Unit", Warehouse custom fields; creates missing inspection templates only).

### 3.5 Verify ownership (read-only). All must return zero rows
```sql
select name, module, custom from tabDocType where module in ('Upande Agriculture','Summer Flowers');          -- 0 rows
select name, module from tabDocType where custom=1 and module in ('Crop Production','Upande Crop Material Planning','Upande Propagation'); -- 0 rows (custom flag cleared)
select name from tabReport where module in ('Upande Agriculture','Summer Flowers');                              -- 0
select name from tabPage   where module in ('Upande Agriculture','Summer Flowers');                              -- 0
select name from tabWorkspace where module in ('Upande Agriculture','Summer Flowers');                           -- 0
select name from `tabWorkspace Sidebar` where module in ('Upande Agriculture','Summer Flowers');                 -- 0
select name, dt from `tabCustom Field` where module in ('Upande Agriculture','Summer Flowers');                  -- 0
select name from `tabProperty Setter` where module in ('Upande Agriculture','Summer Flowers');                   -- 0
```
Generic gate (every doctype that links to Module Def, anything still pointing at the old modules), Python:
```python
old = ("Upande Agriculture", "Summer Flowers")
links = frappe.get_all("DocField", filters={"fieldtype": "Link", "options": "Module Def"}, fields=["parent", "fieldname"])
for l in links:
    if frappe.db.exists("DocType", l.parent) and l.parent != "DocType" and frappe.db.has_table(l.parent):
        n = frappe.db.count(l.parent, {l.fieldname: ("in", old)})
        if n: print("LEFT", l.parent, l.fieldname, n)
print(frappe.db.sql("select name, module from tabDocType where module in %s", (old,)))
```
Expected: no `LEFT` lines, empty DocType list. And the positive check, the expected owner:
```sql
select module, count(*) from tabDocType where name in ('Crop Cycle','Crop Protocol','Greenhouse','Crop Type','Agriculture Settings','Planting Calendar','Crop Protocol Version','Field Activity','Bed Work Order','Summer Flower Settings') group by module;   -- all Crop Production
select module, count(*) from tabDocType where name in ('Production Forecast','Production Projection','Summer Flower Production Plan','Summer Flower Budget','Material Route','Summer Flower Market Demand') group by module;  -- Upande Crop Material Planning
select module, count(*) from tabDocType where name in ('Flower Trial','Summer Flower Propagation Plan','Summer Flower Motherstock Plan') group by module;   -- Upande Propagation (after 3.6)
```

### 3.6 Switch propagation to `marginpar` (Deploy 2)
Do 2.2, then Update the site. Propagation is already installed, so migrate **does** run:
- pre_model_sync `move_agriculture_ownership`: Flower Trial (+ Flower Trial Bed Range/Bed Detail, FT Harvest
  Grade) "Upande Agriculture" -> "Upande Propagation"; Crop Type and Agriculture Settings "Upande Propagation"
  -> "Crop Production" (already done by production, no-op).
- pre_model_sync `adopt_summer_flowers_propagation`: the 11 SF propagation/motherstock doctypes module and
  `custom=0`.
- post_model_sync (only the ones not yet in Patch Log): `seed_propagation_settings`, `backfill_harvest_datetime`,
  `recalculate_propagation_totals` (rewrites derived totals of Mother Blocks, Propagation Batches, Seedling
  Requests; check it is already in Patch Log from the earlier install so it does not run again), 
  `create_propagation_dashboard_page`, `add_propagation_unit_fields`, `seed_arrival_defaults`,
  `reconcile_propagation_desktop_icon`. List which are pending with step 1.3's Patch Log extract and read each
  pending one before the window.
Re-run 3.5, and confirm Crop Type has 4 rows, Agriculture Settings 1.

Scheduler: new jobs are registered by `sync_jobs` during migrate (production: stages.refresh_all_open,
cycle_chain.refresh_flags_all, scheduled.release_stale_buckets, scheduled.rollup_plan_tasks; planning:
scheduled.rollup_actuals). The old `upande_agriculture.scheduled.*` jobs stay registered until 5.3: disable
them now to avoid running twice:
```sql
update `tabScheduled Job Type` set stopped=1 where method like 'upande_agriculture.%';
```
(rollup_actuals and release_stale_buckets are the only two agriculture jobs; summer_flowers has none.)

---------------------------------------------------------------------------------------------------

## 4. Verification (maintenance mode off)

### 4.1 Counts equal
Re-run 1.3 into `counts_after.json` and diff with `counts_before.json`.
```bash
diff <(python3 -m json.tool --sort-keys counts_before.json | grep -v _module_of) <(python3 -m json.tool --sort-keys counts_after.json | grep -v _module_of)
```
Every doctype count must be identical (new doctypes appear as additions with 0). `_module_of` changes as
intended; `_custom_field_by_module`: "Summer Flowers" -> 0, the rows reappear under the new modules with the same
total. Any difference stops the window (7).

Spot data checks (read-only), same before/after: `select count(*), sum(plants) from \`tabCrop Cycle\`` (use the
plant field that exists), `select count(*) from tabBed where ...`, SF Production Plan `status` counts.

### 4.2 Desk
- Desk home: tiles/workspaces "Agriculture", "Roses Production", "Summer Flowers", "Propagation", "Production",
  "Crop Material Planning" open; each shows its Navigation Custom HTML Block (links only). No broken block.
- Lists/forms open: Crop Cycle, Crop Protocol (check the orange "Out of date" intro: 32 of 32 SF protocols are
  expected to show it; do NOT click Recalculate in this window), Crop Protocol Version, Planting Calendar, Block,
  Bed, SF Production Plan, SF Budget, Propagation Batch, Flower Trial list.
- Desk page `production_budget` opens (planning-owned).
- Reports: Crop Protocol Yield, Summer Flower Plan Space, Summer Flower Planting Slippage, Propagation Traceability.

### 4.3 Web routes
`/production_app` (Mutara avocado pages exist but crops with no data are empty; roses/summer flowers pages:
Crop Cycles, Blocks and Beds, Overview, Farm Map, Planting Calendars, Protocol Versions, Crop Protocols),
`/planning_app`, `/propagation_app`, `/crop-cycles`, `/summer-flowers-overview`, `/summer-flowers-flow`,
`/summer-flowers-planning`, `/budget-forecast`, `/propagation-dashboard`, `/propagation` www. Each loads
without a 500 and shows the figures of the old page (compare against screenshots taken on live before).

### 4.4 Old API paths resolve (do this on STG with the old apps already removed, and again on SITE)
The override map is read from hooks of the new apps; the old module need not exist.
```bash
# from a shell with an API key; pick read-only endpoints
curl -s -H "Authorization: token KEY:SECRET" https://SITE/api/method/upande_agriculture.mobile.api.<readonly_endpoint>
curl -s -H "Authorization: token KEY:SECRET" https://SITE/api/method/upande_agriculture.api.get_week_summary
curl -s -H "Authorization: token KEY:SECRET" https://SITE/api/method/upande_summer_flowers.summer_flowers.propagation_solver.options
```
Static check that every old whitelisted path still maps (in the three apps' repos):
```bash
grep -rhoE '"upande_(agriculture|summer_flowers)\.[A-Za-z0-9_.]+"' /mnt/data/code/frappe16-marginpar/apps/upande_{production,crop_material_planning,propagation}/*/hooks.py | sort -u | wc -l
```
and in the Python console `frappe.get_hooks("override_whitelisted_methods")` for each key: `frappe.get_attr(value[-1])`
must import. Run Mark's roses mobile app login and one harvest/grading round trip on STG. List of old paths
used by the mobile app (grep of its source for `upande_agriculture.mobile.api.`) must be a subset of the maps;
any path missing is added to the right app and redeployed BEFORE removal.

### 4.5 Scheduler
```sql
select method, stopped, last_execution from `tabScheduled Job Type`
 where method like 'upande_production.%' or method like 'upande_crop_material_planning.%' or method like 'upande_agriculture.%';
```
New jobs present and not stopped, old ones stopped. The scheduler must be on (Site > Site Config:
`pause_scheduler` absent/0). After the next daily run check `tabScheduled Job Log` for the five new methods with
status Complete. If waiting a day is not acceptable run once: `bench --site SITE execute upande_production.scheduled.release_stale_buckets`
and `... upande_crop_material_planning.scheduled.rollup_actuals` (read the functions first; `rollup_actuals`
rewrites forecast actuals, there are 0 Production Forecast rows on live so it should be a no-op).

### 4.6 Doc events
Submit nothing on SITE for tests. On STG: save a Block, a Bed, a Crop Cycle, a Crop Protocol; submit a Stock Entry
(planning forecast actuals + production harvest hooks fire only once each; no hook still points at an
upande_agriculture path: `frappe.get_hooks("doc_events")` printed and grepped for `upande_agriculture` and
`upande_summer_flowers`: only the two old apps' own entries remain while they are installed).

Go/no-go: 4.1 equal, 4.2 to 4.4 pass. Keep the old apps one more day (or a normal business cycle with the
mobile app) before step 5.

---------------------------------------------------------------------------------------------------

## 5. Removing the old apps

Do only after 4 has been green for the agreed period and a new backup (with files) exists.

### 5.1 marginpar_integration
Its source is not in this bench copy. On the Frappe Cloud bench open the app and grep:
```bash
grep -rnE "upande_agriculture|upande_summer_flowers|Crop Cycle|Crop Protocol|Summer Flower|Greenhouse|Production Forecast" <bench>/apps/marginpar_integration
```
Look at `hooks.py` (`required_apps`, `doc_events` on Crop Cycle/Block/Stock Entry, `override_*`), imports, and
fixtures. From the export only the Workspace "Marginpar Integrations" (module Marginpar Integration) is
visible; nothing in the exported UI/schema points at the old apps. Any import or `required_apps` of an old app
must be re-pointed to `upande_production`/... before 5.2; any `doc_events` on a doctype that production now owns
keeps working (doctype names are unchanged). If marginpar_integration lists an old app in `required_apps`,
`remove_app` refuses to uninstall that old app.

### 5.2 Gate (all must hold)
- 3.5 queries return zero (re-run now, data may have changed).
- `select count(*) from tabDocType where module in ('Upande Agriculture','Summer Flowers')` = 0.
- Blocker 3 resolved: no Custom Field/Property Setter/Client Script/Print Format/Web Form in the old modules.
- A `bench uninstall-app --dry-run`-equivalent: `bench --site SITE uninstall-app upande_summer_flowers --dry-run`
  lists only "removing Module Def" lines and no `removing DocType`, `removing Workspace`, `removing Custom Field`
  lines. Same for upande_agriculture. **Any DocType in that list = stop.**
- Neither old app has a `before_uninstall`/`after_uninstall` hook (verified in the repos' hooks.py: none).
- Backup taken, STG did the same removal cleanly.

### 5.3 Remove
Preferred (Frappe Cloud): Site > Apps > Uninstall `upande_summer_flowers`, then `upande_agriculture`. With every
DocType already re-homed this only deletes the (now empty) Module Defs and removes the app from
`installed_apps`; no table drops. Run the dry run (5.2) first. After the Uninstall:
```sql
delete from `tabScheduled Job Type` where method like 'upande_agriculture.%' or method like 'upande_summer_flowers.%';
select count(*) from `tabCrop Cycle`;   -- still equal to counts_after
```
(Module Def "Upande Agriculture" and "Summer Flowers" are gone; the new modules' Module Defs remain.)
Then run 4.1 again (counts), 4.3 and 4.4.
If a DocType does remain in an old module and cannot be moved, do not uninstall; leave the app installed
(removal from the bench group is blocked by Frappe Cloud while a site has it installed) and carry on.
The alternative of editing `installed_apps` by hand ("remove without uninstall") is possible
(`frappe.db.set_single_value`-style edit of `__global_search`/`tabSingles installed_apps`) but leaves Module
Defs and Scheduled Job Types behind and is not needed once the gate is green; use it only if the uninstall
dry run is not clean and the person responsible accepts the leftovers.

### 5.4 Bench group
After the site no longer has them: Bench Group > Apps > Remove `upande_agriculture`,
`upande_summer_flowers` and deploy. Test again (4.3, 4.4).

---------------------------------------------------------------------------------------------------

## 6. Data cleanup (optional, separate window, after at least a week of stable running)

All three are run by hand and default to a dry run. Take a backup first. Read-only first, then apply on STG,
then on SITE.

```bash
# 6.1 Crop Protocols: re-derive stale summer-flower protocols (32 of 32 are flagged Out of date)
bench --site SITE execute upande_production.summer_flowers.cleanup.refresh_protocols
#     review the per-protocol diff; only then:
bench --site SITE execute upande_production.summer_flowers.cleanup.refresh_protocols --kwargs '{"apply": true}'

# 6.2 Plan counters
bench --site SITE execute upande_crop_material_planning.summer_flowers.cleanup.refresh_plan_counters
bench --site SITE execute upande_crop_material_planning.summer_flowers.cleanup.refresh_plan_counters --kwargs '{"apply": true}'

# 6.3 Propagation plan rebuild: run the propagation app's plan rebuild entry point in dry-run mode first
#     (name given by the agent writing it; not committed at the time of this runbook, confirm the function
#     name and its dry-run parameter in upande_propagation before the window).
```
Confirm the exact argument name (`apply`) in each function's docstring before running (`refresh_protocols`
documents `apply=False` as a dry run; the other two were still being written on 2026-11-05).
Verify afterwards with 4.1 (counts must not change) and spot-compare the figures of the pages in 4.3.

---------------------------------------------------------------------------------------------------

## 7. Rollback

| Where you are | Action |
|---|---|
| Before 3.1 | nothing was changed on the site. Remove the added apps from the bench group if wanted. |
| After 3.1 to 3.6, old apps still installed | Do not "uninstall-app" the new apps: that drops the tables (their modules now own the doctypes). Restore the site from the backup of 1.1 (Frappe Cloud > Site > Backups > Restore, DB + files). On the restored DB the old apps still own everything. Then Update/redeploy the bench group to the previous app shas (propagation back to its previous branch). |
| After 5.3 (old apps uninstalled) | restore the 1.1 backup (or the backup taken in 5.2), re-add `upande_agriculture`/`upande_summer_flowers` to the bench group at the shas recorded in 1.1, and restore the site. Data written since the backup is lost; export what is needed (CSV/Data Export of the doctypes with a `modified` date after the backup) before restoring. |
| Only a bad ownership flip (data intact) | the module can be flipped back with `update tabDocType set module=... where name=...` and `bench migrate`, while the old apps are installed; faster than a restore but only for a pure module problem. |

Decision point: any 4.1 difference, any DocType loss, or a failing Mark mobile app path within the first day =
restore. Keep the 1.1 backup until the old apps are removed and a week has passed.

---------------------------------------------------------------------------------------------------

## 8. Known inherited issues (not caused by the move)

- **Crop Cycle on live lacks fields** that the source apps expect: `company`, `number_of_beds`, `replanting_logs`,
  `uprooting_logs`. The ported code reads only fields that exist (`crop_cycle_api.have_fields`, `cycle_company`
  takes the company from the farm; Bed Work Order uses `uproot_log`). Do not "fix" it by adding the fields in
  this window.
- **Supplier `custom_sf_propagation_weeks`** (propagator weeks) does not exist on live; read only when present.
- **Material Request `custom_request_type`** does not exist on live (live has `custom_sf_*` only); guarded.
- **Block.farm vs cycle name**: some cycles say "Kariki Nanyuki" while their Block says "Bondet"; the cycle title
  follows the block (display only).
- **Block has no geometry** on live data: Farm Map uses the layout fallback.
- **Crop Protocol re-saves**: a save with no change is skipped (`is_unedited_resave`); 32 of 32 summer flower
  protocols show "Out of date" until 6.1 is applied.
- **Block Change Request flows, delivery_confirmation, root_line against live plans, the mobile endpoints and
  the doctype JS files** were not verified in a browser (spec 2026-11-04-summer-flowers-split.md). Add them to the
  STG test list in 1.4.
- **Client Scripts on live** ("Crop Cycle Automation", "Crop Protocol Fill Flush Schedule", "Summer Flower Market
  Demand Fill Weeks") have no module and survive; the apps also ship `doctype_js`. Check on STG that the form is
  not double-handled.
- **Production's Mutara doctypes** (Production Crop, Production Crop Cycle, ...) appear as empty tables on Margin
  Par; the avocado www pages (`/avocado-*`) exist and are empty there.
- `maintenance.py` one-offs from agriculture are not ported.
- The agriculture spec says "36 doctypes", live has 34 in module Upande Agriculture.
