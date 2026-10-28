// The Production mark: the Upande disc and arrow at rest, and on hover the arrow
// steps aside and Production's harvest scene plays (an avocado branch, the fruit
// ripen, are ringed, picked and drop into the picking crate). It loops while the
// pointer or keyboard focus stays and eases back out on leave.
//
// The artwork and the keyframes come from production_logo.svg (written by
// scripts/build_production_logo.py, which also copies it to src/assets): the
// same file the desk tile uses, inlined so the Web Animations API can reach it.
// Hover is taken from the nearest enclosing <a>/<button> when there is one (the
// sidebar's brand link), otherwise from the mark itself.
import { useEffect, useMemo, useRef } from "react";
import markSvg from "@/assets/production_logo.svg?raw";

type Frame = Record<string, string | number>;
interface Track {
  sel: string;
  box: string | null;
  origin: string | null;
  frames: Frame[];
}
interface Spec {
  enterMs: number;
  loopMs: number;
  ease: string;
  enter: Track[];
  loop: Track[];
}

function parseSpec(): { html: string; spec: Spec | null } {
  const m = /<metadata id="production-motion">([\s\S]*?)<\/metadata>/.exec(markSvg);
  let spec: Spec | null = null;
  try {
    spec = m ? (JSON.parse(m[1]) as Spec) : null;
  } catch {
    spec = null;
  }
  // Fill the host box instead of the file's 689px size.
  const html = markSvg
    .replace(/ width="689" height="689"/, ' width="100%" height="100%"')
    .replace(/<metadata[\s\S]*?<\/metadata>/, "");
  return { html, spec };
}

const PARSED = parseSpec();

function build(svg: SVGElement, tracks: Track[], timing: KeyframeAnimationOptions) {
  const out: Animation[] = [];
  for (const t of tracks) {
    svg.querySelectorAll<SVGElement>(t.sel).forEach((el) => {
      if (t.origin) {
        el.style.transformBox = t.box || "view-box";
        el.style.transformOrigin = t.origin;
      }
      const a = el.animate(t.frames as unknown as Keyframe[], timing);
      a.pause();
      a.currentTime = 0;
      out.push(a);
    });
  }
  return out;
}

export function ProductionMark({
  size = 48,
  className,
  title = "Upande Production",
}: {
  size?: number;
  className?: string;
  title?: string;
}) {
  const host = useRef<HTMLSpanElement>(null);
  const html = useMemo(() => PARSED.html, []);

  useEffect(() => {
    const el = host.current;
    const spec = PARSED.spec;
    const svg = el?.querySelector("svg");
    if (!el || !svg || !spec || typeof svg.animate !== "function") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    const enter = build(svg, spec.enter, { duration: spec.enterMs, easing: spec.ease, fill: "both" });
    const loop = build(svg, spec.loop, {
      duration: spec.loopMs,
      easing: "ease-in-out",
      iterations: Infinity,
      fill: "both",
    });
    let hovered = false;
    const at = () => (enter.length ? Number(enter[0].currentTime) || 0 : 0);

    const run = (forward: boolean) => {
      enter.forEach((a) => {
        const t = Number(a.currentTime) || 0;
        if (forward ? t >= spec.enterMs : t <= 0) {
          a.pause();
          return;
        }
        a.playbackRate = forward ? 1 : -1;
        a.play();
      });
    };
    enter[0]?.addEventListener("finish", () => {
      if (hovered && at() >= spec.enterMs) loop.forEach((l) => l.play());
    });

    const on = () => {
      hovered = true;
      if (at() <= 0) {
        loop.forEach((l) => {
          l.pause();
          l.currentTime = 0;
        });
      }
      run(true);
    };
    const off = () => {
      hovered = false;
      loop.forEach((l) => l.pause());
      run(false);
    };

    const target = (el.closest("a, button") as HTMLElement | null) ?? el;
    target.addEventListener("mouseenter", on);
    target.addEventListener("mouseleave", off);
    target.addEventListener("focusin", on);
    target.addEventListener("focusout", off);
    return () => {
      target.removeEventListener("mouseenter", on);
      target.removeEventListener("mouseleave", off);
      target.removeEventListener("focusin", on);
      target.removeEventListener("focusout", off);
      [...enter, ...loop].forEach((a) => a.cancel());
    };
  }, []);

  return (
    <span
      ref={host}
      role="img"
      aria-label={title}
      className={className}
      style={{ display: "inline-block", width: size, height: size, lineHeight: 0, flexShrink: 0 }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export default ProductionMark;
