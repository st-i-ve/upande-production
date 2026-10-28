"""Desk API for protocol versions and approval. Same envelope as api.production: data or {"error": msg}."""

import frappe

from upande_production.api.envelope import run
from upande_production.production.logic import protocols as logic


@frappe.whitelist(methods=["POST"])
@run
def list_protocols(crop):
	return logic.list_protocols(crop)


@frappe.whitelist(methods=["POST"])
@run
def pending_protocols(crop=None):
	return logic.pending_list(crop or None)


@frappe.whitelist(methods=["POST"])
@run
def new_version(name):
	return logic.new_version(name)


@frappe.whitelist(methods=["POST"])
@run
def submit_for_approval(name):
	return logic.submit_for_approval(name)


@frappe.whitelist(methods=["POST"])
@run
def approve(name):
	return logic.approve(name)


@frappe.whitelist(methods=["POST"])
@run
def send_back(name, note=""):
	return logic.send_back(name, note)


@frappe.whitelist(methods=["POST"])
@run
def reject(name, note=""):
	return logic.reject(name, note)


@frappe.whitelist(methods=["POST"])
@run
def diff(name):
	return logic.diff(name)


@frappe.whitelist(methods=["POST"])
@run
def save_draft(data):
	"""Edit a Draft (steps, item). Active/Pending/Superseded versions are refused by the doctype."""
	return logic.save_draft(data)
