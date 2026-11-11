# Supervisor API (mobile)

Backend for the mobile supervisor screens. All endpoints are in `upande_production/mobile/api.py`.

- **Call**: `POST /api/method/upande_production.mobile.api.<function>` with a JSON body, logged in
  (session cookie, or token auth). Every example below is the real response from the live site
  (Administrator) with long lists shortened.
- **Response**: always `{"data": ...}`. A refusal or validation problem is `{"data": {"error": "message"}}`
  (HTTP 200); show `data.error` to the user.
- **Pay**: `rate`, `default_rate` and `pay_value` are `null` unless the user has a pay role
  (Production Supervisor / Manager, System Manager). Hide the UI when they are `null`.
- **Crop scoping**: every call takes `crop` (a `name` from `productionListCrops`). Blocks are the crop's
  Production Units. `farm` is optional everywhere; omit it and the crop's plan for that week is used
  (a farm-less plan first, else the only plan that week). Pass `farm` from a list row to be explicit.
- **Weeks**: ISO `year` + `week`, both default to the current week. Dates are `YYYY-MM-DD`.
- **Approvals**: a tick-off creates **Pending** drafts. They count in `pending_qty` and only reach
  `done_qty` once a manager approves. A manager can send them back (**Sent Back**, with a note); the
  supervisor edits and resubmits.

Task `status` is one of `Open`, `In Progress`, `Done`, `Partly Done`, `Skipped`. `deviation` is `null`,
`Late`, `Partial` or `Skipped` (set once the task is ticked off). Crops without cycles (Apiary,
Aquaculture) have no protocol steps; plans, tasks and tick-off work the same.

## Screens and the calls behind them

| Screen | Calls |
|---|---|
| Crop picker | `productionListCrops` |
| Planning: week list | `productionListWeekPlans` |
| Planning: week detail (all blocks, or one) | `productionGetPlanDetail` |
| Task sheet: tick-off with crew | `productionUpdateTask`, pickers below |
| Assign work | `productionAddTask`, `productionGeneratePlan`, `productionRecordUnplannedWork` |
| Sent back | `productionListSentBack`, `productionResubmitWork` |
| Protocol check | `productionProtocolCheck` |
| Avocado fruit dry matter | `productionFruitTags`, `productionTagFruit`, `productionRecordFruitReading`, `productionUpdateFruitTag` |
| Pickers | `productionListUnits`, `productionListOperations`, `productionListCasualLabourers` |

## productionListCrops  (existing)

Enabled crops, in display order. Params: none.

```json
[
  {
    "name": "Avocado",
    "crop_name": "Avocado",
    "crop_key": "avocado",
    "accent_color": "#3f7d3a",
    "icon_key": "avocado",
    "unit_label": "Block",
    "sub_unit_label": "Row",
    "yield_uom": "Kg"
  },
  {
    "name": "Fruits & Vegetables",
    "crop_name": "Fruits & Vegetables",
    "crop_key": "fruits-vegetables",
    "accent_color": "#c0662b",
    "icon_key": "vegetables",
    "unit_label": "Block",
    "sub_unit_label": "Bed",
    "yield_uom": "Kg"
  }
]
```

## productionListUnits  (existing)

Active blocks of a crop (block picker, filter chips). Params: `crop` (required).

```json
[
  {
    "name": "Avocado Block A",
    "unit_name": "Avocado Block A",
    "unit_type": "Orchard Block",
    "farm": "Mutara",
    "is_group": 0,
    "parent_production_unit": null,
    "area_ha": 6.5,
    "plant_count": 1040
  }
]
```

## productionListWeekPlans  (new)

Plans of a crop, newest week first, with task counts. Params: `crop` (required), `farm`, `year`
(restrict to a year), `limit` (default 26). `current_plan` is the plan name of the current ISO week, or
`null` when that week has no plan yet (offer "Generate from protocols" / "Add task", which create it).

Counts: `tasks_open` = Open + In Progress; `tasks_done` = Done + Partly Done + Skipped;
`tasks_pending_approval` = tasks holding unapproved crew entries; `tasks_late` = still open and past due,
or finished late.

```json
{
  "crop": "Avocado",
  "current_year": 2026,
  "current_week": 44,
  "plans": [
    {
      "name": "PLAN-2026-00021",
      "farm": "Mutara",
      "plan_year": 2026,
      "plan_week": 44,
      "week_start": "2026-10-26",
      "week_end": "2026-11-01",
      "tasks_total": 3,
      "tasks_open": 2,
      "tasks_done": 1,
      "tasks_pending_approval": 0,
      "tasks_late": 1,
      "is_current": true
    },
    {
      "name": "PLAN-2026-00020",
      "farm": "Mutara",
      "plan_year": 2026,
      "plan_week": 43,
      "week_start": "2026-10-19",
      "week_end": "2026-10-25",
      "tasks_total": 2,
      "tasks_open": 0,
      "tasks_done": 2,
      "tasks_pending_approval": 1,
      "tasks_late": 0,
      "is_current": false
    }
  ],
  "current_plan": "PLAN-2026-00021"
}
```

## productionGetPlanDetail  (new)

One week's plan, tasks grouped by block. Params: `crop` (required), `year`, `week`, `farm`,
`unit` (only that block), `mine` (true: only tasks whose supervisor is the Employee linked to the
logged-in user via `Employee.user_id`; a user with no Employee gets nothing; response carries `mine` and
`employee`; `productionListWeekPlans` accepts `mine` too and counts only those tasks). No plan for the week gives `plan: null` and `blocks: []`.

Per task: `planned_qty` + `uom`, `done_qty` (approved), `pending_qty` (awaiting approval), `due_date`,
`status`, `deviation`, `is_late`, `supervisor` / `supervisor_name`, `protocol_ref` + `from_protocol`
(tasks generated from a protocol), and `entries`: every crew entry recorded so far, with
`approval_status` (`Pending`, `Sent Back`, `Approved`) and the manager's `review_note`.
Block and plan level counts use the same meaning as in the list. Example (week 45, first block shown):

```json
{
  "plan": "PLAN-2026-00038",
  "crop": "Avocado",
  "farm": null,
  "year": 2026,
  "week": 45,
  "week_start": "2026-11-02",
  "week_end": "2026-11-08",
  "unit": null,
  "tasks_total": 3,
  "tasks_open": 2,
  "tasks_done": 1,
  "tasks_pending_approval": 1,
  "tasks_late": 0,
  "blocks": [
    {
      "unit": "Avocado Block A",
      "unit_name": "Avocado Block A",
      "tasks": [
        {
          "name": "ji3n4omto4",
          "unit": "Avocado Block A",
          "cycle": "CYC-2026-0001",
          "operation": "OP-00004",
          "operation_name": "Irrigation Check",
          "planned_qty": 6.0,
          "done_qty": 0.0,
          "pending_qty": 0.0,
          "uom": "Hectare",
          "rate": 150.0,
          "due_date": "2026-11-03",
          "supervisor": null,
          "status": "Open",
          "deviation": null,
          "note": null,
          "protocol_ref": "CYC-2026-0001:djtncsmtrq:13",
          "started_at": null,
          "completed_at": null,
          "supervisor_name": null,
          "is_late": false,
          "entries": [],
          "from_protocol": true
        },
        {
          "name": "ji4mruckab",
          "unit": "Avocado Block A",
          "cycle": "CYC-2026-0001",
          "operation": "OP-00005",
          "operation_name": "Weeding",
          "planned_qty": 4.0,
          "done_qty": 0.0,
          "pending_qty": 2.25,
          "uom": "Hectare",
          "rate": 1200.0,
          "due_date": "2026-11-04",
          "supervisor": "HR-EMP-00324",
          "status": "Partly Done",
          "deviation": "Partial",
          "note": "Rain stopped work",
          "protocol_ref": null,
          "started_at": "2026-10-28 19:23:09.362660",
          "completed_at": "2026-10-28 19:23:09.362660",
          "supervisor_name": "Grace Wairimu",
          "is_late": false,
          "entries": [
            {
              "name": "VAW-2026-00413",
              "employee": "HR-EMP-00300",
              "employee_name": "Wanjiru Kamau",
              "qty": 1.25,
              "uom": "Hectare",
              "work_date": "2026-10-28",
              "pay_value": 1500.0,
              "approval_status": "Pending",
              "review_note": "Please recount the trees pruned along the south boundary."
            },
            {
              "name": "VAW-2026-00414",
              "employee": "HR-EMP-00301",
              "employee_name": "Otieno Odhiambo",
              "qty": 1.0,
              "uom": "Hectare",
              "work_date": "2026-10-28",
              "pay_value": 1200.0,
              "approval_status": "Pending",
              "review_note": "Please recount the trees pruned along the south boundary."
            }
          ],
          "from_protocol": false
        }
      ],
      "tasks_total": 2,
      "tasks_open": 1,
      "tasks_done": 1,
      "tasks_pending_approval": 1,
      "tasks_late": 0
    }
  ]
}
```

## productionGetWeekPlan  (existing, flat)

Flat task list of the week with no crew entries. Prefer `productionGetPlanDetail`. Params: `crop`
(required), `farm`, `year`, `week`.

```json
{
  "plan": null,
  "farm": null,
  "crop": "Avocado",
  "year": 2026,
  "week": 44,
  "week_start": "2026-10-26",
  "week_end": "2026-11-01",
  "tasks": []
}
```

## productionUpdateTask  (existing, verified and extended)

Tick a task off with a crew. Params: `plan`, `task` (the task `name`), `status` (see above),
`note` (optional), `entries`: `[{"employee", "qty"}]`. Several entries are supported; each
becomes one Pending draft (`qty` must be > 0). Pay is per unit of work (qty x the operation's rate per unit); there is no
hourly pay, and a legacy `hours` key from an old app is ignored. Entries may be empty (for
In Progress / Skipped). Entries need create permission on Casual Labour Work; the call checks it.
The response carries the refreshed `task` (with new `pending_qty`) and, new, `entries`: all crew
entries of the task so the screen can redraw without a second call.

```json
{
  "status": "success",
  "task": {
    "name": "ji4mruckab",
    "unit": "Avocado Block A",
    "cycle": "CYC-2026-0001",
    "operation": "OP-00005",
    "operation_name": "Weeding",
    "planned_qty": 4.0,
    "done_qty": 0.0,
    "pending_qty": 2.5,
    "uom": "Hectare",
    "rate": 1200.0,
    "due_date": "2026-11-04",
    "supervisor": "HR-EMP-00324",
    "status": "Partly Done",
    "deviation": "Partial",
    "note": "Rain stopped work"
  },
  "entries": [
    {
      "name": "VAW-2026-00413",
      "employee": "HR-EMP-00300",
      "employee_name": "Wanjiru Kamau",
      "qty": 1.5,
      "uom": "Hectare",
      "work_date": "2026-10-28",
      "pay_value": 1800.0,
      "approval_status": "Pending",
      "review_note": null
    },
    {
      "name": "VAW-2026-00414",
      "employee": "HR-EMP-00301",
      "employee_name": "Otieno Odhiambo",
      "qty": 1.0,
      "uom": "Hectare",
      "work_date": "2026-10-28",
      "pay_value": 1200.0,
      "approval_status": "Pending",
      "review_note": null
    }
  ],
  "work": [
    "VAW-2026-00413",
    "VAW-2026-00414"
  ],
  "approval_status": "Pending",
  "message": "Weeding marked Partly Done. Work awaits manager approval."
}
```

## productionAddTask  (new)

Assign work: add a planned task to a week. The week's plan is created when it does not exist.
Params: `crop`, `unit` (block of the crop), `operation` (an operation of the crop), `planned_qty` (> 0),
all required; `year`, `week`, `farm`, `due_date` (must fall inside the week; defaults to the Monday),
`supervisor` (Employee name), `note`. The uom and rate come from the operation, the cycle from the block's
active cycle. Task starts `Open`.

```json
{
  "status": "success",
  "plan": "PLAN-2026-00038",
  "task": {
    "name": "jt0agk62l3",
    "unit": "Avocado Block A",
    "cycle": "CYC-2026-0001",
    "operation": "OP-00005",
    "operation_name": "Weeding",
    "planned_qty": 4.0,
    "done_qty": 0,
    "pending_qty": 0,
    "uom": "Hectare",
    "rate": 1200.0,
    "due_date": "2026-11-04",
    "supervisor": "HR-EMP-00324",
    "status": "Open",
    "deviation": null,
    "note": "Along the south boundary",
    "protocol_ref": null,
    "started_at": null,
    "completed_at": null
  },
  "message": "Weeding added to week 45."
}
```

Error example: `{"data": {"error": "Due date must fall in week 45 (2026-11-02 to 2026-11-08)."}}`

## productionGeneratePlan  (new)

Generate the week's tasks from the active cycles' protocols (idempotent: steps already planned are
skipped). Params: `crop` (required), `year`, `week`, `farm`. `created` is the number of tasks added;
when it is 0 `reason` says why (crop without cycles, or everything already planned).

```json
{
  "status": "success",
  "plan": "PLAN-2026-00038",
  "created": 2,
  "reason": null,
  "message": "2 task(s) generated from protocols."
}
```

## productionRecordUnplannedWork  (existing)

Work done that nobody planned. Params: `unit`, `operation`, `entries` (`[{employee, qty}]`)
required; `work_date` (default today). Creates Pending drafts with no plan task.

```json
{
  "status": "success",
  "work": [
    "VAW-2026-00415"
  ],
  "approval_status": "Pending",
  "message": "1 work record(s) saved, awaiting manager approval."
}
```

## productionListSentBack  (existing, verified)

Work the manager sent back. A supervisor sees their own, a manager sees all. Params: `crop`, `from_date`,
`to_date` (all optional). One group per task (or per block + operation + day for unplanned work);
`names` are the work records, `entries` carry the editable qty, `review_note` is the manager's note.

```json
{
  "groups": [
    {
      "key": "ji4mruckab::Administrator::Sent Back",
      "status": "Sent Back",
      "crop": "Avocado",
      "unit": "Avocado Block A",
      "unit_name": "Avocado Block A",
      "operation": "OP-00005",
      "operation_name": "Weeding",
      "plan": "PLAN-2026-00038",
      "plan_year": 2026,
      "plan_week": 45,
      "plan_task": "ji4mruckab",
      "task_planned_qty": 4.0,
      "task_done_qty": 0.0,
      "task_pending_qty": 0.0,
      "task_status": "Partly Done",
      "note": "Rain stopped work",
      "unplanned": 0,
      "uom": "Hectare",
      "work_date": "2026-10-28",
      "submitted_by": "Administrator",
      "submitted_by_name": "Administrator",
      "created": "2026-10-28 19:23:09.324803",
      "age_days": 0,
      "stale": false,
      "total_qty": 2.5,
      "total_pay": 3000.0,
      "review_note": "Please recount the trees pruned along the south boundary.",
      "reviewed_by": "Administrator",
      "reviewed_at": "2026-10-28 19:23:14.687155",
      "names": [
        "VAW-2026-00413",
        "VAW-2026-00414"
      ],
      "entries": [
        {
          "name": "VAW-2026-00413",
          "employee": "HR-EMP-00300",
          "employee_name": "Wanjiru Kamau",
          "qty": 1.5,
          "uom": "Hectare",
          "rate": 1200.0,
          "pay_value": 1800.0,
          "work_date": "2026-10-28",
          "approval_status": "Sent Back",
          "review_note": "Please recount the trees pruned along the south boundary."
        },
        {
          "name": "VAW-2026-00414",
          "employee": "HR-EMP-00301",
          "employee_name": "Otieno Odhiambo",
          "qty": 1.0,
          "uom": "Hectare",
          "rate": 1200.0,
          "pay_value": 1200.0,
          "work_date": "2026-10-28",
          "approval_status": "Sent Back",
          "review_note": "Please recount the trees pruned along the south boundary."
        }
      ]
    }
  ],
  "count": 1
}
```

## productionResubmitWork  (existing, verified)

Resubmit sent-back work, optionally with edits. Params: `names` (list of work record names, required),
`entries`: `[{"name", "qty", "employee"}]` to correct individual records (the `name` must be one
of `names`; omit to resubmit unchanged). They go back to Pending.

```json
{
  "status": "success",
  "approval_status": "Pending",
  "work": [
    "VAW-2026-00413",
    "VAW-2026-00414"
  ],
  "message": "2 work record(s) resubmitted for approval."
}
```

## productionProtocolCheck  (new)

For a crop's week (every block with an active cycle) or one block: each protocol step due that week
for the block's cycle, with its plan status. Built on the same step/due-date logic as the desk deviations.
Params: `crop` (required), `year`, `week`, `unit` (a block; omit for the whole crop).

Step `status`:

| status | meaning |
|---|---|
| `done` | ticked off and fully approved, on time |
| `partial` | Partly Done, or approved qty below planned |
| `late` | done after the due date (beyond tolerance), or still open and past due |
| `skipped` | marked Skipped |
| `pending_approval` | ticked off, crew entries still await the manager |
| `open` | planned, not done, not yet due |
| `not_planned` | due this week but never put on a plan (`plan` / `task` are `null`; `planned_qty` is the protocol's) |

`totals` counts steps per status and gives `planned_qty_by_uom` / `done_qty_by_uom` (never summed across
units of measure). Each block also has its own `counts`. A step is matched to its plan task by `protocol_ref`
(`<cycle>:<step>:<repeat>`), wherever the task was planned. Crops without cycles (Apiary, Aquaculture), or
weeks with nothing due, return `blocks: []` with a human `reason`; never an error.

```json
{
  "crop": "Avocado",
  "year": 2026,
  "week": 44,
  "week_start": "2026-10-26",
  "week_end": "2026-11-01",
  "unit": "Avocado Block B",
  "reason": null,
  "blocks": [
    {
      "unit": "Avocado Block B",
      "unit_name": "Avocado Block B",
      "cycle": "CYC-2026-0002",
      "protocol": "Avocado Season",
      "protocol_version_status": "Active",
      "steps": [
        {
          "protocol_ref": "CYC-2026-0002:djtncsmtrq:14",
          "operation": "OP-00004",
          "operation_name": "Irrigation Check",
          "due_date": "2026-10-26",
          "status": "partial",
          "planned_qty": 6.0,
          "done_qty": 0.0,
          "pending_qty": 0.0,
          "uom": "Hectare",
          "plan": "PLAN-2026-00021",
          "task": "sej79qar4e",
          "task_status": "Done",
          "note": null
        },
        {
          "protocol_ref": "CYC-2026-0002:djt9lg4deb:3",
          "operation": "OP-00003",
          "operation_name": "Fertiliser Application",
          "due_date": "2026-11-01",
          "status": "open",
          "planned_qty": 300.0,
          "done_qty": 0.0,
          "pending_qty": 0.0,
          "uom": "Tree",
          "plan": "PLAN-2026-00021",
          "task": "sejdpe97vb",
          "task_status": "Open",
          "note": null
        }
      ],
      "counts": {
        "done": 0,
        "partial": 1,
        "late": 0,
        "skipped": 0,
        "pending_approval": 0,
        "open": 1,
        "not_planned": 0
      }
    }
  ],
  "totals": {
    "steps": 2,
    "done": 0,
    "partial": 1,
    "late": 0,
    "skipped": 0,
    "pending_approval": 0,
    "open": 1,
    "not_planned": 0,
    "planned_qty_by_uom": [
      {
        "uom": "Tree",
        "qty": 300.0
      },
      {
        "uom": "Hectare",
        "qty": 6.0
      }
    ],
    "done_qty_by_uom": [
      {
        "uom": "Hectare",
        "qty": 0.0
      },
      {
        "uom": "Tree",
        "qty": 0.0
      }
    ]
  }
}
```

Crop without cycles:

```json
{
  "crop": "Apiary",
  "year": 2026,
  "week": 44,
  "week_start": "2026-10-26",
  "week_end": "2026-11-01",
  "unit": null,
  "reason": "This crop does not run in crop cycles, so it has no protocol steps.",
  "blocks": [],
  "totals": {
    "steps": 0,
    "done": 0,
    "partial": 0,
    "late": 0,
    "skipped": 0,
    "pending_approval": 0,
    "open": 0,
    "not_planned": 0,
    "planned_qty_by_uom": [],
    "done_qty_by_uom": []
  }
}
```

## productionListOperations  (existing, verified)

Operations of the crop only (filter is on `crop`; `crop` required). `default_rate` is `null` without a pay
role. `is_harvest` operations are the harvest ones. `activity_type` (Capital, Planting, Key activity, Cultural,
Harvesting, Uprooting) and `color` (hex or null) tag each operation.

```json
[
  {
    "name": "OP-00003",
    "operation_name": "Fertiliser Application",
    "category": "Fertilising",
    "work_uom": "Tree",
    "default_rate": 10.0,
    "is_harvest": 0,
    "activity_type": "Cultural",
    "color": "#3f7d3a"
  },
  {
    "name": "OP-00006",
    "operation_name": "Fruit Count",
    "category": "Weeding",
    "work_uom": "Tree",
    "default_rate": 5.0,
    "is_harvest": 0
  }
]
```

## productionListCasualLabourers  (existing, extended)

Renamed from `productionListValueAdders` (Value Adders are now Casual Labourers). The old name still resolves through
`override_whitelisted_methods` for one release; responses have no renamed keys, so nothing else changes.

Active employees with the Casual Labourer designation (the crew picker). The list is company-wide (an Employee
has no crop). New optional params: `search` (matches name or id) and `limit`.

```json
[
  {
    "name": "HR-EMP-00318",
    "employee_name": "Achieng Awino"
  },
  {
    "name": "HR-EMP-00302",
    "employee_name": "Akinyi Onyango"
  },
  {
    "name": "HR-EMP-00308",
    "employee_name": "Atieno Ouma"
  }
]
```


## Activity rules (stage and calendar restrictions)

Production Activity Rules forbid (`Block`) or frown on (`Warn`) an operation in a growth stage or window
(e.g. no spraying 14 days before harvest, no weeding in Tuber initiation, no picking within 7 days after
spraying). They are checked on `productionAddTask`, `productionUpdateTask` (when work is recorded or the task
is started/done) and `productionRecordUnplannedWork`, and when plan tasks are generated.

- New optional param `override_reason` on `productionAddTask`, `productionUpdateTask` (also now accepts
  `work_date`) and `productionRecordUnplannedWork`.
- `Block`: nothing is saved; response is `{"error": "<message for the supervisor>", "breaches": [...],
  "rule_status": "Block", "needs_override_reason": false}`.
- `Warn` without a reason: nothing is saved; same shape with `"rule_status": "Warn"` and
  `"needs_override_reason": true`. Ask for a reason and resend with `override_reason`.
- A breach is `{rule, rule_type, enforcement, message}`.
- Protocol buffers are rules too, always `Warn` (a reason is required; the breach is flagged in Approvals). `rule` is
  `protocol:<row name>` and `rule_type` is `Establishment period` ("Spraying is in week 2; the protocol's establishment
  period is 3 weeks after planting.", or "after the last harvest" from the second cycle on) or `Pre-harvest interval`
  ("Spraying is planned 9 days before harvest; the protocol's pre-harvest interval is 14 days."). No expected harvest
  date means no pre-harvest check. Activities the protocol schedules inside the interval are not planned at all.
- Tasks now carry `rule_status` (OK / Warn / Block, empty on old rows), `rule_notes` and `override_reason`
  (in every task list: week plan, plan detail, add task, update task). A task keeps its reason, so closing it
  later needs no new one.
- Work records carry the same three fields; Approvals cards and entries (`rule_status`, `rule_notes`,
  `override_reason`) show them to the manager.
- `productionGeneratePlan` adds `skipped`: `[{protocol_ref, unit, cycle, operation, due_date, message}]`, the
  protocol steps an activity rule blocked (not planned; also noted as a comment on the plan). Warn steps are
  planned with `rule_status: "Warn"`.
- `productionProtocolCheck`: each block has `breaches` (`[{rule, rule_type, enforcement, message, operation,
  operation_name, due_date}]`) and each step has `rule_status` and `breaches`.
- Operation `category` is one list: Spraying, Weeding, Fertilising, Irrigation, Harvesting, Pruning, Feeding, Other.

## Stage and pre-harvest fields

`productionListUnits` rows, `productionGetPlanDetail` blocks and tasks, and `productionProtocolCheck`
blocks carry, from the unit's open (Active / Harvesting) cycle:

| field | meaning |
|---|---|
| `variety` | the cycle's Production Variety |
| `current_stage` | the variety stage the cycle is in today |
| `stage_day` | days into that stage (0 = first day) |
| `days_to_harvest` | days until harvest starts; negative once harvest is under way |
| `pre_harvest_days` | the longest "Not within days before harvest" rule for the variety (e.g. no spraying for 21 days) |
| `in_pre_harvest` | `true` when `days_to_harvest <= pre_harvest_days` — restricted work (spraying etc.) will be refused or warned |

Example (Avocado Block A, Hass): `{"variety": "Hass", "current_stage": "Harvest", "days_to_harvest": -35, "pre_harvest_days": 21, "in_pre_harvest": true}`.

## productionDryMatterTests  (read only)

Dry matter tests of a crop that tests dry matter (the crop's default is on, or one of its varieties says Yes;
not avocado, which keeps its Maturity Test), newest first (max 500). Whether to test, on which part, to what target and
from which stage is set per variety (the crop is the default). Retired blocks are left out. Params: `crop` (required), `unit` (optional). Tests are entered on the desk.

```json
[
  {
    "name": "DMT-2026-00001",
    "unit": "Block A",
    "cycle": "CYC-0001",
    "crop": "Mango",
    "variety": "Tommy",
    "test_date": "2026-10-05",
    "tested_on": "Fruit",
    "stage": "Maturity",
    "tested_by": "user@example.com",
    "avg_pct": 21.83,
    "target_pct": 21.0,
    "ready": true,
    "samples": [{"sample_no": 1, "dry_matter_pct": 20.0}, {"sample_no": 2, "dry_matter_pct": 23.5}]
  }
]
```

`stage` is the cycle's growth stage on the test date (null without a cycle or a variety timeline); `tested_on` is
Fruit, Tuber, Bulb, Head or Leaf. `ready` is average at or above target (variety target, else crop target). Missing `crop` fails with an error;
no read permission on Dry Matter Test is a permission error.

## Avocado tagged-fruit dry matter  (new)

Monitor one tagged fruit over time. A tree is a block plus a tree label (e.g. `R12-T7`); a fruit is a tag number on
that tree. Each reading holds either or both methods:

- microwave: `fresh_g`, `dry_g` (grams, after microwave drying) and optional `dish_g` (tare, taken off both). The server
  works out `microwave_pct = (dry - dish) / (fresh - dish) x 100`; the phone sends weights, never the percentage.
- machine: `machine_pct`, straight off the dry matter meter, optional `instrument`.

`dm_pct` is the value that drives the trend and "ready": the average of the two when both were used, else the one that was.
`ready` on a fruit is its latest `dm_pct` at or above the crop's export target. Readings cannot be dated in the future or before
the tag date, a dry weight cannot exceed the fresh weight, and a result outside 5 to 60 % is refused as a slip.
Rights are document rights on Dry Matter Fruit Tag (read, create, write); a user without them gets a permission error.

### productionFruitTags  (read)
Params: `crop` (required), `unit` (optional). Returns `{target_pct, max_pct, tags: [...], series: {unit: {points, projection, fruit}}}`.
`series` is each block's weekly average of its tagged fruit (`points`: `date` is the week's Monday, `dm_pct`, `microwave_pct`,
`machine_pct`, `fruit`), and `projection` is a straight line through the last readings: `{state: reached|rising|flat|few|far|none, date,
slope_per_week}`.

```json
{"name": "DMF-00001", "unit": "Avocado Block A", "farm": "Mutara", "variety": "Hass", "tree_label": "R12-T7", "fruit_tag": "3",
 "tagged_on": "2026-10-20", "status": "Active", "latest_pct": 22.35, "latest_on": "2026-11-03", "ready": false,
 "readings": [{"name": "abc123", "reading_date": "2026-11-03", "method": "Both", "fresh_g": 24.5, "dish_g": 4.5, "dry_g": 10.2,
   "microwave_pct": 28.5, "machine_pct": 22.0, "instrument": "NIR-1", "dm_pct": 25.25, "recorded_by": "user@example.com", "notes": null}]}
```

### productionTagFruit  (new)
Params: `unit`, `tree_label`, `fruit_tag` (required), `tagged_on` (default today), `notes`, `reading` (optional first reading, same keys
as below). A tag number is unique on its tree in a block (duplicate = error). Returns the tag.

### productionRecordFruitReading  (new)
Params: `tag` (the tag name), `reading_date` (required), then the microwave weights and/or `machine_pct` (at least one method), `instrument`, `notes`.
Returns the tag with the new reading computed.

### productionUpdateFruitTag  (new)
Params: `tag`, `status` (`Active`, `Harvested` or `Lost`) and/or `notes`. Returns the tag.

## Harvest store (mark ready for collection)

Harvested crates are received into a store chosen when the batch is closed (never a block warehouse).

`upande_production.mobile.harvest.get_stores(block=None)` returns
`{"data": [{"name": "Mutara Harvest Store - MUT", "label": "Mutara Harvest Store"}], "default": "Mutara Harvest Store - MUT"}`.
`default` is the last store used for the block's farm, else the harvest warehouse in Production Settings.

`mark_ready_for_collection(block, team_id, warehouse=None)` posts the Harvesting stock entry into `warehouse`
(default as above) and returns the usual fields plus `warehouse`. A block warehouse, group, disabled or
other-company warehouse is refused with `{"error": ...}` and the crates stay open.


## Daily targets (a yardstick; never changes pay)

* `productionListOperations` rows carry `daily_target` and `target_uom` (the operation's default per person per day).
* `productionGetWeekPlan` / `productionGetPlanDetail` tasks carry `daily_target` and `target_uom` for their operation.
* `productionListCasualLabourers` rows: `{name, employee_name, targets}` where `targets` is
  `{operation: {target, uom}}`, the person's own overrides. Only active roster labourers (plus employees
  designated Casual Labourer that are not on the roster at all) are listed.
* Crew entries on a task carry `target`, `target_uom`, `day_qty` (that person's total that day for the operation)
  and `target_met` (true / false, null when there is no target).
* The app shows the target next to the quantity: the person's override for the task's operation, else the task's
  `daily_target`.

## Machine allocation by QR scan  (new)

Endpoints are in `upande_production/mobile/asset_allocation.py`
(`POST /api/method/upande_production.mobile.asset_allocation.<function>`), same envelope as above.

Every Production Machine has a label whose QR code encodes a link,
`https://<site>/production_app?machine=<TOKEN>#/_/scan`. Send whatever the scanner read as `code`: the
link or the bare token (typed by hand from the label) both work.

**GPS is read once, at the moment the QR code is scanned**, never in the background. Send that fix with the
start or close call: `latitude`, `longitude`, `accuracy` (metres) and `scanned_at` (`YYYY-MM-DD HH:MM:SS`,
when the scan happened; default now). All optional: a user who refuses location still allocates the
machine. Half a fix, (0, 0) or an off-globe position is refused.

| Screen | Calls |
|---|---|
| Machine list | `productionListMachines` |
| Scan | `productionScanMachine` then `productionStartAllocation` or `productionCloseAllocation` |
| Start sheet pickers | `productionAllocationForm` |
| History | `productionListAllocations` |

### productionScanMachine
Params: `code`. Returns `{"machine": {name, machine_name, machine_type, fuel_item, qr_code, last_latitude,
last_longitude, last_seen_at, ...}, "open_allocation": {...} | null}`. With an open allocation the scan
closes it; without one it starts one. A disabled or unknown machine is `{"error": ...}`.

### productionStartAllocation
Params: `code`, `operator` (Employee, required), `allocated_to` (`Feedlot` · `Production Unit` ·
`Silage Cycle` · `Other`, default Feedlot), `reference_doctype` / `reference_name` (a Production Unit or
a Silage Cycle), `cost_center` (default: the reference's, else the Feedlot Cost Center in Production
Settings for the feedlot, else the machine's default), the GPS fix, `notes`. A machine already allocated is
refused (one open allocation per machine). Returns `{status, name, allocation, message}`.

### productionCloseAllocation
Params: `code` (or `allocation`), the GPS fix of the closing scan, `diesel_litres` (in the fuel item's stock
UOM), `notes`, `submit` (1 to post now; needs the submit right, Production Manager, which
`productionAllocationForm` reports as `can_submit`; a supervisor closes and a manager posts). Submitting issues the diesel from the Fuel Warehouse as a Material
Issue on the allocation's cost centre; `diesel_cost` is that Stock Entry's value.

### productionListAllocations
Params: `from_date`, `to_date`, `status` (`Open` · `Closed` · `Posted` · `Cancelled`), `machine`,
`allocated_to`. Open allocations are always listed; rows carry `running_hours` while open.

### productionListMachines / productionAllocationForm
Machines with `open_allocation` and last position; the start sheet's `employees`, `me` (the user's own
Employee), `allocated_to`, `references` (`{"Production Unit": [...], "Silage Cycle": [...]}`),
`cost_centers`, `settings` (`fuel_warehouse`, `feedlot_cost_center`) and rights (`can_allocate`,
`can_submit`).
