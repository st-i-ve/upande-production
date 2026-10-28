# Upande Production mobile: fleet base + supervisor planning

Date: 2026-10-28. Follows `2026-10-28-harvesting-and-mobile-design.md`.

## Decisions (user)

- Our app (`/home/ubuntu/stive/code/reactnative/upande-production`, repo
  `st-i-ve/st-i-ve-upande-production-mobile`, package `com.upande.avocadoproduction`) moves onto
  the **roses / Upande fleet base** — Mark's roses app
  `/home/ubuntu/stive/code/reactnative/upande-production-roses` (Expo SDK 54, `src/theme.ts`
  tokens, DM Sans body + Poppins headings, Ionicons only, its components and services; see its
  `AGENTS.md`). History of our repo is kept.
- **Biometric lock is optional**: off by default, a toggle in Settings turns it on (use the roses
  app's safe probe in `src/services/biometric.ts`; never block login when unavailable).
- **Multi-crop like SCP**: after login the supervisor picks a crop (Avocado / Fruits & Vegetables
  first; list comes from the backend so Aquaculture / Apiary appear when enabled); everything below
  is scoped to that crop; switchable from the drawer.
- Supervisor planning is built from the roses **Planning** tab (weekly plan list/detail, task
  sheet, add task, new plan) adapted to our model, plus what roses lacks:
  - crew on a task: several value adders, each with qty (and hours) — that is what pay needs;
  - tick-off is **Pending** until the manager approves; **Sent back** list with the manager's note,
    fix and **Resubmit**;
  - **protocol check** per block: this week's protocol steps — done, late, partial, skipped, or
    never planned (from the Active protocol version);
  - "assign work": add a task (operation, block, planned qty, due date) or record unplanned work.
- Harvesting (crate scan → close → Harvesting stock entry) is kept, restyled on the fleet base.

## Backend contract (upande_production)

Mobile endpoints live in `upande_production/mobile/` (`api.py` mona-style `production*` functions,
`harvest.py` for crates). Supervisor endpoints and their shapes are documented in
`upande_production/mobile/SUPERVISOR_API.md` (written by the backend builder): list crops, week
plan for a crop (+ block filter), task detail, tick-off with crew entries, add task, unplanned
work, sent back + resubmit, protocol check per block, value adders and operations for pickers.
