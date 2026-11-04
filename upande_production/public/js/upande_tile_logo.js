// Replays an app tile's logo on hover/focus, for the Upande apps whose mark is a pure-CSS play-once SVG.
//
// The desk draws app tiles as <img class="app-icon"> inside <a class="desktop-icon">. The SVG animates
// itself once when it loads and comes to rest as the plain Upande mark (see
// scripts/build_production_logo.py: production_logo.svg). An <img> cannot be replayed, so on
// mouseenter/focusin the SVG text (fetched once) is handed to the same <img> as a fresh Blob URL, which
// restarts the CSS. The <img> is never swapped for inline SVG, so the tile keeps its size and its HD
// rendering. Old blob URLs are revoked. With reduced motion nothing is touched.
//
// One script serves upande_production, upande_crop_material_planning and upande_propagation (the other
// two require production): any tile whose src is /assets/<app>/.../*_logo.svg.
(function () {
	var TILE = /^\/assets\/(upande_production|upande_crop_material_planning|upande_propagation)\/.*_logo\.svg(\?.*)?$/;

	if (window.__upandeTileLogo) return;
	window.__upandeTileLogo = true;
	if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
	if (!window.fetch || !window.URL || !URL.createObjectURL || !window.Blob) return;

	var cache = {}; // src -> Promise<text>

	function load(src) {
		if (!cache[src]) {
			cache[src] = fetch(src, { credentials: "same-origin" }).then(function (r) {
				if (!r.ok) throw new Error(r.status);
				return r.text();
			});
			cache[src].catch(function () {
				delete cache[src];
			});
		}
		return cache[src];
	}

	function path(src) {
		try {
			return new URL(src, window.location.href).pathname;
		} catch (_) {
			return "";
		}
	}

	function replay(img) {
		var src = img.getAttribute("data-logo-src");
		if (!src) return;
		load(src)
			.then(function (text) {
				if (!img.isConnected) return;
				var old = img.getAttribute("data-logo-play");
				var url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml" }));
				img.setAttribute("data-logo-play", url);
				img.src = url;
				if (old) URL.revokeObjectURL(old);
			})
			.catch(function () {
				// keep the resting mark
			});
	}

	function wire(img) {
		if (img.getAttribute("data-logo-src")) return;
		var src = img.getAttribute("src") || "";
		var p = path(src);
		if (!TILE.test(p)) return;
		img.setAttribute("data-logo-src", p);
		img.setAttribute("data-logo-animated", "1");
		var tile = img.closest(".desktop-icon") || img.parentElement;
		var on = function () {
			replay(img);
		};
		tile.addEventListener("mouseenter", on);
		tile.addEventListener("focusin", on);
		load(p).catch(function () {});
	}

	function scan() {
		var imgs = document.querySelectorAll(".desktop-icon img.app-icon");
		for (var i = 0; i < imgs.length; i++) wire(imgs[i]);
	}

	var queued = false;
	function onMutate() {
		if (queued) return;
		queued = true;
		requestAnimationFrame(function () {
			queued = false;
			scan();
		});
	}
	function start() {
		scan();
		new MutationObserver(onMutate).observe(document.body, { childList: true, subtree: true });
	}
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
	else start();
})();
