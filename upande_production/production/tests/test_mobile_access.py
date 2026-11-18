from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.mobile import access, api, harvest

ROLES = {
	"manager": ["Production Manager"],
	"avocado_manager": ["Avocado Production Manager"],
	"system": ["System Manager"],
	"supervisor": ["Production Supervisor"],
	"viewer": ["Production Viewer"],
	"none": ["Guest", "All"],
}
# farm_report, plan_view, plan_tick_off, plan_manage, harvest
EXPECT = {
	"manager": (1, 1, 1, 1, 1),
	"avocado_manager": (1, 1, 1, 1, 1),
	"system": (1, 1, 1, 1, 1),
	"supervisor": (0, 1, 1, 0, 1),
	"viewer": (0, 1, 0, 0, 0),
	"none": (0, 0, 0, 0, 0),
}
CAPS = ("farm_report", "plan_view", "plan_tick_off", "plan_manage", "harvest")


def as_roles(key):
	return patch.multiple(frappe, get_roles=lambda user=None: ROLES[key]), patch.dict(
		frappe.local.session, {"user": f"{key}@x.test"})


class TestMobileAccess(IntegrationTestCase):
	def caps(self, key):
		p1, p2 = as_roles(key)
		with p1, p2:
			return access.capabilities()

	def test_capability_matrix(self):
		for key, exp in EXPECT.items():
			c = self.caps(key)
			self.assertEqual(tuple(int(c[k]) for k in CAPS), exp, key)
			self.assertEqual(c["any"], any(exp), key)

	def test_administrator_has_everything(self):
		self.assertTrue(all(access.capabilities("Administrator")[k] for k in CAPS))

	def test_session_info_reports_capabilities_and_legacy_flag(self):
		for key in ("supervisor", "manager", "none"):
			p1, p2 = as_roles(key)
			with p1, p2:
				info = harvest.get_session_info()
			self.assertEqual(info["is_farm_manager"], bool(EXPECT[key][0]), key)
			self.assertEqual(info["capabilities"]["farm_report"], bool(EXPECT[key][0]), key)

	def test_farm_report_refuses_supervisor_and_viewer(self):
		for key in ("supervisor", "viewer", "none"):
			p1, p2 = as_roles(key)
			with p1, p2:
				res = harvest.farm_manager_report(period="today")
			self.assertIn("error", res, key)
		p1, p2 = as_roles("manager")
		with p1, p2:
			self.assertNotIn("error", harvest.farm_manager_report(period="today"))

	def _call(self, key, fn):
		frappe.response.pop("data", None)
		p1, p2 = as_roles(key)
		with p1, p2, patch.object(api, "_denied", return_value=False), patch.object(
			api, "_payload", return_value={}):
			fn()
		return frappe.response.get("data")

	def test_plan_management_is_managers_only(self):
		for fn in (api.productionAddTask, api.productionGeneratePlan):
			res = self._call("supervisor", fn)
			self.assertEqual(res, {"error": "You do not have permission to do this."}, fn.__name__)
			res = self._call("manager", fn)  # passes the guard, fails on the missing inputs
			self.assertNotIn("permission", res["error"], fn.__name__)

	def test_viewer_cannot_tick_off_or_resubmit_but_may_view(self):
		for fn in (api.productionUpdateTask, api.productionRecordUnplannedWork, api.productionResubmitWork,
				api.productionRecordHarvest):
			res = self._call("viewer", fn)
			self.assertEqual(res, {"error": "You do not have permission to do this."}, fn.__name__)
		res = self._call("viewer", api.productionListWeekPlans)
		self.assertFalse(isinstance(res, dict) and "permission" in res.get("error", ""))

	def test_supervisor_may_tick_off(self):
		res = self._call("supervisor", api.productionUpdateTask)
		self.assertNotIn("permission", res["error"])

	def test_no_role_refused_everywhere(self):
		for fn in (api.productionListWeekPlans, api.productionUpdateTask, api.productionAddTask):
			self.assertEqual(self._call("none", fn), {"error": "You do not have permission to do this."})
