"""QR codes for machine labels.

Ported from upande_scp (serverscripts/qr/qr_generator.py, ``generate_qr_base64``): same
defaults (box size 4, a 2-module quiet zone, error correction chosen per label). SCP renders a
PNG with the ``qrcode`` library; that library is not on every bench, so this port falls back to
``pyqrcode`` (a Frappe dependency, used by its two-factor setup) and renders SVG, which needs no
image library and prints sharp at any label size.

Labels carry the machine's ``qr_code`` token inside a link to the scan screen, so any phone
camera opens the right page; the app's own scanner reads the token out of the same link.
"""

import base64
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import frappe

SCAN_PARAM = "machine"
SCAN_PATH = "/production_app"
SCAN_HASH = "#/_/scan"  # the app lands the unknown crop "_" on the user's first crop, view kept


def scan_url(token: str) -> str:
	"""The link printed in a machine's QR code."""
	return frappe.utils.get_url(f"{SCAN_PATH}?{SCAN_PARAM}={token}{SCAN_HASH}")


def parse_scan_code(text) -> str:
	"""The machine token in whatever a scanner read: the label's link (``?machine=TOKEN``) or the
	bare token typed by hand. Empty string when there is nothing."""
	text = str(text or "").strip()
	if not text:
		return ""
	if f"{SCAN_PARAM}=" in text:
		parsed = urlparse(text)
		for part in (parsed.query, parsed.fragment.split("?", 1)[-1] if "?" in parsed.fragment else ""):
			value = parse_qs(part).get(SCAN_PARAM)
			if value and value[0].strip():
				return value[0].strip()
	return text


def qr_data_uri(payload: str, box_size: int = 4, border: int = 2, error_correction: str = "M") -> str | None:
	"""A data: URI with the QR image (PNG via ``qrcode`` when installed, else SVG via ``pyqrcode``),
	or None when neither library can render it."""
	try:
		import qrcode

		levels = {
			"L": qrcode.constants.ERROR_CORRECT_L,
			"M": qrcode.constants.ERROR_CORRECT_M,
			"Q": qrcode.constants.ERROR_CORRECT_Q,
			"H": qrcode.constants.ERROR_CORRECT_H,
		}
		qr = qrcode.QRCode(version=None, error_correction=levels.get(str(error_correction).upper(),
			qrcode.constants.ERROR_CORRECT_L), box_size=box_size, border=border)
		qr.add_data(str(payload))
		qr.make(fit=True)
		buf = BytesIO()
		qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
		return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
	except ImportError:
		pass
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Production QR: render error")
		return None
	try:
		import pyqrcode

		level = str(error_correction).upper()
		code = pyqrcode.create(str(payload), error=level if level in {"L", "M", "Q", "H"} else "L")
		buf = BytesIO()
		code.svg(buf, scale=box_size, quiet_zone=border, background="#fff", xmldecl=False, svgns=True, omithw=True)
		return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Production QR: no QR library")
		return None
