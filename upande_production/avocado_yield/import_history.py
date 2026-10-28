# Load the estate's own avocado spreadsheets into Avocado Yield Block.
#
# The orchard's truth lives in three files the farm already maintains:
#   Master Yield Summary            block, plant date, hectares, kg by year
#   <date> Lokitela ... harvest      trees planted and BEARING trees, per block
#   SABOTI FARM BLOCKS               the Saboti plant counts, which the ERP lacks
#
# Bearing trees are the number that matters: the forecast is sized on them, and
# they are the one figure the block master on the ERP either lacks (Saboti) or
# disagrees with. Everything is matched on block code, and anything that cannot be
# matched is reported rather than guessed at.
#
# Run:  bench --site <site> execute \
#         upande_production.avocado_yield.import_history.run --kwargs "{'folder': '/mnt/c/Users/teddy/Downloads'}"

import os
import re

import frappe
from frappe.utils import cint, flt, getdate

DOCTYPE = "Avocado Yield Block"

MASTER = "Master Yield Summary - edit July 2025 .xlsx"
HARVEST = "24 Sept 2025 - Lokitela Late Crop harvest All Areas.xlsx"
SABOTI = "SABOTI FARM BLOCKS.xlsx"


def _rows(path, sheet):
	import openpyxl

	wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
	ws = wb[sheet] if sheet in wb.sheetnames else wb[wb.sheetnames[0]]
	out = [list(r) for r in ws.iter_rows(values_only=True)]
	wb.close()
	return out


def _code(label):
	"""'1' -> LK01 for the 2018 planting; everything else keeps its own name."""
	t = str(label).strip()
	if t.replace(".0", "").isdigit():
		return f"LK{int(float(t)):02d}"
	t = t.upper()
	# The estate spells the same four blocks Kinyoro on the yield and harvest sheets
	# and Kinyoroo on the 2026 estimate. Left alone that is eight block codes where
	# there are four blocks, each holding half the truth about the same trees — and
	# the four with the current bearing counts would be the empty ones.
	if t.startswith("KINYOROO"):
		t = t.replace("KINYOROO", "KINYORO", 1)
	return t


def read_master(folder):
	"""{code: {area_ha, planting_year, planting_date, variety}} from the summary."""
	rows = _rows(os.path.join(folder, MASTER), "Summary Incl Late Crop")
	out = {}
	for r in rows:
		label = r[0]
		if label is None:
			continue
		name = str(label).strip()
		if not name or name.lower().startswith(("lokitela", "block", "lk total", "cumulative",
											   "feasability", "variance", "kg/ha")):
			continue
		plant, ha = r[1], r[4]
		if not isinstance(ha, (int, float)) or not (0 < ha <= 60):
			continue
		code = _code(name)
		out[code] = {
			"area_ha": flt(ha),
			"variety": str(r[3] or "Hass").strip() or "Hass",
			"planting_date": getdate(plant) if plant else None,
			"planting_year": getdate(plant).year if plant else None,
		}
	return out


def read_trees(folder):
	"""{code: {total_trees, bearing_trees}} — walks every planting section."""
	rows = _rows(os.path.join(folder, HARVEST), "Sept- Late crop 2025")
	out = {}
	for r in rows:
		label, ha, trees, bearing = (r + [None] * 4)[:4]
		if label is None or not isinstance(trees, (int, float)) or not trees:
			continue
		name = str(label).strip()
		if not name or name.lower().startswith(("block", "budget", "lk total", "total")):
			continue
		# The sheet stacks several planting sections with repeated headers, and a
		# few rows carry kilograms where trees belong. Anything outside what a
		# block can physically be is dropped rather than imported: a block is at
		# most a few hectares, at 250 trees a hectare, and bearing trees cannot
		# exceed the trees that are there.
		area = flt(ha) if isinstance(ha, (int, float)) else None
		bear = flt(bearing) if isinstance(bearing, (int, float)) else 0.0
		if not (0 < trees <= 6000):
			continue
		if area is not None and not (0 < area <= 60):
			continue
		if area and trees > area * 400:
			continue
		if bear > trees:
			bear = 0.0
		out[_code(name)] = {"total_trees": int(trees), "bearing_trees": bear, "area_ha": area}
	return out


def read_saboti(folder):
	rows = _rows(os.path.join(folder, SABOTI), "SABOTI FARM")
	out = {}
	for r in rows:
		code, plants, ha = (list(r) + [None] * 3)[:3]
		if not code or not isinstance(plants, (int, float)):
			continue
		name = str(code).strip().upper()
		if not name.startswith("SB"):
			continue
		out[name] = {
			"total_trees": int(plants),
			"area_ha": flt(ha),
			# Planted 2024/2025 and not yet in crop — the block master on the ERP
			# says the same, so nothing here is invented.
			"bearing_trees": 0.0,
			"farm": "Saboti",
			"variety": "Golden Hass",
		}
	return out


def run(folder="/mnt/c/Users/teddy/Downloads", commit=True):
	master, trees, saboti = read_master(folder), read_trees(folder), read_saboti(folder)
	current = read_estimate(folder)
	card = read_history_card(folder)

	merged = {}
	for code, m in master.items():
		merged[code] = dict(m, farm="Lokitela")
	for code, t in trees.items():
		merged.setdefault(code, {"farm": "Lokitela", "variety": "Hass"}).update(
			{k: v for k, v in t.items() if v is not None}
		)
	for code, sb in saboti.items():
		merged.setdefault(code, {}).update(sb)
	# The history card carries what only it knows about Saboti: rootstock, planting
	# date, spacing. Its tree and hectare figures are the same ones the farm block
	# list gives, so nothing here contradicts what is already loaded.
	for code, hc in card.items():
		merged.setdefault(code, {}).update(hc)
	# Bearing trees LAST, and from the current season's estimate wherever it has
	# them. The older harvest sheet counted the trees that bore in Sept 2025; a
	# whole planting has come into crop since, and forecasting on last year's
	# bearing count is how this model promised half the crop the farm expected.
	stale = 0
	for code, e in current.items():
		if code in merged:
			stale += 1
		merged.setdefault(code, {"farm": "Lokitela", "variety": "Hass"})["bearing_trees"] = \
			e["bearing_trees"]
	print(f"bearing trees taken from the 2026 estimate for {stale} blocks, "
		  f"from the Sept 2025 harvest sheet for the rest")

	created, updated, skipped = 0, 0, []
	for code, vals in sorted(merged.items()):
		area = flt(vals.get("area_ha"))
		if not (0 < area <= 60):
			skipped.append((code, f"implausible hectarage {area}"))
			continue
		total = int(vals.get("total_trees") or round(flt(vals["area_ha"]) * 250))
		doc = {
			"doctype": DOCTYPE,
			"block_code": code,
			"farm": vals.get("farm") or "Lokitela",
			"variety": vals.get("variety") or "Hass",
			"status": "Active",
			"area_ha": flt(vals["area_ha"]),
			"spacing": vals.get("spacing"),
			"trees_per_ha": 250,
			"total_trees": total,
			# No separate live count in these sheets, so live == planted. Sick trees
			# and gaps stay empty rather than being made up; the ERP block master
			# has those where anyone has recorded them.
			"live_trees": total,
			"bearing_trees": flt(vals.get("bearing_trees")),
			"planting_year": vals.get("planting_year"),
			"planting_date": vals.get("planting_date"),
			"notes": vals.get("notes") or "Imported from the estate yield and harvest spreadsheets.",
		}
		if frappe.db.exists(DOCTYPE, code):
			d = frappe.get_doc(DOCTYPE, code)
			d.update({k: v for k, v in doc.items() if k not in ("doctype", "block_code")})
			d.save(ignore_permissions=True)
			updated += 1
		else:
			frappe.get_doc(doc).insert(ignore_permissions=True)
			created += 1

	if commit:
		frappe.db.commit()

	print(f"blocks created {created}, updated {updated}, skipped {len(skipped)}")
	for code, why in skipped[:10]:
		print(f"  skipped {code}: {why}")
	bearing = frappe.db.sql(f"select sum(bearing_trees), sum(total_trees), sum(area_ha) "
							f"from `tab{DOCTYPE}`")[0]
	print(f"totals: {flt(bearing[0]):,.0f} bearing of {flt(bearing[1]):,.0f} trees "
		  f"on {flt(bearing[2]):,.1f} ha")
	return {"created": created, "updated": updated, "skipped": skipped}


def reset(folder="/mnt/c/Users/teddy/Downloads"):
	"""Wipe the imported blocks and load them again.

	Safe because this table is a mirror of the spreadsheets, never hand-keyed: a
	site that keeps its blocks in avocado_production does not use it at all.
	"""
	frappe.db.delete(DOCTYPE)
	frappe.db.commit()
	return run(folder=folder)


# ── Yearly delivered yield, and the estate's own 2026 estimate ───────────────

ESTIMATE = "2026 Lokitela Early Crop Estimate All Areas .xlsx"
HISTORY_DOCTYPE = "Avocado Yield History"
COUNT_DOCTYPE = "Avocado Fruit Count"

SKIP_LABELS = ("lokitela", "block", "lk total", "total", "cumulative", "feasability",
			   "variance", "kg/ha", "budget", "estimate", "actual", "by age", "planting")


def _is_block_label(label):
	if label is None:
		return False
	t = str(label).strip()
	return bool(t) and not t.lower().startswith(SKIP_LABELS)


def read_yearly(folder):
	"""[(code, year, kg)] from the Master Yield Summary, late crop included."""
	rows = _rows(os.path.join(folder, MASTER), "Summary Incl Late Crop")
	year_cols = []
	for r in rows[:10]:
		cand = [(j, int(c)) for j, c in enumerate(r)
				if isinstance(c, (int, float)) and 2015 < c < 2035]
		if len(cand) >= 4:
			# The sheet repeats the whole year block further right (early crop, then
			# early + late). Keep the FIRST column for each year or every row lands
			# twice and the primary key rejects the second.
			seen = set()
			for j, y in cand:
				if y not in seen:
					seen.add(y)
					year_cols.append((j, y))
			break
	out = []
	for r in rows:
		if not _is_block_label(r[0]):
			continue
		ha = r[4] if len(r) > 4 else None
		if not isinstance(ha, (int, float)) or not (0 < ha <= 60):
			continue
		code = _code(r[0])
		for j, year in year_cols:
			kg = r[j] if j < len(r) else None
			if isinstance(kg, (int, float)) and kg > 0:
				out.append((code, year, flt(kg)))
	return out


def read_estimate(folder):
	"""{code: {bearing_trees, fruit_per_tree, est_kg}} — the farm's own 2026 estimate.

	Their method is the one this module now supports: bearing trees x average fruit
	per tree, packed at 18 kg a crate. Reading it in means the model can be checked
	against what the people who walk the orchard expected, not just against history.
	"""
	rows = _rows(os.path.join(folder, ESTIMATE), "March - Early crop 2026")
	out = {}
	for r in rows:
		if not _is_block_label(r[0]):
			continue
		ha, trees, bearing, fruit = (list(r) + [None] * 6)[1:5]
		nums = [ha, trees, bearing, fruit]
		if not all(isinstance(v, (int, float)) for v in nums):
			continue
		if not (0 < ha <= 60 and 0 < trees <= 6000 and 0 < bearing <= trees and 0 < fruit <= 2000):
			continue
		kg = r[7] if len(r) > 7 and isinstance(r[7], (int, float)) else None
		out[_code(r[0])] = {"bearing_trees": flt(bearing), "fruit_per_tree": flt(fruit),
							"est_kg": flt(kg) if kg else None, "trees": int(trees)}
	return out


# ── The late crop: what it actually delivered, and when ──────────────────────
#
# This estate harvests twice a year and the Master Yield Summary records one number
# per year, so a late crop has never been separable from the early one it was added
# to. The Sept 2025 harvest sheet has the missing half: an Actual column per block,
# and a delivery log with the dates the crates left each block.

LATE_SHEET = "Sept- Late crop 2025"
LATE_SEASON = 2025

# The ACTUAL kilograms, not the estimate. They sit three columns apart on the sheet
# and one keystroke apart here: column 7 is what the farm thought in July and column
# 10 is what the weighbridge said in September. Only the second is a fact.
LATE_ACTUAL_CRATES_COL = 9
LATE_ACTUAL_KG_COL = 10

# The most any row of this orchard has delivered in a single crop, per hectare: LK01
# managed 15.9 t/ha in Sept 2025 and that is the estate record. 30 is a ceiling no
# avocado block on earth clears, and it is what stops a planting subtotal — 150 t
# against a hectarage the row does not carry — from being imported as a block.
MAX_BLOCK_KG_PER_HA = 30000.0

# The delivery log writes block numbers the way a foreman says them: "1&2",
# "3,4,5&6", "W1-2, B1", "W 5,6". Only the two prefixes the estate actually uses are
# mapped; anything else is left alone rather than guessed at, because "M" could be
# Mima, Mlima or Muhammed and picking one would put a truck at the wrong gate.
RPC_PREFIXES = {"W": "WESA", "B": "BONDENI"}


def _rpc_blocks(text):
	"""'3,4,5&6' -> LK03..LK06;  'W 5,6' -> WESA 5, WESA 6;  'W1-2, B1' -> both.

	The prefix carries forward within a row, because that is how the sheet is
	written: once the foreman is in Wesa, a bare 6 is Wesa 6, not block 6 of the
	2018 planting on the other side of the estate.
	"""
	out, prefix = [], ""
	for token in str(text or "").replace("&", ",").split(","):
		token = token.strip().upper()
		if not token:
			continue
		seen = ""
		while token and token[0].isalpha():
			seen += token[0]
			token = token[1:].strip()
		if seen:
			prefix = seen
		if prefix and prefix not in RPC_PREFIXES:
			continue
		parts = token.split("-")
		try:
			lo, hi = int(float(parts[0])), int(float(parts[-1]))
		except ValueError:
			continue
		# Every planting on this estate numbers its blocks 1 to 12 at most. A wider
		# range is a date, a delivery note number or a crate count, not a block.
		if not (1 <= lo <= hi <= 12):
			continue
		for n in range(lo, hi + 1):
			out.append(f"{RPC_PREFIXES[prefix]} {n}" if prefix else f"LK{n:02d}")
	return out


def read_late_actuals(folder, sheet=LATE_SHEET):
	"""{code: {kg, crates, bearing_trees, area_ha, trees, section}} — the LATE crop.

	Only what the bins weighed. The estimate beside it is the farm's own method and
	is already modelled elsewhere; the whole value of this column is that it is the
	fact that method gets checked against.
	"""
	out, section = {}, None
	for r in _rows(os.path.join(folder, HARVEST), sheet):
		r = list(r) + [None] * 14
		label = r[0]
		if isinstance(label, str) and "planting" in label.lower():
			section = label.strip()
		if not _is_block_label(label):
			continue
		ha, trees, bearing, kg = r[1], r[2], r[3], r[LATE_ACTUAL_KG_COL]
		if not all(isinstance(v, (int, float)) for v in (ha, trees, kg)):
			continue
		# The same discipline the tree import keeps: a block is a few hectares of
		# trees at roughly 250 to the hectare, and it cannot out-deliver the estate
		# record several times over. Subtotals, the RPC delivery log and the summary
		# block all fail one of these and are dropped rather than imported.
		if not (0 < ha <= 60 and 0 < trees <= 6000):
			continue
		if not (kg > 0 and kg / ha <= MAX_BLOCK_KG_PER_HA):
			continue
		crates = r[LATE_ACTUAL_CRATES_COL]
		out[_code(label)] = {
			"kg": flt(kg),
			"crates": flt(crates) if isinstance(crates, (int, float)) else None,
			"bearing_trees": flt(bearing) if isinstance(bearing, (int, float)) else 0.0,
			"trees": int(trees),
			"area_ha": flt(ha),
			"section": section,
		}
	return out


def read_late_windows(folder, sheet=LATE_SHEET, codes=None, sections=None):
	"""{code: (start, end, basis)} — the weeks each block was actually picked.

	Straight off the RPC delivery log at the foot of the harvest sheet, which dates
	every load and names the blocks it came from. Three tiers, weakest last, and
	every block says which it got:

	  its own dates          — the log named it
	  its planting's window  — the log named its neighbours of the same age
	  the whole crop's       — the log named nobody in its planting

	Nothing is invented for a block the log is silent about; it inherits, and the
	basis string is what stops a page presenting an inheritance as a record.
	"""
	import datetime

	dated, in_log, all_dates = {}, False, []
	for r in _rows(os.path.join(folder, HARVEST), sheet):
		r = list(r) + [None] * 8
		if isinstance(r[0], str) and r[0].strip().lower().startswith("rpc"):
			in_log = True
			continue
		if not in_log or not isinstance(r[0], (datetime.date, datetime.datetime)):
			continue
		day = getdate(r[0])
		all_dates.append(day)
		for code in _rpc_blocks(r[3]):
			lo, hi = dated.get(code, (day, day))
			dated[code] = (min(lo, day), max(hi, day))
	if not all_dates:
		return {}

	sections = sections or {}
	by_section = {}
	for code, (lo, hi) in dated.items():
		sec = sections.get(code)
		if not sec:
			continue
		s_lo, s_hi = by_section.get(sec, (lo, hi))
		by_section[sec] = (min(s_lo, lo), max(s_hi, hi))
	crop = (min(all_dates), max(all_dates))

	out = {}
	for code in (codes if codes is not None else dated):
		if code in dated:
			out[code] = dated[code] + ("its own dates in the delivery log",)
			continue
		sec = sections.get(code)
		if sec and sec in by_section:
			out[code] = by_section[sec] + (f"the {sec} window — this block was not "
										   f"named in the delivery log",)
			continue
		out[code] = crop + ("the whole late crop's window — no block of this planting "
							"was named in the delivery log",)
	return out


def import_yearly(folder="/mnt/c/Users/teddy/Downloads", commit=True):
	"""Delivered kilograms per block per season, with the two crops split apart.

	The Master Yield Summary gives one number a year. Where the late crop of that
	year is known block by block, the year is SPLIT — Late is what the harvest sheet
	weighed, Early is the remainder — so that a page summing the whole table still
	gets the year right and a page asking for the late crop gets the late crop. A
	year with no late sheet stays one row, tagged Year, because splitting it would
	mean inventing the split.
	"""
	# The crop tag is part of the name, so a site that has not migrated yet would
	# collide two crops onto one record. Reload first and the importer is always
	# writing against the doctype it was written for.
	frappe.reload_doc("Avocado Yield", "doctype", "avocado_yield_history")
	frappe.db.delete(HISTORY_DOCTYPE)

	late = read_late_actuals(folder)
	windows = read_late_windows(folder, codes=list(late),
								sections={c: v["section"] for c, v in late.items()})

	def _insert(code, year, part, kg, **extra):
		frappe.get_doc(dict({"doctype": HISTORY_DOCTYPE, "block_code": code, "year": year,
							 "season_part": part, "kg_harvested": kg}, **extra)
					   ).insert(ignore_permissions=True)

	def _late_row(code):
		lk = late[code]
		lo, hi, basis = windows.get(code, (None, None, None))
		return dict(trees=int(lk["bearing_trees"]) or None, harvest_start=lo, harvest_end=hi,
					window_basis=basis, source=HARVEST)

	n, split, refused, seen_late = 0, 0, [], set()
	for code, year, kg in read_yearly(folder):
		lk = late.get(code) if year == LATE_SEASON else None
		if not lk:
			_insert(code, year, "Year", kg, source=MASTER)
			n += 1
			continue
		# The late crop cannot be bigger than the year that contains it. Where it is,
		# the two sheets disagree about the same block and the year is left whole
		# rather than being made to balance with a negative early crop.
		early = kg - lk["kg"]
		if early < -1:
			refused.append((code, kg, lk["kg"]))
			_insert(code, year, "Year", kg, source=MASTER)
			n += 1
			continue
		seen_late.add(code)
		if early > 1:
			_insert(code, year, "Early", early, source=f"{MASTER} less the late crop")
			n += 1
		_insert(code, year, "Late", lk["kg"], **_late_row(code))
		n += 1
		split += 1
	# A block the late sheet weighed and the master summary never carried — Endebess
	# is one. Real delivered fruit, so it is loaded rather than dropped for not being
	# on the other sheet.
	for code in sorted(set(late) - seen_late):
		_insert(code, LATE_SEASON, "Late", late[code]["kg"], **_late_row(code))
		n += 1

	if commit:
		frappe.db.commit()

	print(f"history rows: {n} ({split} seasons split into an early and a late crop)")
	for code, year_kg, late_kg in refused:
		print(f"  {code}: late crop {late_kg:,.0f} kg exceeds the year's {year_kg:,.0f} kg "
			  f"— left as one Year row")
	tot = frappe.db.sql(f"""select year, season_part, sum(kg_harvested), sum(trees), count(*)
		from `tab{HISTORY_DOCTYPE}` group by year, season_part order by year, season_part""")
	for y, part, kg, trees, blocks in tot:
		per_tree = f"{flt(kg)/flt(trees):>5.1f} kg/tree" if trees else "trees not recorded"
		print(f"  {y} {part:<5}: {flt(kg)/1000:>8.1f} t over {blocks:>3} blocks, {per_tree}")
	return n


def report_late_actuals(folder="/mnt/c/Users/teddy/Downloads"):
	"""Print the late crop block by block, so the total can be checked by eye."""
	late = read_late_actuals(folder)
	windows = read_late_windows(folder, codes=list(late),
								sections={c: v["section"] for c, v in late.items()})
	own = sum(1 for c, w in windows.items() if w[2].startswith("its own"))
	print(f"{LATE_SEASON} late crop actuals, per block:")
	total = 0.0
	for code in sorted(late, key=lambda c: -late[c]["kg"]):
		lk, (lo, hi, _basis) = late[code], windows[code]
		total += lk["kg"]
		bearing = f"{lk['bearing_trees']:,.0f}" if lk["bearing_trees"] else "?"
		print(f"  {code:<12} {lk['kg']:>10,.0f} kg  {lk['kg']/lk['area_ha']:>8,.0f} kg/ha  "
			  f"{bearing:>6} bearing  picked {lo} to {hi}")
	print(f"  {'TOTAL':<12} {total:>10,.0f} kg over {len(late)} blocks "
		  f"({total/1000:,.1f} t); {own} of them carry their own pick dates")
	return late


def import_estimate(folder="/mnt/c/Users/teddy/Downloads", count_date="2026-01-15", commit=True):
	"""Load the farm's own fruit-per-tree figures as fruit counts.

	Dated mid-January because that is when the early-crop estimate was made: the
	forecast then uses them exactly as it would a count taken on the tree today.
	"""
	est = read_estimate(folder)
	frappe.db.delete(COUNT_DOCTYPE, {"notes": ("like", "%Early Crop Estimate%")})
	made = 0
	for code, e in sorted(est.items()):
		frappe.get_doc({
			"doctype": COUNT_DOCTYPE, "orchard_block": code, "count_date": count_date,
			"trees_counted": 0, "fruit_per_tree": e["fruit_per_tree"],
			# 18 kg a crate over ~81 fruit a crate is the 222 g their own sheets imply.
			"avg_fruit_weight_g": 222.0, "drop_pct": 10,
			"notes": "From the 2026 Lokitela Early Crop Estimate (bearing trees x ave fruit).",
		}).insert(ignore_permissions=True)
		made += 1
	if commit:
		frappe.db.commit()
	print(f"fruit counts from the farm's estimate: {made}")
	return made


# ── The Saboti block history cards ───────────────────────────────────────────

HISTORY_CARD = "AVO HISTORY CARD - 82Ha.xls"


def read_history_card(folder):
	"""{code: {rootstock, planting_date, spacing, ...}} from the Saboti cards.

	One sheet per block, SB1 to SB8, each headed with the things the ERP block
	master has nowhere else: the rootstock the Golden Hass is grafted on, the date
	it went in the ground, the spacing and the irrigation. Below the header sits a
	spray and fertiliser log, which is a husbandry record rather than a yield one
	and is deliberately left in the spreadsheet.
	"""
	path = os.path.join(folder, HISTORY_CARD)
	if not os.path.exists(path):
		return {}
	import xlrd

	wb = xlrd.open_workbook(path)
	out = {}
	for name in wb.sheet_names():
		ws = wb.sheet_by_name(name)
		if ws.nrows < 5 or ws.ncols < 14:
			continue
		cell = lambda r, c: ws.cell_value(r, c)  # noqa: E731
		code = str(cell(3, 1) or name).strip().upper()
		ha, trees = cell(2, 11), cell(4, 7)
		if not code.startswith("SB"):
			continue
		# Same discipline as everywhere else: a block is a few hectares of trees at
		# roughly 250 to the hectare, and a card that says otherwise is a layout
		# that has shifted, not an orchard.
		if not (isinstance(ha, float) and 0 < ha <= 60):
			continue
		if not (isinstance(trees, float) and 0 < trees <= ha * 400):
			continue
		# Planting dates are Excel serials on most cards and free text on SB6
		# ("March/May 2025"), where the block was planted over two months. Only a
		# real date is kept; the text is carried in the notes instead of guessed at.
		planted, planted_text = None, str(cell(3, 7)).strip()
		if isinstance(cell(3, 7), float) and cell(3, 7) > 40000:
			planted = xlrd.xldate_as_datetime(cell(3, 7), wb.datemode).date()
		rootstock = str(cell(2, 7) or "").strip()
		spacing = str(cell(3, 10) or "").strip()
		if spacing.lower() == "spacing":
			spacing = str(cell(3, 11) or "").strip()
		out[code] = {
			"total_trees": int(trees),
			"area_ha": flt(ha),
			"variety": str(cell(4, 1) or "Golden Hass").strip(),
			"spacing": spacing or None,
			"planting_date": planted,
			"planting_year": planted.year if planted else None,
			"notes": f"Block history card: {rootstock or 'rootstock not stated'} rootstock, "
					 f"planted {planted or planted_text}, {spacing or 'spacing not stated'}, "
					 f"{str(cell(4, 11) or 'irrigation not stated').strip()}.",
		}
	return {k: {f: v for f, v in vals.items() if v is not None} for k, vals in out.items()}


# ── Dry matter maturity tests ────────────────────────────────────────────────

MATURITY_DOCTYPE = "Avocado Maturity Test"

# The estate's own running summary, one stacked grid per planting, week 7 to this
# week. The per-planting "week 7" extracts that were loaded before are the first few
# columns of this same sheet, so this file replaces them rather than adding to them.
SUMMARY = "2026 Lokitela Dry Matter Summary xlsx.xlsx"
SUMMARY_SHEET = "2026"
SUMMARY_SEASON = 2026
# Every planting on this sheet is Lokitela's — it says so in the title row. It
# matters because Saboti also has a 2024 planting, and a planting YEAR alone would
# hand Lokitela's readings to trees on the other farm.
SUMMARY_FARM = "Lokitela"

# The section headings carry the planting year, which is the whole join: "23Ha  -
# 2018", "56Ha -2024". The hectarage in them is a nickname, and it is only ever
# cross-checked against the block master (match_cohorts), never used to match.
SECTION_RE = re.compile(r"^\s*(\d+)\s*ha\s*-?\s*(\d{4})\s*$", re.I)

# An avocado is 60-85% water. This is wider than any fruit anyone would pick, and it
# still refuses the two things on the sheet that are not readings: the 1.00 parked in
# every week nobody sampled, and the 0.76/0.66 reference lines that draw the export
# band on the graph (those sit on heading rows and never reach here anyway).
MIN_MOISTURE, MAX_MOISTURE = 0.55, 0.95

# How far a planting's hectarage may sit from the figure on the section heading and
# still be the same planting. The blocks are the survey, the heading is the
# shorthand, and they were never going to agree to the metre. Three hectares is wide
# enough for that and narrow enough that the 65 Ha and 70 Ha plantings — five
# hectares apart — can never be mistaken for each other.
COHORT_TOLERANCE_HA = 3.0


def match_cohorts(areas, tolerance_ha=COHORT_TOLERANCE_HA, verbose=True):
	"""{planting_area: planting_year} — which planting a hectarage label could be.

	Kept as a CROSS-CHECK only, now that the sheet's own section headings carry the
	planting year. Add up the blocks of each planting year and see which total the
	heading is quoting: agreement is reassurance, disagreement is the thing worth
	printing. The one person who can say whether 63.95 ha is "65ha" walks that
	orchard, so both numbers are printed and neither is acted on.
	"""
	cohorts = frappe.db.sql(f"""select planting_year, sum(area_ha), count(*)
		from `tab{DOCTYPE}` where ifnull(planting_year, 0) > 0
		group by planting_year order by planting_year""")
	out = {}
	for area in areas:
		want = flt(str(area).split()[0])
		near = sorted(((abs(flt(ha) - want), year, flt(ha), n) for year, ha, n in cohorts))
		if not near or near[0][0] > tolerance_ha:
			if verbose:
				closest = f"{near[0][2]:.2f} ha in {near[0][1]}" if near else "nothing"
				print(f"  {area}: NO planting matches within {tolerance_ha} ha "
					  f"(closest is {closest})")
			continue
		gap, year, ha, n = near[0]
		out[area] = year
		if verbose:
			print(f"  {area} ~ the {year} planting: {ha:.2f} ha over {n} blocks, "
				  f"{gap:.2f} ha off the {want:.0f} on the heading")
	return out


def _plausible_moisture(v):
	"""0.77 or 77 -> 0.77. Anything that is not a moisture reading -> None.

	The sheet writes fractions; a hand-entered percentage is accepted the same way so
	that one typed row cannot land as 7700% dry matter. 1.00 is a formula artifact,
	not a reading, and falls out on its own.
	"""
	if not isinstance(v, (int, float)) or isinstance(v, bool):
		return None
	v = flt(v)
	if v > 1.0:
		v = v / 100.0
	return v if MIN_MOISTURE <= v <= MAX_MOISTURE else None


def read_summary_maturity(folder, sheet=SUMMARY_SHEET, season=SUMMARY_SEASON, refused=None):
	"""[dict] one row per (planting, week, count size) that was actually sampled.

	The sheet is stacked sections, one per planting: fruit count size down the side,
	calendar week across the top, moisture in the cell. Three things in it are not
	measurements and must not be imported —

	  the 1.00 placeholder in every week nobody has sampled yet,
	  the Min/Max reference lines that draw the export band on the graph, and
	  the "Average All Lokitela" section at the foot, which is the mean of the
	  sections above it and would count every planting a second time.

	And the same weeks appear TWICE across the header: moisture on the left, the
	dry-matter mirror of those exact cells on the right (0.77 becomes 0.23). Only the
	moisture group is read; taking both would double every test on the estate.
	"""
	rows = _rows(os.path.join(folder, SUMMARY), sheet)
	weeks, header = [], next((r for r in rows if "Wk.7" in [str(c) for c in r]), [])
	for j, c in enumerate(header):
		# "Wk.7" is a week column; "Wk. no'" is the label on the count axis.
		label = str(c or "").replace(" ", "")
		if not label.startswith("Wk.") or not label[3:].isdigit():
			continue
		wk = int(label[3:])
		if any(w == wk for _, w in weeks):
			break                      # the dry-matter mirror starts here
		weeks.append((j, wk))

	out, area, year = [], None, None
	for r in rows:
		count, lo, hi = (list(r) + [None] * 3)[:3]
		# Export count sizes run 12 to 36. Every other value in this column is a
		# heading, and a heading either opens a section or closes the one before it.
		if not isinstance(count, (int, float)):
			text = str(count or "").strip()
			if text:
				m = SECTION_RE.match(text)
				area, year = (f"{m.group(1)} Ha", int(m.group(2))) if m else (None, None)
			continue
		if not (area and 12 <= count <= 36):
			continue
		for j, wk in weeks:
			v = r[j] if j < len(r) else None
			if v is None:
				continue
			moisture = _plausible_moisture(v)
			if moisture is None:
				if refused is not None:
					refused.append((area, wk, int(count), v))
				continue
			out.append({
				"planting_area": area, "planting_year": year, "week_number": wk,
				"fruit_count_size": int(count),
				"fruit_min_g": flt(lo) if isinstance(lo, (int, float)) else None,
				"fruit_max_g": flt(hi) if isinstance(hi, (int, float)) else None,
				"moisture_pct": moisture, "season": season, "source": SUMMARY,
			})
	return out


def import_maturity(folder="/mnt/c/Users/teddy/Downloads", commit=True):
	"""Load the lab's maturity tests. Re-runnable: the table is wiped first."""
	import datetime

	# Dry matter itself is derived on the record, not here — the doctype owns that
	# conversion so a hand-entered test and an imported one cannot disagree.
	from upande_production.api.avocadoapi import MIN_DRY_MATTER_PCT

	frappe.db.delete(MATURITY_DOCTYPE)
	refused = []
	rows = read_summary_maturity(folder, refused=refused)

	# A planting year only becomes a JOIN where this farm actually has blocks of that
	# age. The 2024 planting on this sheet is Lokitela's and the block master has no
	# Lokitela 2024 blocks at all — only Saboti ones — so those readings are stored
	# with the year in their notes and no year in the field. Left as a match they
	# would date a pick on trees on the wrong farm that bear nothing.
	known = {cint(y) for (y,) in frappe.db.sql(
		f"""select distinct planting_year from `tab{DOCTYPE}`
			where farm = %s and ifnull(planting_year, 0) > 0""", SUMMARY_FARM)}

	made, per_area, orphaned = 0, {}, {}
	for r in rows:
		# The sheet records a week and never a day, so the test is dated to the
		# Monday of that week and the field says as much. Better than a made-up day.
		try:
			test_date = datetime.date.fromisocalendar(r["season"], r["week_number"], 1)
		except ValueError:
			test_date = None
		year = r["planting_year"] if r["planting_year"] in known else None
		if not year:
			orphaned[r["planting_area"]] = r["planting_year"]
		frappe.get_doc({
			"doctype": MATURITY_DOCTYPE, "planting_area": r["planting_area"],
			"planting_year": year, "week_number": r["week_number"],
			"test_date": test_date, "fruit_count_size": r["fruit_count_size"],
			"fruit_min_g": r["fruit_min_g"], "fruit_max_g": r["fruit_max_g"],
			"moisture_pct": r["moisture_pct"], "source": r["source"],
			"notes": f"Imported from the estate's {r['season']} dry matter summary, "
					 f"section {r['planting_area']} - {r['planting_year']}. The sheet "
					 f"records moisture; dry matter is the remainder."
					 + ("" if year else f" No {SUMMARY_FARM} block is recorded as planted "
										f"in {r['planting_year']}, so this reading is "
										f"stored unassigned rather than matched."),
		}).insert(ignore_permissions=True)
		made += 1
		per_area[r["planting_area"]] = per_area.get(r["planting_area"], 0) + 1
	if commit:
		frappe.db.commit()

	print(f"maturity tests: {made} from {SUMMARY}")
	# What was thrown out, and why, so nobody has to wonder whether a reading went
	# missing. Nearly every one of these is the 1.00 the sheet parks in a week that
	# has not been sampled — an avocado that was all water would be juice.
	seen = {}
	for _area, _wk, _count, v in refused:
		seen[v] = seen.get(v, 0) + 1
	print(f"  refused {len(refused)} cells that are not moisture readings: "
		  + (", ".join(f"{n} x {v}" for v, n in sorted(seen.items(), key=lambda kv: -kv[1]))
			 or "none"))
	tot = frappe.db.sql(f"""select planting_area, planting_year, min(week_number),
		max(week_number), count(*), round(min(dry_matter_pct),1), round(max(dry_matter_pct),1),
		sum(export_ready) from `tab{MATURITY_DOCTYPE}`
		group by planting_area, planting_year order by planting_area""")
	for area, year, w0, w1, n, dmin, dmax, ready in tot:
		print(f"  {area} ({year or 'no planting year'}): {n} tests, weeks {w0}-{w1}, "
			  f"dry matter {dmin}-{dmax}%, {int(ready or 0)} at or above the "
			  f"{MIN_DRY_MATTER_PCT}% export minimum")
	# Which blocks a test speaks for, said out loud rather than implied.
	for area in sorted(per_area):
		year = next((r["planting_year"] for r in rows if r["planting_area"] == area), None)
		if area in orphaned:
			print(f"  {area} ({year} planting) is tied to NO blocks — the block master "
				  f"has no {SUMMARY_FARM} planting of {year}. Its {per_area[area]} "
				  f"readings are stored unassigned and no block inherits them.")
			continue
		print(f"  {area} covers the {frappe.db.count(DOCTYPE, {'planting_year': year, 'farm': SUMMARY_FARM})} "
			  f"{SUMMARY_FARM} blocks planted in {year}")
	# The hectarage on the headings, against the hectarage the block master surveyed.
	# Reassurance where they agree, and the loudest possible flag where they do not.
	print("  cross-check, heading hectarage against the block master:")
	match_cohorts(sorted(per_area))
	return made


# ── Days to ripen: the second maturity signal ────────────────────────────────
#
# Dry matter says the fruit is legal to cut. It does not say the fruit is ready. A
# mature avocado softens off the tree in a week or two; an immature one sits on the
# shelf and shrivels. So the estate cuts a handful, lays them out and writes down the
# day each one goes soft — an independent read on the same question, needing no oven.
#
# It is corroboration and nothing more. Nothing here gates a pick date, because the
# estate has published no threshold and this module will not invent one.

RIPENING_DOCTYPE = "Avocado Ripening Test"
RIPEN_FILE = "2026-Fruit Days to Ripen- xlsx.xlsx"
RIPEN_SHEETS = ("Big Size", "Small Size")

# Nothing softens the day it was cut, and nothing anyone would eat takes two months.
# Outside this the "average" is a formula reading over an empty trial — the sheet is
# laid out weeks ahead and most of its blocks are still blank.
MIN_DAYS_TO_RIPEN, MAX_DAYS_TO_RIPEN = 1.0, 60.0


def _under_dates(row, dates):
	"""{column: value} for the columns that sit under a real date, and no others.

	The sheet keeps its row totals immediately to the right of the last date. Summing
	the whole row would count every fruit twice.
	"""
	return {j: flt(v) for j, v in enumerate(row)
			if j in dates and isinstance(v, (int, float)) and flt(v)}


def read_days_to_ripen(folder, refused=None):
	"""[dict] one row per shelf trial: size class, harvest date, fruit, days to ripen.

	Each sheet repeats the same six-row block once per trial — Date, days from
	harvest, fruit harvested, fruit ripe, days to ripen, average. A trial nobody has
	cut fruit for yet is a heading for a week that has not happened, and is refused
	rather than imported as a zero.
	"""
	import datetime

	path = os.path.join(folder, RIPEN_FILE)
	if not os.path.exists(path):
		return []

	trials = []
	for sheet in RIPEN_SHEETS:
		cur = None
		for r in _rows(path, sheet):
			row = list(r)
			label = str((row[0] if row else None) or "").strip().lower()
			if label.startswith("date"):
				cur = {"size_class": sheet, "harvested": {}, "ripe": {}, "avg_days": None,
					   "dates": {j: getdate(c) for j, c in enumerate(row)
								 if isinstance(c, (datetime.date, datetime.datetime))}}
				trials.append(cur)
			elif cur is None:
				continue
			elif label.startswith("no' fruit harvested"):
				cur["harvested"] = _under_dates(row, cur["dates"])
			elif label.startswith("no' fruit ripe"):
				cur["ripe"] = _under_dates(row, cur["dates"])
			elif label.startswith("average days"):
				# The average sits in the total column, past the last date. '#DIV/0!'
				# is a string and falls out here; a 0 falls out on plausibility below.
				cur["avg_days"] = next((flt(c) for c in row[1:]
										if isinstance(c, (int, float))), None)

	out = []
	for t in trials:
		if not t["harvested"] or not t["dates"]:
			if refused is not None and t["dates"]:
				refused.append((t["size_class"], min(t["dates"].values()),
								"no fruit cut for this trial yet"))
			continue
		avg = t["avg_days"]
		if avg is not None and not (MIN_DAYS_TO_RIPEN <= avg <= MAX_DAYS_TO_RIPEN):
			if refused is not None:
				refused.append((t["size_class"], min(t["dates"].values()),
								f"average of {avg} days is not a ripening time"))
			avg = None
		out.append({
			"size_class": t["size_class"],
			# The day the fruit came off the tree: the first day of the trial anyone
			# actually cut fruit on.
			"harvest_date": t["dates"][min(t["harvested"])],
			"fruit_harvested": int(sum(t["harvested"].values())),
			"fruit_ripe": int(sum(t["ripe"].values())),
			"last_observed": max(t["dates"].values()),
			"avg_days_to_ripen": avg,
			"source": RIPEN_FILE,
		})
	return out


def import_ripening(folder="/mnt/c/Users/teddy/Downloads", commit=True):
	"""Load the shelf trials. Re-runnable: the table is wiped first."""
	frappe.reload_doc("Avocado Yield", "doctype", "avocado_ripening_test")
	frappe.db.delete(RIPENING_DOCTYPE)
	refused = []
	rows = read_days_to_ripen(folder, refused=refused)
	for r in rows:
		frappe.get_doc(dict(r, doctype=RIPENING_DOCTYPE, notes=(
			"Imported from the estate's days-to-ripen sheet. An independent read on "
			"maturity: mature fruit softens off the tree, immature fruit sits."
		))).insert(ignore_permissions=True)
	if commit:
		frappe.db.commit()

	done = [r for r in rows if r["avg_days_to_ripen"]]
	print(f"ripening trials: {len(rows)} loaded, {len(refused)} refused")
	for size, day, why in refused:
		print(f"  refused {size} {day}: {why}")
	for r in sorted(rows, key=lambda r: r["harvest_date"]):
		avg = (f"{r['avg_days_to_ripen']:.0f} days to ripen"
			   if r["avg_days_to_ripen"] else "still on the shelf, no average yet")
		print(f"  {r['size_class']:<10} cut {r['harvest_date']}: "
			  f"{r['fruit_harvested']} fruit, {r['fruit_ripe']} ripe — {avg}")
	if done:
		print(f"  {len(done)} completed trial(s), averaging "
			  f"{sum(r['avg_days_to_ripen'] for r in done) / len(done):.1f} days")
	return len(rows)


@frappe.whitelist()
def block_dry_matter():
	"""Latest dry matter for every block, taken from its planting's maturity test.

	Nobody tests a block. The lab tests a planting — one sample stands for every
	block of that age — so this is the honest way to give the harvest calendar a
	pick date per block, and every row says `measured_on: cohort` so a page can
	label it as the weaker evidence it is. A per-block figure would need per-block
	sampling, which the estate does not do today.

	Averaged across the fruit count sizes tested that week, because a big fruit and
	a small one off the same trees mature at different speeds and the block gets
	picked once. `sizes` is how many went into the average — one size is a hint,
	five is a measurement.
	"""
	from upande_production.api.avocadoapi import MIN_DRY_MATTER_PCT

	tests = frappe.get_all(
		MATURITY_DOCTYPE, filters={"planting_year": [">", 0]},
		fields=["planting_year", "planting_area", "week_number", "test_date", "dry_matter_pct"],
		order_by="test_date asc", limit_page_length=0,
	)
	# Latest week per planting only. An older week is a fruit that has since filled.
	latest = {}
	for t in tests:
		cur = latest.get(t.planting_year)
		if cur is None or t.test_date > cur[0].test_date:
			latest[t.planting_year] = [t]
		elif t.test_date == cur[0].test_date:
			cur.append(t)

	out = []
	for b in frappe.get_all(DOCTYPE, fields=["block_code", "planting_year", "bearing_trees"],
							limit_page_length=0):
		group = latest.get(b.planting_year)
		if not group:
			continue
		dm = round(sum(flt(t.dry_matter_pct) for t in group) / len(group), 1)
		first = group[0]
		out.append({
			"block": b.block_code,
			"planting_year": b.planting_year,
			"planting_area": first.planting_area,
			"dry_matter_pct": dm,
			"sizes": len(group),
			"week_number": first.week_number,
			"sample_date": str(first.test_date),
			"ready": dm >= MIN_DRY_MATTER_PCT,
			"shortfall_pct": round(MIN_DRY_MATTER_PCT - dm, 1) if dm < MIN_DRY_MATTER_PCT else 0,
			"measured_on": "cohort",
			"basis": f"{first.planting_area} planting, week {first.week_number}, "
					 f"average of {len(group)} fruit sizes — not this block",
		})
	out.sort(key=lambda r: -r["dry_matter_pct"])
	unsampled = [y for y in {b.planting_year for b in
							 frappe.get_all(DOCTYPE, fields=["planting_year"])}
				 if y and y not in latest]
	return {
		"minimum_pct": MIN_DRY_MATTER_PCT,
		"blocks": out,
		"sampled": len(out),
		"measured_on": "cohort",
		"unsampled_planting_years": sorted(unsampled),
	}


def demo():
	"""Runnable check on the two things here that are easy to get wrong: the
	placeholders must not be read as tests, and moisture must invert to dry matter.
	"""
	from upande_production.api.avocadoapi import dry_matter_from_moisture

	rows = read_summary_maturity("/mnt/c/Users/teddy/Downloads")
	assert rows, "no maturity readings found at all"
	assert all(MIN_MOISTURE <= r["moisture_pct"] <= MAX_MOISTURE for r in rows)
	assert not any(r["moisture_pct"] == 1 for r in rows), "the 1.00 placeholder got in"
	by_area = {}
	for r in rows:
		by_area.setdefault(r["planting_area"], []).append(r)
	# Four sections and no more. A fifth would be "Average All Lokitela", which is the
	# mean of the other four and would count every planting twice.
	assert set(by_area) == {"23 Ha", "70 Ha", "65 Ha", "56 Ha"}, sorted(by_area)
	# The moisture group and its dry-matter mirror carry the same weeks. Read both and
	# every planting doubles, with half the readings inverted.
	for area, rs in by_area.items():
		seen = {(r["week_number"], r["fruit_count_size"]) for r in rs}
		assert len(seen) == len(rs), f"{area} read a week twice — the mirror got in"
	# The sheet's own computed dry-matter column is the check on the conversion:
	# 0.81 moisture is written there as 0.19, which is 19%.
	assert dry_matter_from_moisture(0.81) == 19.0
	assert dry_matter_from_moisture(0.818) == 18.2

	# The hectarage cross-check. It must land where the sheet's own headings say —
	# and it must refuse to place 56 Ha, whose planting the block master lacks.
	cohorts = match_cohorts(sorted(by_area), verbose=False)
	assert cohorts == {"23 Ha": 2018, "70 Ha": 2022, "65 Ha": 2023}, cohorts
	areas = dict(frappe.db.sql(f"""select planting_year, sum(area_ha) from `tab{DOCTYPE}`
		where ifnull(planting_year, 0) > 0 group by planting_year"""))
	for area, year in cohorts.items():
		want = flt(area.split()[0])
		assert abs(flt(areas[year]) - want) <= COHORT_TOLERANCE_HA
		# And the match has to be the only one available. The 65 Ha and 70 Ha
		# plantings are five hectares apart; a tolerance that reached from a
		# heading to both of them would mislabel a whole cohort's pick date and
		# nothing downstream would ever notice.
		reachable = [y for y, ha in areas.items() if abs(flt(ha) - want) <= COHORT_TOLERANCE_HA]
		assert reachable == [year], f"{area} could be any of {reachable}"
	# Widen it far enough and a Saboti planting starts answering for Lokitela fruit.
	assert match_cohorts(sorted(by_area), tolerance_ha=0.001, verbose=False) == {}

	blocks = block_dry_matter()
	expect = sum(frappe.db.count(DOCTYPE, {"planting_year": y}) for y in set(cohorts.values()))
	assert blocks["sampled"] == expect, f"{blocks['sampled']} blocks got a pick date, expected {expect}"
	assert all(b["measured_on"] == "cohort" for b in blocks["blocks"]), "a row claims to be a block reading"
	assert all(b["sizes"] >= 1 for b in blocks["blocks"])

	# The shelf trials. Only trials somebody actually cut fruit for, and an average
	# only where one was measured — a 0 in that cell is a formula over an empty week.
	trials = read_days_to_ripen("/mnt/c/Users/teddy/Downloads")
	assert trials, "no ripening trials found at all"
	assert all(t["fruit_harvested"] > 0 for t in trials), "an empty trial got in"
	assert all(t["fruit_ripe"] <= t["fruit_harvested"] for t in trials), \
		"more fruit came off the shelf than went on it — the totals column got summed"
	assert all(t["avg_days_to_ripen"] is None
			   or MIN_DAYS_TO_RIPEN <= t["avg_days_to_ripen"] <= MAX_DAYS_TO_RIPEN
			   for t in trials)
	print(f"ok: {len(rows)} readings across {len(by_area)} plantings, no placeholders; "
		  f"{blocks['sampled']} blocks carry a cohort dry matter; {len(trials)} shelf trials")


def load_all(folder="/mnt/c/Users/teddy/Downloads"):
	reset(folder=folder)
	report_late_actuals(folder=folder)
	import_yearly(folder=folder)
	import_estimate(folder=folder)
	import_maturity(folder=folder)
	import_ripening(folder=folder)
