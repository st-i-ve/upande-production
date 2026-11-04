# Legacy pages → SCP-style frontends (Margin Par apps)

Date: 2026-11-04. User decision: every app (production, crop material planning, propagation) gets a
React frontend built exactly like Upande SCP's, the reference being
`/home/ubuntu/stive/code/frappe15/apps/upande_scp/frontend` (App.tsx, AppSidebar, PageHeader,
PageToolbar, DatePicker / DateRangePicker / WeekPicker, PlacePicker (farm picker), MapBase / maplibre,
recharts graphs, Loading skeletons, Poppins font, tokens in index.css, served by `www/scp_app.html`).
upande_production already has one built the same way (`frontend/`, served at `/production_app`) — copy
the shell from there or SCP, do not invent a new look.

Rules of the end state:
1. Every legacy screen below gets a React page with the same data and actions (same whitelisted
   endpoints; add endpoints only where a page needs one).
2. The legacy screens stay reachable (old routes keep working) — the React page links to the legacy one
   ("Classic view") and vice versa.
3. **Workspaces contain only a navigation Custom HTML Block of links** (tiles to the React pages and to
   the legacy pages) — no number cards, charts, dashboards or other blocks. Content moves into React.
4. Every Custom HTML Block and Web Page lives in the owning app's fixtures (one file per doctype:
   `fixtures/custom_html_block.json`, `fixtures/web_page.json`).
5. Desk → app crossing in the same tab (no target=_blank), behind the app's loader splash.

## Inventory (marginpar.local, 2026-11-04)

| App | Legacy screen | Kind | What it shows | React page |
|---|---|---|---|---|
| production | Production Navigation | Custom HTML Block (fixture) | per-crop launcher tiles | stays as the workspace's only block |
| production | Roses Production Navigation | Custom HTML Block (fixture) | roses launcher (setup, beds, planning, stock movement) | Roses home / sidebar of /production_app for flower crops |
| production | Crop Cycle Dashboard | Custom HTML Block (fixture) | plants standing, greenhouses, planted area, cycles, varieties; by farm; top varieties; cycles by status; greenhouse table | Roses Overview page (move off the workspace) |
| production | /production_app | www (React) | Mutara production app | add Margin Par flower crops (greenhouse → bed, stems) |
| production | /avocado-outlook, -labour, -calendar, -production, -maturity | www (Jinja) | avocado reports (Mutara) | already mirrored in the React app on Mutara; keep |
| planning | Crop Material Planning Navigation | Custom HTML Block (fixture) | launcher | stays as the workspace's only block |
| planning | /budget-forecast | www (Jinja + jspreadsheet) | Dashboard, Budget, Forecast, Lifetime, Weekly Plan, Farm Map, Crop Protocols, Greenhouses, Calibration | new `/planning_app`: one page per view (Weekly Plan / Farm Map / Greenhouses link to production's pages) |
| planning | production_budget | Desk Page | budget grid | `/planning_app` Budget page |
| propagation | Propagation Navigation | Custom HTML Block (fixture) | launcher | stays as the workspace's only block |
| propagation | Propagation workspace number cards + charts | Workspace content | batches, nursery, ready to dispatch, open requests, planted, sold, sales, losses; funnel; by stage; dispatch split | new `/propagation_app` Dashboard page; removed from workspace |
| propagation | propagation-dashboard | Web Page (DB only → export to fixture) | portal dashboard | `/propagation_app` page (keep portal route) |
| propagation | Propagation Traceability | Script Report | batch chain | `/propagation_app` Traceability page |
| propagation | doctypes: Propagation Batch, Seedling Request/Dispatch, Trough Setting, Plant Consignment, Flower Trial, Mother Block | lists/forms | | list + detail pages in `/propagation_app` |

Not ours: "T&A Dashboard" (upande_ta).

## Propagation reference branch
upande_propagation `marginpar` tracks `origin/james` (merged 699776c on 2026-11-04: plant consignments
from outside propagators, Trough Setting, plan feedback). Merge `origin/james` again before each phase.
