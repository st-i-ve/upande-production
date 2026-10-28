# Protocol approval and per-crop field logs

Date: 2026-10-28. Follows `2026-10-28-scp-design-parity-design.md` (design rules, primitives, working rules all still apply).

## Intent (user's words, paraphrased)

- Protocols need an approval process: a protocol is drafted, a manager approves it and it becomes
  Active; changing it later makes a new version that is approved again. Only Active protocols drive
  weekly plans. (Pattern: Marginpar propagation's "Crop Protocol Version" — version + version_status
  Active.)
- Avocado has its own logs and pages. Apiary, Aquaculture and Fruits & Vegetables must get their own
  field logs and pages the same way, so every crop's workspace is equally complete.
- Bees and fish have no crop cycles. (Hidden already for `apiary` and `aquaculture` in
  `frontend/src/lib/nav.ts` `NOT_FOR`; generic pages must not lean on cycles for them.)

## Protocol versions and approval

- Production Protocol gains: `version` (Int), `version_status` (Draft · Pending Approval · Active ·
  Superseded · Rejected), `protocol_family` (stable key shared by all versions of one protocol),
  `submitted_by/at`, `approved_by/at`, `review_note`, `previous_version` (Link Production Protocol).
- Flow: Draft → (supervisor/manager "Submit for approval") Pending Approval → manager Approve → Active
  (the previous Active version of the same family becomes Superseded) or Send back with a note →
  Draft (Rejected kept only if the manager rejects outright). Editing an Active protocol never edits
  it in place: "New version" copies it to a Draft with version+1.
- Only Active protocols generate plan tasks / are offered for crop cycles; cycles keep the version they
  were planned with.
- The manager approves on the Approvals page (new "Protocols" tab with a diff vs the previous version)
  and from Settings → Protocols (version list per family, status chips, actions).
- Desk: pending protocol approvals counted in the "Awaiting approval" strip.

## Field logs per crop

Doctype names must not collide with ERPNext/Frappe (no "Batch", "Inspection", "Quality Inspection").
Each log: doctype(s) + desk API in `api/<crop>.py` (envelope pattern) + mobile endpoints in
`mobile/api.py` style (supervisors record from the phone) + React page(s) + demo seed (idempotent,
one config dict) + tests. Logs link to Production Unit (hive group / pond / pivot block).

- **Apiary** (`apiary`): `Hive Inspection Log` (hive group unit, date, colonies inspected, queen seen,
  brood pattern, temperament, varroa count / mite load, frames of honey/brood, disease signs, feeding,
  actions, inspector) → page `hive-inspections`; `Honey Harvest Log` (unit, date, supers, frames,
  kg extracted, moisture %, grade) → page `honey-harvest`. Colony health trends, yield per hive.
- **Aquaculture** (`aquaculture`): `Pond Stocking` (the fish "batch": pond, species, date, count,
  avg weight g, source) with derived live count / biomass / FCR / survival → page `pond-batches`
  (replaces crop cycles for fish); `Water Quality Reading` (pond, time, DO mg/L, pH, temp °C,
  ammonia, nitrite, turbidity) with safe bands → page `water-quality`; `Pond Feeding Log` (pond, date,
  feed item, kg) and `Fish Mortality Log` (pond, date, count, cause) → page `feeding`
  ("Feeding & Mortality"); fish harvest uses Production Harvest (count + kg).
- **Fruits & Vegetables** (`fruits-vegetables`): `Pivot Irrigation Run` (pivot, start/end, hours,
  mm applied, pass %, slices covered, operator, fault) → page `irrigation`; `Harvest Grading Log`
  (block, crop item, date, crates/kg in, grade split (child table), rejects + reason) → page
  `grading`.

Routes/stubs exist (`frontend/src/pages/apiary/*`, `aquaculture/*`, `fruits-vegetables/*`); views are
registered in `router.ts`, labels in `crops.ts`, sidebar in `nav.ts` ("Field logs" group).
