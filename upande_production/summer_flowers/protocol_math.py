"""Protocol arithmetic the crop cycle and the root line share (plants a bed holds, what grades out, what takes).

Lifted out of the Summer Flower Production Plan controller (planning) so production owns it and the
planning/propagation apps import it from here: dependency runs core <- production <- planning/propagation.
Pure functions of a Crop Protocol Version (or anything carrying its fields).
"""

import math

from frappe.utils import cint, flt

#: Below this, a "minimum planting area" is a field nobody filled in rather than
#: a statement about the ground. The farm's beds are 50 m2 -- 4,789 of them in
#: the register say so, and 17 of the 19 protocols that state a bed agree -- so
#: a one-metre bed is not a small bed, it is an absent one.
MIN_CREDIBLE_BED_SQM = 5.0


def bed_sqm(v):
	"""How big a bed is, or zero when nobody has said.

	The fallback to the minimum planting area was reasonable and was wrong. A
	farm that has not recorded its bed size has usually not recorded its minimum
	planting either, and that field defaults to 1.0 -- so the fallback did not
	rescue the arithmetic, it furnished a one-square-metre bed and let every
	figure downstream read as if the ground were known. SFPP-2026-00064 asked for
	1,688,336 plants and reported six beds on 0.0006 hectares, with a verdict
	saying there was enough land. At the protocol's own 16 plants a square metre
	it needs 2,111 beds and 15.8 hectares, on a farm that states 0.4.

	Zero means it genuinely cannot be worked out, and the caller must say so
	rather than put a number on it.
	"""
	stated = flt(getattr(v, "sqm_net_per_bed", 0))
	if stated > 0:
		return stated
	fallback = flt(getattr(v, "min_planting_area_sqm", 0))
	return fallback if fallback >= MIN_CREDIBLE_BED_SQM else 0.0



def plants_per_bed_for(v):
	"""How many plants a bed holds, worked out if it was not stored.

	A version frozen before the geometry was derived carries zero here, and a zero
	used to become a one: a bed holding a single plant. Applying the bed's AREA while
	that one stood for its CONTENTS is worse than either error alone -- ten thousand
	beds of a hundred square metres came out as a hundred hectares for a crop that
	needs a fifth of one, five hundred times too much, stated confidently.

	Density and bed area are both on the version, so the number can simply be worked
	out. Zero means it genuinely cannot be, and the caller must say nothing rather
	than guess.
	"""
	stored = cint(getattr(v, "plants_per_bed", 0))
	if stored:
		return stored
	return int(round(bed_sqm(v) * flt(getattr(v, "plants_per_sqm_net", 0))))


def saleable(v):
	"""The share of cut stems that grade out, as a fraction.

	The cutting reject is a loss of STEMS, not of plant material: a tenth
	rejected is a tenth of what the flushes produce, so it only has a size once
	the flushes have been counted. It used to be taken off the cuttings instead
	-- a tenth more stuck, as though the plants were short -- which is the same
	percentage doing the opposite job, and left the harvest counting rejects as
	production.

	reject_pct is read as well, because Crop Protocol has carried a field of
	that name and that meaning for every crop since before this app, and a
	protocol that states both means them both.

	1.0 where neither is stated: a loss nobody has measured is better carried as
	none than invented.
	"""
	keep = 1.0
	for field in ("cutting_reject_pct", "reject_pct"):
		pct = flt(getattr(v, field, 0) or 0)
		if 0 < pct < 100:
			keep *= 1.0 - pct / 100.0
	return keep


def establishment(v):
	"""The share of what is planted that takes, as a fraction. 1.0 when the
	protocol does not say, because guessing a loss is worse than carrying none."""
	pct = flt(getattr(v, "field_establishment_pct", 0) or 0)
	return (pct / 100.0) if 0 < pct < 100 else 1.0


def plants_to_plant(v, standing_required):
	"""How many to put in the ground to be left with `standing_required`."""
	take = establishment(v)
	return int(math.ceil(cint(standing_required) / take)) if take else cint(
		standing_required)


def plants_standing_from(v, planted, at_least=0):
	"""What a planting of `planted` leaves standing once it has established.

	Never less than what was asked for: the planting was rounded UP to a whole
	minimum area, so the stand it leaves is at least the one the demand needed.
	"""
	return max(cint(at_least), int(round(cint(planted) * establishment(v))))


def size_planting(v, plants_required, min_beds=1):
	"""Turn a flush-true plant requirement into a plantable size.

	Returns (beds held, plants planted, net m2 planted).

	The unit a planting comes in is the protocol's MINIMUM PLANTING AREA, not the
	bed. Rounding to whole beds quantised every cohort to a bed's worth of plants:
	a week needing 7,408 plants was planted with 8,000 because a bed holds a
	thousand, eight per cent over the whole order, and the flush's own answer was
	computed and thrown away. Where the minimum is smaller than a bed -- and on most
	crops it is -- the area rounds far closer and the plant count follows the flush
	again.

	Beds are still whole, because a bed is what the block calendar holds; a planting
	of 380 m2 occupies eight 50 m2 beds even though it plants only seven and a half
	of them.
	"""
	per_sqm = flt(getattr(v, "plants_per_sqm_net", 0))
	unit = flt(getattr(v, "min_planting_area_sqm", 0))
	bed = flt(getattr(v, "sqm_net_per_bed", 0))
	ppb = plants_per_bed_for(v)
	if not per_sqm or not unit:
		# No density or no stated minimum: the area arithmetic has nothing to stand
		# on, so fall back to whole beds and say so by returning no area.
		beds = max(cint(min_beds), int(math.ceil(plants_required / ppb))) if ppb \
			else cint(min_beds)
		return beds, (beds * ppb if ppb else 0), (beds * bed)
	units = max(1, int(math.ceil((plants_required / per_sqm) / unit)))
	area = units * unit
	plants = int(round(area * per_sqm))
	beds = max(cint(min_beds), int(math.ceil(area / bed))) if bed else cint(min_beds)
	return beds, plants, area
