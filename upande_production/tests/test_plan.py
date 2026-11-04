import frappe
from frappe.tests.utils import FrappeTestCase


class TestWeekPlan(FrappeTestCase):
    """The week's work board and the map's live-operation feed."""

    def setUp(self):
        from upande_production import plan
        self.plan = plan
        self.house = frappe.db.get_value("Crop Cycle", {"status": ("!=", "Ended")}, "greenhouse")
        if not self.house:
            self.skipTest("no crop cycles on this site")
        self.year, self.week = 2035, 12
        self._clean()

    def tearDown(self):
        self._clean()
        frappe.db.commit()

    def _clean(self):
        for n in frappe.db.get_all("Production Plan Form",
                                   {"plan_year": self.year, "plan_week": self.week},
                                   pluck="name"):
            frappe.delete_doc("Production Plan Form", n, force=1, ignore_permissions=True)

    def test_add_task_creates_the_plan_then_reuses_it(self):
        a = self.plan.add_task(self.house, "Cut block A", "Harvest", "Monday",
                               year=self.year, week=self.week)
        b = self.plan.add_task(self.house, "Spray round", "Spray", "Tuesday",
                               year=self.year, week=self.week)
        self.assertEqual(a["plan"], b["plan"], "a second task must not open a second plan")
        self.assertEqual(b["tasks"], 2)

    def test_unknown_operation_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self.plan.add_task(self.house, "Nonsense", "Teleport",
                               year=self.year, week=self.week)

    def test_status_transitions_stamp_the_clock(self):
        self.plan.add_task(self.house, "Cut block A", "Harvest", "Monday",
                           year=self.year, week=self.week)
        w = self.plan.week_plan(self.year, self.week)
        task = w["by_day"]["Monday"][0]["task"]

        self.plan.set_task_status(task, "In Progress")
        row = frappe.db.get_value("Production Plan Task", task,
                                  ["status", "started_at", "completed_at"], as_dict=True)
        self.assertEqual(row.status, "In Progress")
        self.assertIsNotNone(row.started_at)
        self.assertIsNone(row.completed_at)

        self.plan.set_task_status(task, "Done", note="cut early")
        row = frappe.db.get_value("Production Plan Task", task,
                                  ["status", "completed_at", "completion_note"], as_dict=True)
        self.assertEqual(row.status, "Done")
        self.assertIsNotNone(row.completed_at)
        self.assertEqual(row.completion_note, "cut early")

        # Reopening must clear the clock, or a re-run looks already finished.
        self.plan.set_task_status(task, "Open")
        row = frappe.db.get_value("Production Plan Task", task,
                                  ["started_at", "completed_at"], as_dict=True)
        self.assertIsNone(row.started_at)
        self.assertIsNone(row.completed_at)

    def test_progress_counts_done_and_skipped(self):
        for i, day in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday")):
            self.plan.add_task(self.house, f"Job {i}", "Scout", day,
                               year=self.year, week=self.week)
        w = self.plan.week_plan(self.year, self.week)
        self.assertEqual(w["total"], 4)
        self.assertEqual(w["progress"], 0)
        tasks = [t["task"] for d in w["days"] for t in w["by_day"][d]]
        self.plan.set_task_status(tasks[0], "Done")
        self.plan.set_task_status(tasks[1], "Skipped")
        w = self.plan.week_plan(self.year, self.week)
        self.assertEqual(w["progress"], 50, "a skipped task is dealt with, not outstanding")

    def test_house_tasks_of_an_unplanned_house_is_empty_not_an_error(self):
        r = self.plan.house_tasks(self.house, self.year, self.week)
        self.assertEqual(r["tasks"], [])
        self.assertEqual(r["open"], 0)

    def test_live_operations_ignores_another_week(self):
        # 2035-W12 is not the current week, so nothing in it is "under way".
        self.plan.add_task(self.house, "Cut block A", "Harvest", "Monday",
                           year=self.year, week=self.week)
        w = self.plan.week_plan(self.year, self.week)
        self.plan.set_task_status(w["by_day"]["Monday"][0]["task"], "In Progress")
        live = self.plan.live_operations(self.year, self.week)
        self.assertEqual(live["houses"], {},
                         "only the current week can have work under way")
