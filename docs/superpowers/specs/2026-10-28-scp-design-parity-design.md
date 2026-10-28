# Production app: SCP design parity, approvals, coverage map, avocado forecast pages

Date: 2026-10-28. Demo is imminent: working and polished beats exhaustive.

## Intent

Upande Production (`/production_app`, React in `frontend/`) must look and behave like
Upande SCP (kaitet branch), and the manager uses the desktop mainly to **approve** what
supervisors key in. Each crop is its own world: entering Avocado from the desk shows only
Avocado (no crop list in the sidebar). teddy's standalone avocado pages (`/avocado-*`)
are rebuilt inside our app in our design; nothing links out.

## Reference (read-only — never edit)

- SCP repo, kaitet branch: `/home/ubuntu/stive/code/frappe15/apps/upande_scp`
  - frontend: `frontend/src` — components (`PageHeader`, `PageToolbar`, `FilterSelect`,
    `DateRangePicker`, `TogglePill`, `ClearFiltersPill`, `SearchInput`, `TreePicker`,
    `Toast`, `Loading`, `maps/MapPanelDock`, `maps/MapFloatingCard`, `MapBase`), pages,
    `index.css` tokens.
  - UI commits Sep–Oct 2026: `git -C <repo> log --since=2026-09-01 --oneline` (scp-ui,
    scp-maps, scp-dashboard, scp-approvals). Read the diffs of the ones relevant to you.
  - logo: `scripts/build_scp_logo.py`, `upande_scp/public/js/scp_logo_motion.js`,
    `upande_scp/public/images/scp_logo*.svg`, `www/scp_app.html` splash.
- Livestock did the same logo pattern: `/mnt/data/code/frappe16-mutara/apps/upande_livestock`
  (`scripts/build_livestock_logo.py`, `public/js/livestock_logo_motion.js`).
- teddy's avocado pages: `upande_production/www/avocado-*.html` + `avocado_*.py`, backend in
  `upande_production/avocado_yield/`.

## Design rules (from SCP Sep–Oct UI commits)

- Poppins everywhere; tabular figures for numbers (no mono font for IDs/figures).
- Page header: eyebrow (thin rule + uppercase letter-spaced crop/area) + large title; one-row
  toolbar under it: tabs as pills on the left, filters as pill dropdowns on the right
  (`FilterSelect`, `DateRangePicker`, refresh), red "Clear" text when filters are set.
- No native `<select>` or date inputs. Searchable pills for pickers.
- Cards: white, rounded, soft shadow; KPI cards with label (uppercase small), big figure,
  sub-line, sparkline in UFD style where a trend exists.
- In-place skeletons: the page frame paints immediately, data slots pulse. No full-page spinners.
- Floating desk-style toasts.
- Maps: one format — full width, floating panels docked bottom-right (`MapPanelDock`),
  KPI pill on top, small ⓘ credit bottom-left.
- Crop accent colour from `Production Crop.accent_color` used for highlights (avocado
  `#3f7d3a`); ink/paper neutrals as in SCP otherwise.

## Parts

1. **Shell & design primitives** — port SCP primitives into `frontend/src/components/`,
   restyle sidebar/header to SCP, then restyle existing pages (Overview, Blocks, Cycles,
   Plan, Value Adders, Costs, Forecast, Settings) to them; make pages more detailed.
2. **Approvals** — supervisor-keyed work no longer counts on save. Value Adder Work saved as
   draft with `approval_status` = Pending; manager approves (submit → counts toward
   done_qty / pay / costs) or sends back with a note (`Sent Back`); supervisor fixes and
   resubmits (back to Pending). Applies to desk API tick-off and mobile API. Approvals page
   like SCP's: Pending / Approved / Sent back tabs, date range, bulk-approve floating pill,
   detail per entry (block, task, people, qty, pay). Plan task shows pending vs approved
   quantities. Desk workspace block shows pending count per crop.
3. **Coverage map** — MapLibre map of the crop's units (pivots/slices, orchard blocks)
   coloured by this week's plan progress (done / partial / not started / late / pending
   approval), filters (week, operation, status, farm), floating panel with work remaining
   per block. Demo units get simulated geojson near the Mutara farm.
4. **Avocado forecast pages** — Season Outlook, Block Forecast (teddy's "Production
   Forecast / Forecast & Blocks"), Harvest Calendar, Picking Plan (labour), Dry Matter
   (maturity). JSON endpoints for what the jinja pages computed; React pages in our design
   with all their content (KPIs, timeline, treemap, yield curve, tables, losses, gaps).
5. **Logo** — Production's own animated mark like SCP's: rest = Upande mark, hover plays a
   vector scene (avocado harvest), on the desk apps-screen tile (motion JS) and in the app
   sidebar + splash.

## Shared ground already in place (commit 77f7f9a)

- Routes: `frontend/src/lib/router.ts` VIEWS include `approvals`, `map`, `outlook`,
  `block-forecast`, `harvest-calendar`, `picking-plan`, `dry-matter`; stub pages exist.
- Sidebar groups: `frontend/src/lib/nav.ts` (`navForCrop`, avocado-only views).
- `maplibre-gl` and `recharts` installed.

## Working rules for builders

- Own only your files (listed in your brief). API calls for your part go in your own module
  (`src/lib/<part>-api.ts`), not `src/lib/api.ts`.
- Do not run `vite build`/`npm run build` and do not commit — the lead builds and commits.
  Check with `npx tsc -b` and `npx vitest run <your tests>`.
- Backend tests: `cd /mnt/data/code/frappe16-mutara && bench --site mutara.local run-tests --app upande_production --module <module>`.
- Never name a doctype or field after an ERPNext one. Never touch other sites/databases.
- Pay figures stay hidden from viewers (`can_see_pay`).
