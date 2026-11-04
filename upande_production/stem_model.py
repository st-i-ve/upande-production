"""
Stem production model for cut roses -- the copy the farm map and house tiles need.

upande_crop_material_planning owns the budget built on this model; the map in this app
only needs the weekly stems per planting, so the maths and the protocol lookup live here
and production never imports planning code. (Same functions as planning's projection_calc.)

Pure functions — plain dicts and dates, no Frappe runtime — so the maths is
testable on its own. The Frappe layer feeds in Crop Protocol + Crop Cycle.

The model
---------
A rose block is not harvested on a fixed schedule; it multiplies. You bend the
plant, take a first cut, and every stem you cut comes back as 2-3 breaks of
which some fraction makes grade. That fraction (`stems_per_cut`, ~1.5) is the
engine, and it compounds each cut cycle until the canopy runs out of room:

    wave 1 stems/plant = stems_per_plant_first_harvest
    wave n stems/plant = min(wave n-1 x stems_per_cut, max_stems_per_plant_per_cut)

Without the ceiling this grows without bound, which is why it is required.

Waves also de-synchronise. The first cut off a freshly bent block comes in
almost together; every stem then regrows on its own clock, so each generation
inherits its parents' timing plus fresh variation and the spread compounds:

    wave n is spread over min(2 ** (n - 1), weeks_between_cuts) weeks

Doubling, not +1 per wave. A block reaches continuous production inside its
first year (wave 4 of an 8-week cycle, ~7 months); widening one week at a time
would leave dead weeks deep into year two, which is not how a rose block
behaves.

Once the spread reaches `weeks_between_cuts`, consecutive waves tile exactly and
the block settles at a flat weekly rate, which is the number growers quote:

    steady stems/week = plants x max_stems_per_plant_per_cut / weeks_between_cuts

e.g. 10,000 plants x 1.61 / 7 weeks = 2,300 stems/week.
"""

from __future__ import annotations

import datetime

import frappe

from upande_production import weekcal


def iso_weeks_in_year(year: int, rule: str | None = None) -> int:
    """52 or 53. December 28th always falls in the final ISO week of its year.

    2026 has 53 — a budget that stops at 52 silently loses a week of stems.

    `rule` defaults to ISO, so callers with no opinion behave exactly as before.
    """
    return weekcal.weeks_in_year(year, rule)


def iso_week_key(d: datetime.date, rule: str | None = None) -> tuple[int, int]:
    """(week_year, week_number) — budgets bucket on the calendar, not on plant age.

    `rule` defaults to ISO. Pass the rule stamped on the document being built so
    the buckets and the dates the page prints agree with each other.
    """
    return weekcal.week_key(d, rule)


def production_start(cycle: dict, protocol: dict) -> datetime.date | None:
    """First harvest date. Explicit bending dates win over protocol offsets."""
    planting = cycle.get("planting_date")
    if not planting:
        return None

    second_bend = cycle.get("second_bending_date")
    if not second_bend:
        first_bend = cycle.get("first_bending_date")
        if not first_bend:
            wks = int(protocol.get("weeks_to_first_bending") or 0)
            first_bend = planting + datetime.timedelta(weeks=wks)
        wks2 = int(protocol.get("weeks_to_second_bending") or 0)
        second_bend = first_bend + datetime.timedelta(weeks=wks2)

    return second_bend + datetime.timedelta(
        weeks=int(protocol.get("weeks_between_cuts") or 0)
    )


def production_end(cycle: dict, protocol: dict) -> datetime.date | None:
    """Last date this block can produce."""
    for key in ("cycle_end_date", "planned_uprooting_date"):
        if cycle.get(key):
            return cycle[key]
    life = int(protocol.get("productive_life_weeks") or 0)
    if life and cycle.get("planting_date"):
        return cycle["planting_date"] + datetime.timedelta(weeks=life)
    return None


def cycle_weekly_stems(
    cycle: dict,
    protocol: dict,
    seasonal_factors: dict[int, float] | None = None,
    rule: str | None = None,
) -> dict[tuple[int, int], float]:
    """One crop cycle's whole productive life as {(week_year, week): stems}.

    Gross of grading, net of the protocol's reject %. `rule` defaults to ISO.

    A rose compounds off a cut stem; a summer flower flushes on a schedule
    that repeats every year. Same shape out, different model, picked by the
    protocol's Crop Type.
    """
    if protocol.get("crop_type") == "Summer Flower":
        return _flush_weekly_stems(cycle, protocol, seasonal_factors, rule)
    return _rose_weekly_stems(cycle, protocol, seasonal_factors, rule)


def _rose_weekly_stems(
    cycle: dict,
    protocol: dict,
    seasonal_factors: dict[int, float] | None = None,
    rule: str | None = None,
) -> dict[tuple[int, int], float]:
    """The bending-and-compounding model. See module docstring."""
    seasonal_factors = seasonal_factors or {}
    plants = int(cycle.get("qty_planted") or 0)
    cut_weeks = int(protocol.get("weeks_between_cuts") or 0)
    if plants <= 0 or cut_weeks <= 0:
        return {}

    start = production_start(cycle, protocol)
    end = production_end(cycle, protocol)
    if not start:
        return {}

    first = float(protocol.get("stems_per_plant_first_harvest") or 0)
    mult = float(protocol.get("stems_per_cut") or 1.0)
    ceiling = float(protocol.get("max_stems_per_plant_per_cut") or 0)
    reject = float(protocol.get("reject_pct") or 0) / 100.0
    if first <= 0 or ceiling <= 0:
        return {}

    # A block with no end date still cannot run forever.
    max_waves = 520 // cut_weeks

    out: dict[tuple[int, int], float] = {}
    per_plant = first
    for wave in range(1, max_waves + 1):
        wave_date = start + datetime.timedelta(weeks=(wave - 1) * cut_weeks)
        if end and wave_date > end:
            break

        wave_stems = plants * per_plant * (1 - reject)

        # De-synchronisation compounds: the spread doubles each generation
        # until it fills a cut cycle, after which waves tile and production
        # is continuous.
        spread = min(2 ** (wave - 1), cut_weeks)
        share = wave_stems / spread
        for offset in range(spread):
            d = wave_date + datetime.timedelta(weeks=offset)
            if end and d > end:
                break
            factor = seasonal_factors.get(d.month, 1.0)
            key = iso_week_key(d, rule)
            out[key] = out.get(key, 0.0) + share * factor

        per_plant = min(per_plant * mult, ceiling)

    return out


# A block re-flushes on the same weeks every year rather than compounding, so
# the whole schedule is replayed once per year for however long it produces.
WEEKS_PER_YEAR = 52

# However long a block is meant to run, it cannot run forever. Mirrors the
# rose model's own cap (there: 520 weeks regardless of cut length).
MAX_FLUSH_YEARS = 20


def _flush_weekly_stems(
    cycle: dict,
    protocol: dict,
    seasonal_factors: dict[int, float] | None = None,
    rule: str | None = None,
) -> dict[tuple[int, int], float]:
    """The flush model: each row in Flush Schedule fires once a year.

    No compounding and no ceiling — a flush's Stems Per Plant is already the
    whole answer for that pick. Only the calendar repeats.
    """
    seasonal_factors = seasonal_factors or {}
    plants = int(cycle.get("qty_planted") or 0)
    planting = cycle.get("planting_date")
    rows = protocol.get("flush_schedule") or []
    if plants <= 0 or not planting or not rows:
        return {}

    first_flush = planting + datetime.timedelta(
        weeks=int(protocol.get("weeks_to_first_flush") or 0)
    )
    end = production_end(cycle, protocol)
    reject = float(protocol.get("reject_pct") or 0) / 100.0

    out: dict[tuple[int, int], float] = {}
    for year in range(MAX_FLUSH_YEARS):
        year_start = first_flush + datetime.timedelta(weeks=WEEKS_PER_YEAR * year)
        if end and year_start > end:
            break
        for row in rows:
            d = year_start + datetime.timedelta(
                weeks=int(row.get("weeks_after_first_flush") or 0)
            )
            if end and d > end:
                continue
            stems = plants * float(row.get("stems_per_plant") or 0) * (1 - reject)
            if stems <= 0:
                continue
            factor = seasonal_factors.get(d.month, 1.0)
            key = iso_week_key(d, rule)
            out[key] = out.get(key, 0.0) + stems * factor

    return out


def build_budget_year(
    cycles: list[tuple[dict, dict]],
    year: int,
    seasonal_factors: dict[int, float] | None = None,
    rule: str | None = None,
) -> dict[int, int]:
    """One year's weekly budget for a single greenhouse x variety.

    cycles: [(cycle, protocol), ...] — every planting of that variety in that
    house. An old block still cutting and a new block coming online both land
    in the same calendar week, so they are summed.

    `rule` defaults to ISO. It must match the rule stamped on the projection
    being written, or the week buckets and the printed dates will disagree.

    Returns {week: stems} for the requested year only.
    """
    totals: dict[int, float] = {}
    for cycle, protocol in cycles:
        for (week_year, week), stems in cycle_weekly_stems(
            cycle, protocol, seasonal_factors, rule
        ).items():
            if week_year == year:
                totals[week] = totals.get(week, 0.0) + stems
    return {wk: int(round(v)) for wk, v in sorted(totals.items()) if round(v) > 0}


def split_by_grade(stems: int, grade_mix: list[dict]) -> dict[int, int]:
    """Split a week's stems across length grades.

    grade_mix rows are {length_cm, pct}. Shares are normalised, so a mix that
    sums to 98% or 103% still allocates every stem. Empty mix returns {}.
    """
    rows = [(int(r["length_cm"]), float(r.get("pct") or 0)) for r in (grade_mix or [])]
    rows = [(ln, pct) for ln, pct in rows if pct > 0]
    total = sum(pct for _, pct in rows)
    if not rows or total <= 0:
        return {}
    out = {ln: int(round(stems * pct / total)) for ln, pct in rows}
    # Push the rounding remainder onto the largest grade so the split is exact.
    drift = stems - sum(out.values())
    if drift:
        biggest = max(out, key=lambda k: out[k])
        out[biggest] += drift
    return out


# ---------------------------------------------------------------------------
# Protocol / cycle lookup, seasonal curve (shared with the farm map)
# ---------------------------------------------------------------------------

PROTOCOL_FIELDS = (
    "crop_type",
    "weeks_to_first_bending",
    "weeks_to_second_bending",
    "weeks_between_cuts",
    "stems_per_plant_first_harvest",
    "stems_per_cut",
    "max_stems_per_plant_per_cut",
    "weeks_to_first_flush",
    "reject_pct",
    "productive_life_weeks",
)

CYCLE_FIELDS = (
    "name",
    "greenhouse",
    "variety",
    "crop_protocol",
    "planting_date",
    "first_bending_date",
    "second_bending_date",
    "planned_uprooting_date",
    "cycle_end_date",
    "qty_planted",
)



def _protocol_dict(name: str | None) -> dict | None:
    if not name:
        return None
    doc = frappe.get_cached_doc("Crop Protocol", name)
    out = {f: doc.get(f) for f in PROTOCOL_FIELDS}
    # projection_calc wants plain dicts, not child Documents.
    out["flush_schedule"] = [
        {"flush_number": r.flush_number, "weeks_after_first_flush": r.weeks_after_first_flush,
         "stems_per_plant": r.stems_per_plant}
        for r in (doc.flush_schedule or [])
    ]
    return out


def _resolve_protocol(cycle: dict) -> dict | None:
    """The cycle's own protocol, else any protocol for that variety."""
    proto = _protocol_dict(cycle.get("crop_protocol"))
    if proto:
        return proto
    fallback = frappe.db.get_value(
        "Crop Protocol", {"variety_item": cycle.get("variety")}, "name"
    )
    return _protocol_dict(fallback)



# Sep..Aug monthly shape out of the farm's budget workbook.
MONTH_WEIGHT = [0.070, 0.077, 0.077, 0.092, 0.077, 0.140, 0.070, 0.086, 0.086, 0.070, 0.070, 0.085]


def default_seasonal_factors() -> dict[int, float]:
    """Calendar-month multipliers from the farm's own budget shape.

    MONTH_WEIGHT is the Sep-Aug curve out of BUDGET 2026-2027.xlsx. Normalising
    it to mean 1.0 turns it into a factor the model can apply without changing
    the annual total. February is a market shape, not a biological one - the
    Valentine's flush is timed deliberately - but it is what the farm plans to.

    A tenant that maintains Seasonal Yield Factor rows overrides this.
    """
    mean = sum(MONTH_WEIGHT) / len(MONTH_WEIGHT)
    # MONTH_WEIGHT runs Sep..Aug; calendar months are 9..12 then 1..8.
    months = list(range(9, 13)) + list(range(1, 9))
    return {m: round(w / mean, 4) for m, w in zip(months, MONTH_WEIGHT)}


FARM_LAT, FARM_LON = -0.7167, 36.4333
