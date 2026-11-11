"""GPS fixes as SCP's field apps send them, checked before they are stored.

Ported from upande_scp (mobile/create_sprayer_entry.py and mobile/geo_utils.py): a fix is
``latitude``, ``longitude`` and an optional ``accuracy`` in metres (the phone's own estimate),
taken with ``captured_at``. SCP refuses an entry without coordinates; here a fix is optional
(a user may refuse the browser's location prompt) but, when one is sent, it must be a real
place on the globe. Zone detection (shapely / pyproj) is not ported: a machine's position is a
point on the map, not a bed or a tree.

Location is read on the phone or in the browser ONLY at the moment a machine's QR code is
scanned; nothing here asks for or stores a track.
"""

import frappe
from frappe import _
from frappe.utils import flt


def _number(v):
	if v is None or (isinstance(v, str) and not v.strip()):
		return None
	try:
		return float(v)
	except (TypeError, ValueError):
		frappe.throw(_("GPS value {0} is not a number").format(v), frappe.ValidationError)


def check_fix(latitude, longitude, accuracy=None) -> tuple[float, float, float | None] | None:
	"""(lat, lng, accuracy) of a valid fix, None when no fix was sent. Throws on half a fix,
	out-of-range coordinates, the (0, 0) "no fix" placeholder some phones send, or a negative
	accuracy."""
	lat, lng, acc = _number(latitude), _number(longitude), _number(accuracy)
	if lat is None and lng is None:
		return None
	if lat is None or lng is None:
		frappe.throw(_("A GPS fix needs both latitude and longitude"), frappe.ValidationError)
	if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
		frappe.throw(_("GPS position {0}, {1} is not on the globe").format(lat, lng), frappe.ValidationError)
	if lat == 0 and lng == 0:
		frappe.throw(_("The phone sent no GPS position (0, 0)"), frappe.ValidationError)
	if acc is not None and acc < 0:
		frappe.throw(_("GPS accuracy cannot be negative"), frappe.ValidationError)
	return round(lat, 7), round(lng, 7), (round(flt(acc), 1) if acc is not None else None)
