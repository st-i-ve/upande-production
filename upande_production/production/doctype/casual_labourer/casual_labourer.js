frappe.ui.form.on("Casual Labourer", {
	setup(frm) {
		frm.set_query("supervisor", () => ({
			query: "upande_production.production.logic.supervisors.supervisor_query",
		}));
	},
});
