// Production Crop desk form: keep the count size bands contiguous while they are edited.
// Changing a band's min moves the next-higher count's max to it; changing a max moves the next-lower
// count's min. Gaps and overlaps show as an orange banner; saving is never blocked.
// (Same rules as production/logic/count_sizes.py and the React settings editor.)
(function () {
	var num = function (v) { var n = parseFloat(v); return isNaN(n) ? 0 : n; };
	var g = function (v) { return Math.round(num(v) * 100) / 100; };

	function bands(frm) {
		return (frm.doc.count_sizes || []).filter(function (r) { return parseInt(r.count, 10); })
			.sort(function (a, b) { return a.count - b.count; });
	}

	function issues(frm) {
		var out = [], b = bands(frm);
		b.forEach(function (r, i) {
			if (i && b[i - 1].count === r.count) out.push("Count " + r.count + " appears more than once");
			if (num(r.min_g) >= num(r.max_g)) out.push("Count " + r.count + ": min " + g(r.min_g) + " g is not below max " + g(r.max_g) + " g");
		});
		for (var i = 1; i < b.length; i++) {
			var a = b[i - 1], c = b[i];
			if (a.count === c.count || num(a.min_g) >= num(a.max_g) || num(c.min_g) >= num(c.max_g)) continue;
			if (num(c.min_g) >= num(a.min_g)) out.push("Count " + c.count + " is not lighter than count " + a.count + " (a higher count is smaller fruit)");
			else if (num(c.max_g) < num(a.min_g)) out.push("Fruit between " + g(c.max_g) + " g and " + g(a.min_g) + " g has no count size");
			else if (num(c.max_g) > num(a.min_g)) out.push("Counts " + a.count + " and " + c.count + " both cover " + g(a.min_g) + "–" + g(c.max_g) + " g");
		}
		return out;
	}

	function banner(frm) {
		frm.dashboard.clear_headline();
		var list = issues(frm);
		if (!list.length) return;
		frm.dashboard.set_headline_alert(
			"<b>" + __("Count size bands") + "</b><ul style='margin:4px 0 0 16px'>" +
			list.map(function (m) { return "<li>" + frappe.utils.escape_html(m) + "</li>"; }).join("") + "</ul>",
			"orange"
		);
	}

	function link(frm, cdt, cdn, edited, other, which) {
		var row = locals[cdt][cdn];
		if (!parseInt(row.count, 10) || frm.__linking) return;
		var b = bands(frm).filter(function (r) { return r.name !== row.name; });
		var n = which === "min_g"
			? b.filter(function (r) { return r.count > row.count; }).sort(function (x, y) { return x.count - y.count; })[0]
			: b.filter(function (r) { return r.count < row.count; }).sort(function (x, y) { return y.count - x.count; })[0];
		if (n && num(n[other]) !== num(row[edited])) {
			frm.__linking = true;
			frappe.model.set_value(n.doctype, n.name, other, num(row[edited])).then(function () {
				frm.__linking = false;
				frappe.show_alert({ message: __("Count {0} {1} moved to {2} g", [n.count, other === "max_g" ? "max" : "min", g(row[edited])]), indicator: "blue" });
				banner(frm);
			});
		}
		banner(frm);
	}

	frappe.ui.form.on("Production Crop", {
		refresh: banner,
		validate: banner,
		count_sizes_remove: banner,
	});
	frappe.ui.form.on("Production Crop Count Size", {
		min_g: function (frm, cdt, cdn) { link(frm, cdt, cdn, "min_g", "max_g", "min_g"); },
		max_g: function (frm, cdt, cdn) { link(frm, cdt, cdn, "max_g", "min_g", "max_g"); },
		count: function (frm) { banner(frm); },
	});
})();
