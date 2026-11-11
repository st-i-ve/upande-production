// Copyright (c) 2026, Upande and contributors
// For license information, please see license.txt

frappe.ui.form.on("Silage Cycle", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Issue inputs"), () => {
				frappe.new_doc("Stock Entry", {
					stock_entry_type: "Material Issue",
					purpose: "Material Issue",
					company: frm.doc.company,
					production_silage_cycle: frm.doc.name,
				});
			});
		}
		if (frm.doc.receipt_stock_entry) {
			frm.add_custom_button(__("Pit receipt"), () => frappe.set_route("Form", "Stock Entry", frm.doc.receipt_stock_entry));
		}
	},
});
