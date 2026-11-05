// Out-of-date marker on the Crop Protocol form.
//
// A save with no edit leaves a protocol alone, so a protocol whose stored derived
// values have drifted from what the code now computes would stay that way unseen.
// This asks the server (read-only) what a recalculation would change and says so,
// in orange, with a Recalculate button that does it on purpose.
frappe.ui.form.on("Crop Protocol", {
	refresh(frm) {
		frm.set_intro("");
		if (frm.is_new() || !frm.doc.custom_is_summer_flower || frm.is_dirty()) return;
		frappe.call({
			method: "upande_production.summer_flowers.crop_protocol.protocol_recompute_diff",
			args: { protocol: frm.doc.name },
		}).then((r) => {
			const d = r && r.message;
			if (!d || frm.is_dirty() || (!d.changes.length && !d.error)) return;
			const fmt = (v) => (v === null || v === undefined || v === "" ? "empty"
				: typeof v === "number" ? String(Math.round(v * 1000) / 1000) : frappe.utils.escape_html(String(v)));
			let html;
			if (d.error) {
				html = __("Out of date, and it cannot be recalculated: {0}", [frappe.utils.escape_html(d.error)]);
			} else {
				html = "<b>" + __("Out of date.") + "</b> " + __("A recalculation would change:") + "<ul style='margin:4px 0 0 16px'>" +
					d.changes.map((c) => `<li>${frappe.utils.escape_html(c.label)}: ${fmt(c.stored)} &rarr; ${fmt(c.computed)}</li>`).join("") + "</ul>";
			}
			frm.set_intro(html, "orange");
			if (!d.error && frm.perm && frm.perm[0] && frm.perm[0].write) {
				frm.add_custom_button(__("Recalculate"), () => {
					frappe.confirm(__("Recalculate the derived values? If it differs from the approved version the status goes back to Draft."), () => {
						frappe.call({
							method: "upande_production.summer_flowers.crop_protocol.recalculate",
							args: { protocol: frm.doc.name }, freeze: true,
						}).then(() => frm.reload_doc());
					});
				});
			}
		});
	},
});
