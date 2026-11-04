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

	// Leaving for a crop's page shows that crop's scene; otherwise productivity.
	function cover(href) {
		if (document.getElementById(ID)) return;
		var el = document.createElement("div");
		el.id = ID;
		el.setAttribute(
			"style",
			"position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;" +
				"justify-content:center;background:#ffffff"
		);
		var img = document.createElement("img");
		var base = "/assets/upande_production/images/production_logo_loader.svg";
		var k = ((href || "").match(/#\/([a-z0-9-]+)/) || [])[1];
		img.onerror = function () { img.onerror = null; img.src = base; };
		img.src = k ? "/assets/upande_production/images/production_logo_" + k + "_loader.svg" : base;
		img.alt = "Upande Production";
		img.setAttribute("style", "width:106px;height:auto;display:block");
		el.appendChild(img);
		document.body.appendChild(el);
	}

	// Paint the cover, then navigate on the next frame — assigning location.href
	// in the same tick means the browser never paints what was just appended.
	function leave(href) {
		try {
			cover(href);
		} catch (_) {}
		requestAnimationFrame(function () {
			setTimeout(function () {
				window.location.href = href;
			}, 60);
		});
	}

	// Same tab. Frappe turns every External desktop icon (the Production, Crop Material
	// Planning and Propagation tiles on the apps screen) into window.location.origin + link
	// and sets target="_blank" on it, so each module opens in a new tab. Take any same-origin
	// link of that kind back into the current tab: /app and /desk paths go through
	// frappe.set_route (SPA, no reload, as Frappe's own handler does); anything else is a
	// page load behind the cover. Other origins, downloads, file/API URLs and modified or
	// middle clicks are left alone.
	var FILE_PATHS = /^\/(files|private|api|assets|backups)(\/|$)/;

	function sameTabTarget(a) {
		var raw = a.getAttribute("href") || "";
		if (!raw || raw.charAt(0) === "#" || a.hasAttribute("download")) return null;
		var url;
		try {
			url = new URL(raw, window.location.href);
		} catch (_) {
			return null;
		}
		if (url.origin !== window.location.origin) return null;
		if (FILE_PATHS.test(url.pathname)) return null;
		// a relative link without a target already navigates in this tab (Frappe's handler
		// routes /app links itself); only act on a new-tab target or an absolute URL
		var absolute = /^[a-z][a-z0-9+.-]*:|^\/\//i.test(raw);
		if (!absolute && a.getAttribute("target") !== "_blank") return null;
		return url;
	}

	function go(url) {
		var path = url.pathname;
		var spa = /^\/(app|desk)(\/|$)/.test(path);
		if (spa && window.frappe && frappe.set_route) {
			if (url.search) {
				frappe.route_options = {};
				new URLSearchParams(url.search).forEach(function (v, k) {
					frappe.route_options[k] = v;
				});
			}
			if (url.hash) frappe.route_hash = url.hash;
			frappe.set_route(path);
			return;
		}
		var target = path + url.search + url.hash;
		if (path.indexOf("/production_app") === 0) leave(target);
		else window.location.href = target;
	}

	document.addEventListener(
		"click",
		function (e) {
			if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
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
				return;
			}
			var url = sameTabTarget(a);
			if (!url) return;
			e.preventDefault();
			e.stopPropagation();
			go(url);
		},
		true
	);
})();
