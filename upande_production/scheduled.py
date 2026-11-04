"""Nightly field-execution jobs: stale buckets and the weekly plan-task harvest rollup.

The forecast/projection rollups (rollup_actuals, forecast actuals refresh) belong to
upande_crop_material_planning, which schedules its own job.
"""

import datetime

import frappe


def release_stale_buckets() -> int:
    """Nightly cleanup: a bucket left "In Use" from a day that's already
    ended never got received in time, so it's stuck until someone manually
    frees it -- exactly the backlog that piled up before 2026-09-05 and had
    to be cleared by hand. Anything not touched since before today is
    assumed abandoned and released back to Available for reuse; a bucket
    genuinely mid-harvest right now was modified today and is left alone.

    Returns count of buckets released.
    """
    cutoff = frappe.utils.today()
    stuck = frappe.get_all(
        "Bucket QR Code",
        filters={"status": "In Use", "modified": ["<", cutoff]},
        pluck="name",
    )
    if not stuck:
        return 0
    frappe.db.set_value(
        "Bucket QR Code",
        {"name": ["in", stuck]},
        {"status": "Available", "last_stock_entry": None, "current_journey_start": None},
        update_modified=False,
    )
    frappe.db.commit()
    frappe.log_error(
        title="Released {0} stale bucket(s)".format(len(stuck)),
        message=", ".join(stuck[:200]),
    )
    return len(stuck)


def rollup_plan_tasks() -> int:
    """Same idea for Production Plan Task: a Harvest-operation task with a
    variety set gets its actual weekly total filled in, so the plan shows
    target vs. what was actually picked without anyone opening Actual
    Harvest by hand.

    Soft-fails (returns 0) if tabActual Harvest does not exist on this site.
    Scheduled daily; upande_crop_material_planning no longer calls it.
    """
    if not frappe.db.has_table("tabActual Harvest"):
        return 0

    tasks = frappe.db.sql(
        """
        SELECT t.name, t.greenhouse, t.variety, p.plan_year, p.plan_week
        FROM `tabProduction Plan Task` t
        JOIN `tabProduction Plan Form` p ON p.name = t.parent
        WHERE t.operation = 'Harvest' AND t.variety IS NOT NULL AND t.variety != ''
          AND t.greenhouse IS NOT NULL AND t.greenhouse != ''
        """,
        as_dict=True,
    )
    updated = 0
    for t in tasks:
        monday = datetime.date.fromisocalendar(int(t.plan_year), int(t.plan_week), 1)
        sunday = monday + datetime.timedelta(days=6)
        harvested = frappe.db.sql(
            """
            SELECT COALESCE(SUM(quantity), 0)
            FROM `tabActual Harvest`
            WHERE greenhouse=%s AND variety=%s
              AND harvest_date BETWEEN %s AND %s
            """,
            (t.greenhouse, t.variety, monday, sunday),
        )[0][0]
        frappe.db.set_value("Production Plan Task", t.name, "harvested", harvested,
                            update_modified=False)
        updated += 1
    frappe.db.commit()
    return updated
