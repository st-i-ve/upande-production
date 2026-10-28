// Desk -> /production_app crossing, mirroring upande_scp's scp_desk.js.
//
// Frappe hard-codes target="_blank" on URL-type workspace-sidebar items, so a
// sidebar link into the React app would open a new tab. Intercept clicks on
// /production_app links (capture phase, so this runs before Frappe's handler)
// and navigate in the current tab behind a white cover. The app shell raises
// the same cover (www/production_app.html), so the two loads read as one.
//
// The Production Navigation launcher lives in a Custom HTML Block, which
// Frappe renders inside an open shadow root; e.target is retargeted to the
// shadow host there, so walk e.composedPath() to find the real anchor.
(function () {
	var ID = "pr-desk-splash";

	function cover() {
		if (document.getElementById(ID)) return;
		var el = document.createElement("div");
		el.id = ID;
		el.setAttribute(
			"style",
			"position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;" +
				"justify-content:center;background:#ffffff"
		);
		var img = document.createElement("img");
		img.src = "/assets/upande_production/images/upande_mark.svg";
		img.alt = "Upande Production";
		img.setAttribute("style", "width:106px;height:auto;display:block");
		el.appendChild(img);
		document.body.appendChild(el);
	}

	// Paint the cover, then navigate on the next frame — assigning location.href
	// in the same tick means the browser never paints what was just appended.
	function leave(href) {
		try {
			cover();
		} catch (_) {}
		requestAnimationFrame(function () {
			setTimeout(function () {
				window.location.href = href;
			}, 60);
		});
	}

	document.addEventListener(
		"click",
		function (e) {
			if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
			var path = typeof e.composedPath === "function" ? e.composedPath() : [e.target];
			var a = null;
			for (var i = 0; i < path.length; i++) {
				var el = path[i];
				if (el && el.tagName === "A" && el.hasAttribute && el.hasAttribute("href")) {
					a = el;
					break;
				}
			}
			if (!a) return;
			var href = a.getAttribute("href") || "";
			if (href.indexOf("/production_app") === 0) {
				e.preventDefault();
				e.stopPropagation();
				leave(href);
			}
		},
		true
	);
})();
