import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import protocols as api
from upande_production.production.doctype.production_protocol.production_protocol import validate_tables
from upande_production.production.logic import approvals, plans, protocols as P
from upande_production.production.logic.weeks import iso_of


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=role.split()[-1], send_welcome_email=0, roles=[{"role": role}])
	return email


class TestProtocols(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for uom in ("Kg",):
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="TP Farm", company=cls.company, abbreviation="TPF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="TP Crop", crop_key="tp-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Production Operation", crop=cls.crop.name, operation_name="TP Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.sup = _user("tp_supervisor@example.com", "Production Supervisor")
		cls.mgr = _user("tp_manager@example.com", "Production Manager")
		cls.viewer = _user("tp_viewer@example.com", "Production Viewer")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _active(self, name):
		return _make("Production Protocol", protocol_name=name, crop=self.crop.name, version_status="Active",
			steps=[{"operation": self.op.name, "day_offset": 3, "repeat_every_days": 7, "repeat_count": 2, "planned_qty": 10}])

	def _pending(self, name):
		a = self._active(name)
		v2 = P.new_version(a.name)["name"]
		P.submit_for_approval(v2)
		return a, v2

	def test_new_version_copies_steps(self):
		a = self._active("TPV Copy")
		self.assertEqual(a.protocol_family, a.name)
		res = P.new_version(a.name)
		v2 = frappe.get_doc("Production Protocol", res["name"])
		self.assertEqual((v2.version, v2.version_status, v2.previous_version), (2, "Draft", a.name))
		self.assertEqual(v2.protocol_family, a.protocol_family)
		self.assertEqual(len(v2.steps), 1)
		self.assertEqual(v2.steps[0].planned_qty, 10)
		with self.assertRaises(frappe.ValidationError):  # one in progress at a time
			P.new_version(a.name)

	def test_new_version_only_from_active(self):
		a = self._active("TPV OnlyActive")
		d = frappe.get_doc("Production Protocol", P.new_version(a.name)["name"])
		with self.assertRaises(frappe.ValidationError):
			P.new_version(d.name)

	def test_active_is_read_only(self):
		a = self._active("TPV ReadOnly")
		a.reload()
		a.item = None
		a.steps[0].planned_qty = 99
		with self.assertRaises(frappe.ValidationError):
			a.save()

	def test_approve_supersedes_previous(self):
		a, v2 = self._pending("TPV Approve")
		with self.assertRaises(frappe.ValidationError):  # Pending cannot be edited
			d = frappe.get_doc("Production Protocol", v2)
			d.steps[0].planned_qty = 1
			d.save()
		P.approve(v2)
		self.assertEqual(frappe.db.get_value("Production Protocol", a.name, "version_status"), "Superseded")
		new = frappe.get_doc("Production Protocol", v2)
		self.assertEqual(new.version_status, "Active")
		self.assertEqual(new.approved_by, "Administrator")
		self.assertTrue(new.approved_at)
		fam = P.list_protocols(self.crop.name)["families"]
		f = next(f for f in fam if f["family"] == a.name)
		self.assertEqual(f["active"], v2)
		self.assertEqual([v["version"] for v in f["versions"]], [2, 1])

	def test_send_back_needs_note(self):
		a, v2 = self._pending("TPV SendBack")
		with self.assertRaises(frappe.ValidationError):
			P.send_back(v2, "  ")
		P.send_back(v2, "Rate too high")
		d = frappe.get_doc("Production Protocol", v2)
		self.assertEqual((d.version_status, d.review_note), ("Draft", "Rate too high"))
		d.steps[0].planned_qty = 5  # editable again
		d.save()
		P.submit_for_approval(v2)
		with self.assertRaises(frappe.ValidationError):
			P.reject(v2, "")
		P.reject(v2, "No")
		self.assertEqual(frappe.db.get_value("Production Protocol", v2, "version_status"), "Rejected")

	def test_permissions(self):
		a, v2 = self._pending("TPV Perms")
		frappe.set_user(self.sup)
		with self.assertRaises(frappe.PermissionError):
			P.approve(v2)
		self.assertIn("error", api.approve(v2))
		self.assertIn("error", api.send_back(v2, "x"))
		d = frappe.get_doc("Production Protocol", P.new_version(self._active("TPV Perms2").name)["name"])
		self.assertNotIn("error", api.submit_for_approval(d.name))  # supervisors draft and submit
		frappe.set_user(self.viewer)
		self.assertIn("error", api.new_version(a.name))
		frappe.set_user(self.mgr)
		self.assertNotIn("error", api.approve(v2))

	def test_diff(self):
		a = self._active("TPV Diff")
		v2 = frappe.get_doc("Production Protocol", P.new_version(a.name)["name"])
		v2.steps[0].planned_qty = 12
		v2.append("steps", {"operation": self.op.name, "day_offset": 30, "repeat_count": 1})
		v2.save()
		d = P.diff(v2.name)
		kinds = sorted(s["change"] for s in d["steps"])
		self.assertEqual(kinds, ["added", "changed"])
		ch = next(s for s in d["steps"] if s["change"] == "changed")
		self.assertEqual(ch["changes"], [{"field": "planned_qty", "before": 10, "after": 12}])

	def test_only_active_plans(self):
		unit = _make("Production Unit", unit_name="TP Unit", unit_type="Orchard Block", crop=self.crop.name,
			farm=self.farm.name, company=self.company)
		a = self._active("TPV Plans")
		v2 = P.new_version(a.name)["name"]  # Draft
		with self.assertRaises(frappe.ValidationError):  # drafts cannot be offered for new cycles
			_make("Production Crop Cycle", unit=unit.name, crop=self.crop.name,
				start_date=add_days(today(), -7), protocol=v2, status="Active")
		cy = _make("Production Crop Cycle", unit=unit.name, crop=self.crop.name,
			start_date=add_days(today(), -7), protocol=a.name, status="Active")
		monday = add_days(today(), -frappe.utils.getdate(today()).weekday())
		y, w = iso_of(monday)
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		self.assertGreater(plans.generate_week(plan.name), 0)
		# once a draft is pinned (forced) it still does not plan
		frappe.db.set_value("Production Protocol", a.name, "version_status", "Draft")
		plan2 = plans.get_or_create_plan(self.crop.name, self.farm.name, *iso_of(add_days(monday, 7)))
		self.assertEqual(plans.generate_week(plan2.name), 0)
		# superseded versions keep driving the cycles pinned to them
		frappe.db.set_value("Production Protocol", a.name, "version_status", "Superseded")
		self.assertGreaterEqual(plans.generate_week(plan2.name), 0)
		self.assertEqual(cy.protocol, a.name)

	def test_counts(self):
		self._pending("TPV Count")
		res = approvals.approval_counts()
		row = next(c for c in res["crops"] if c["crop"] == self.crop.name)
		self.assertEqual(row["protocols_pending"], 1)
		self.assertGreaterEqual(res["protocols_pending"], 1)
		for k in ("pending", "stale", "crop_key"):
			self.assertIn(k, row)
		self.assertIn("total", res)


class TestProtocolTables(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.crop = _make("Production Crop", crop_name="TPT Crop", crop_key="tpt-crop", unit_label="Block", yield_uom="Kg")
		mk = lambda n, t: _make("Production Operation", crop=cls.crop.name, operation_name=n, category="Other",
			work_uom="Kg", default_rate=1, activity_type=t).name
		cls.cap, cls.key, cls.cul = mk("TPT Excavate", "Capital"), mk("TPT Prune", "Key activity"), mk("TPT Weed", "Cultural")

	def _doc(self, **kw):
		return frappe._dict({"key_activities": [], "cultural_activities": [], "capital_activities": [], **kw})

	def test_key_activities_out_of_week_order_refused(self):
		d = self._doc(key_activities=[{"operation": self.key, "week": 7}, {"operation": self.key, "week": 3}])
		with self.assertRaises(frappe.ValidationError) as cm:
			validate_tables(d)
		self.assertIn("Row 2 (week 3) comes after row 1 (week 7)", str(cm.exception))
		validate_tables(self._doc(key_activities=[{"operation": self.key, "week": 3}, {"operation": self.key, "week": 3}]))
		with self.assertRaises(frappe.ValidationError):
			validate_tables(self._doc(key_activities=[{"operation": self.key, "week": 0}]))

	def test_cultural_interval_rules(self):
		row = lambda **k: self._doc(cultural_activities=[{"operation": self.cul, **k}])
		with self.assertRaises(frappe.ValidationError):
			validate_tables(row(schedule="Interval"))
		with self.assertRaises(frappe.ValidationError):
			validate_tables(row(schedule="As needed", interval_weeks=2))
		validate_tables(row(schedule="As needed"))
		validate_tables(row(schedule="Interval", interval_weeks=2))

	def test_cycle_protocol_operations_types(self):
		with self.assertRaises(frappe.ValidationError):
			validate_tables(self._doc(key_activities=[{"operation": self.cap, "week": 1}]))
		with self.assertRaises(frappe.ValidationError):
			validate_tables(self._doc(cultural_activities=[{"operation": self.cap, "schedule": "As needed"}]))
		with self.assertRaises(frappe.ValidationError):
			validate_tables(self._doc(capital_activities=[{"operation": self.cul}]))
		validate_tables(self._doc(capital_activities=[{"operation": self.cap}]))

	def test_old_steps_only_protocol_still_saves(self):
		p = _make("Production Protocol", protocol_name="TPT Old", crop=self.crop.name, version_status="Active",
			steps=[{"operation": self.cul, "day_offset": 3, "repeat_count": 1}])
		self.assertEqual(len(p.steps), 1)
