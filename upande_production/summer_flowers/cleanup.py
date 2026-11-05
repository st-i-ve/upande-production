# Copyright (c) 2026, James Kiruga and contributors
# For license information, please see license.txt
"""Data cleanups for summer flower protocols, run by hand.

    bench --site X execute upande_production.summer_flowers.cleanup.refresh_protocols
    bench --site X execute upande_production.summer_flowers.cleanup.refresh_protocols --kwargs "{'apply': True}"
"""

import frappe

from upande_production.summer_flowers import crop_protocol as cp

REFRESH_NOTE = "data refresh"


def _protocol_names(names=None):
	if names:
		return list(names)
	return frappe.get_all(cp.PROTOCOL_DOCTYPE, filters={"custom_is_summer_flower": 1}, pluck="name",
	                      order_by="name asc", limit_page_length=0)


def _missing_links(name):
	"""Link targets the protocol (or its rows) points at that no longer exist, as readable strings."""
	doc = frappe.get_doc(cp.PROTOCOL_DOCTYPE, name)
	invalid, cancelled = doc.get_invalid_links()
	for child in doc.get_all_children():
		result = child.get_invalid_links()
		invalid.extend(result[0])
		cancelled.extend(result[1])
	return [each[2] for each in invalid] + ["{0} (cancelled)".format(each[2]) for each in cancelled]


def _refresh_one(name):
	"""Recompute and save one protocol, keeping its workflow status.

	An Approved protocol stays Approved: a data refresh is not a re-approval. The
	save guard would drop it to Draft where the numbers now differ from the current
	snapshot, so in that case a fresh snapshot is written the way approval writes it
	(noted "data refresh") and the status is put back. Returns {status, action, version}.
	"""
	doc = frappe.get_doc(cp.PROTOCOL_DOCTYPE, name)
	status = doc.get("custom_sf_protocol_status")
	reason = doc.get("custom_sf_change_reason")
	doc.flags.sf_force_recompute = True
	doc.flags.ignore_permissions = True
	doc.save()

	result = {"status": status, "action": "refreshed", "version": None}
	if status == "Approved":
		doc = frappe.get_doc(cp.PROTOCOL_DOCTYPE, name)
		changed = cp.diff_against_current(doc)
		if changed is None or changed:
			doc.db_set("custom_sf_change_reason", REFRESH_NOTE, update_modified=False)
			try:
				out = cp.approve(name)  # sets Approved itself
				result["version"] = out["version"]
				result["action"] = "refreshed + snapshot"
			finally:
				doc.db_set("custom_sf_change_reason", reason, update_modified=False)
	# Whatever the save guard did to the status, the protocol keeps the one it had.
	if frappe.db.get_value(cp.PROTOCOL_DOCTYPE, name, "custom_sf_protocol_status") != status:
		frappe.db.set_value(cp.PROTOCOL_DOCTYPE, name, "custom_sf_protocol_status", status,
		                    update_modified=False)
		doc = frappe.get_doc(cp.PROTOCOL_DOCTYPE, name)
		doc.db_set("custom_sf_pending_changes", None, update_modified=False) \
			if status == "Approved" else None
	return result


def refresh_protocols(apply=False, names=None):
	"""Bring every summer flower protocol's derived fields up to what the code now gives.

	apply=False (default) is a dry run: the per-protocol diff, nothing written.
	apply=True recomputes and saves, keeping each protocol's workflow status, and writes
	a fresh Crop Protocol Version (note "data refresh") for the Approved ones whose
	numbers moved. A protocol that cannot be recomputed (a link to a user or record that
	no longer exists, a validation error) is skipped and reported, never fatal.

	Returns {apply, refreshed: [...], skipped: [...], unchanged: [...], protocols: [...]}.
	"""
	apply = frappe.parse_json(apply) if isinstance(apply, str) else apply
	report = {"apply": bool(apply), "refreshed": [], "skipped": [], "unchanged": [], "protocols": []}
	for name in _protocol_names(names):
		diff = cp.recompute_diff(name)
		row = {"name": name, "status": frappe.db.get_value(cp.PROTOCOL_DOCTYPE, name, "custom_sf_protocol_status"),
		       "changes": diff["changes"], "error": diff["error"], "action": None}
		report["protocols"].append(row)
		if diff["error"]:
			row["action"] = "skipped"
			report["skipped"].append({"name": name, "reason": diff["error"]})
			continue
		try:
			missing = _missing_links(name)
		except Exception as e:
			missing = []
			row["error"] = str(e)[:300]
		if missing:
			row["action"] = "skipped"
			row["error"] = "Missing link target: " + "; ".join(missing)
			report["skipped"].append({"name": name, "reason": row["error"]})
			continue
		if not diff["changes"]:
			row["action"] = "unchanged"
			report["unchanged"].append(name)
			continue
		if not apply:
			row["action"] = "would refresh"
			report["refreshed"].append(name)
			continue
		frappe.db.savepoint("sf_refresh_protocol")
		try:
			res = _refresh_one(name)
		except Exception as e:
			try:
				frappe.db.rollback(save_point="sf_refresh_protocol")
			except Exception:
				frappe.db.rollback()
			row["action"] = "skipped"
			row["error"] = "{0}: {1}".format(type(e).__name__, str(e)[:300])
			report["skipped"].append({"name": name, "reason": row["error"]})
			continue
		row.update({"action": res["action"], "version": res["version"]})
		report["refreshed"].append(name)
		frappe.db.commit()
	if apply:
		frappe.db.commit()
	return report
