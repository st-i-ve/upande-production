# Harvesting (field crates → Harvesting stock entry) and the Upande Production mobile app

Date: 2026-10-28.

## Decisions (user)

- Harvest actuals become stock: a **Harvesting Stock Entry** at the **estimated** weight
  (crates × average kg per crate). **No receiving on our side** (collecting, truck loads, GRNs,
  intake weighing, packhouse are not ours).
- Production at Mutara is **avocado and fruits & vegetables**; harvesting works for both.
- Mobile: **one app of our own**, "Upande Production", package **`com.upande.avocadoproduction`**,
  broken off from `mark-judah/upande-harvest` (history kept, remote `harvest`), living at
  `/home/ubuntu/stive/code/reactnative/upande-production` (branch `main`). It keeps **harvesting
  only** from the harvest app; production building blocks come later from Mark's roses app
  (`reactnative/upande-production-roses`, backend `upande_agriculture`) and teddy's Avocado Trail
  (`reactnative/Upande-Avocado-React`). Mark's roses app (`com.upande.production`) is replaced only
  once roses is proven.

## Source of the harvesting part

- Mobile screens: `app/configure.tsx` (farm/section/block/team), `app/harvesting.tsx` (scan crates
  to a team, mark ready), `app/farm-manager.tsx` (report, fix a crate's block). API wrapper
  `src/services/api.ts` (`call("upande_avocado.<fn>")`), types in `src/types`.
- Backend logic: Server Scripts exported in the mobile repo `frappe/server_scripts.json`
  (`upande_avocado.get_farms`, `get_sections`, `get_blocks`, `get_team_leaders`, `get_harvestors`,
  `get_harvesting_state`, `scan_crate`, `scan_crates_bulk`, `mark_ready_for_collection`,
  `get_team_harvest_today`, `get_harvest_kpis`, `get_session_info`, `farm_manager_report`,
  `lookup_crate_for_fix`, `update_crate_block`, `bulk_create_crates`), doctypes in
  `frappe/doctypes.json` and the Frappe app `mark-judah/upande-avocado` (read-only clone at
  `/home/ubuntu/stive/code/frappe15_unused_apps/upande-avocado-backend`): Crate, Crate Allocation,
  Harvest Team, Harvest Team Member.

## Backend (in upande_production)

- Port the harvesting doctypes into module Production (names must not clash with ERPNext; prefix
  where generic, e.g. "Harvest Crate", "Harvest Crate Scan", "Harvest Team"). Map the harvest app's
  farm/section/block onto our Farm + Production Unit tree (block = a leaf Production Unit of a crop
  that harvests in crates: Avocado blocks, F&V slices).
- Whitelisted endpoints in `upande_production/mobile/harvest.py` with the **same function names and
  response shapes** the app expects (so the app only swaps the method prefix
  `upande_avocado.` → `upande_production.mobile.harvest.`).
- "Mark ready" closes a team's batch for a block → **Harvesting Stock Entry** (Stock Entry Type
  "Harvesting", purpose Material Receipt; created if missing) with one row per block: item = the
  block's current cycle item (variety), qty = crates × avg kg per crate (per item/crop setting,
  avocado 18 kg default), target warehouse = the farm's harvest warehouse (Production Settings),
  cost centre = the block's cost centre; links back to the batch. The same batch writes a
  **Production Harvest** (estimated actual) so Overview, Forecast, Block Costs and the avocado
  pages update, and **Value Adder Work** drafts for the pickers (operation "Harvesting", qty =
  crates, uom Crate, Pending approval) so harvest pay goes through the manager's approvals.
- Cancelling the batch cancels its stock entry and harvest.

## Mobile (upande-production)

- Rename to Upande Production / `com.upande.avocadoproduction`, its own scheme/slug, Production
  mark as icon/splash. Keep Configure + Harvesting + Farm Manager report; remove (not just hide)
  collecting, receiving, ops-room, weighing, packing, storage, dispatch, quality, export/non-export
  stock. Configure picks crop (Avocado / Fruits & Vegetables) → block. Point the API at
  `upande_production.mobile.harvest.*`. Offline queue kept.
