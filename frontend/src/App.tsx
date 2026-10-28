import { lazy, Suspense, useEffect } from "react";
import { AppSidebar } from "@/components/AppSidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/Toast";
import { PageSkeleton } from "@/components/Loading";
import { Page } from "@/components/PageShell";
import { Button } from "@/components/ui/button";
import { CropProvider, useCrops } from "@/lib/crops";
import { viewAllowed } from "@/lib/nav";
import { replaceRoute, useRoute, type View } from "@/lib/router";

/**
 * Every chunk's loader, kept so they can be warmed after first paint.
 *
 * SWITCHING PAGES SHOULD BE WAITING FOR DATA, NOT FOR CODE. Lazy routes mean
 * first paint never pulls the whole app down a rural line — which is right —
 * but it also meant every first visit to a screen stopped on a bare "Loading…"
 * while its JavaScript arrived, and only THEN started asking for the farm's
 * figures. Two waits, one of them invisible to the skeletons built for the
 * other.
 *
 * So the chunks are fetched quietly once the first page is up and the browser
 * is idle. By the time anybody clicks, the code is in cache and the only thing
 * left to wait for is the data — which is what the skeletons are for.
 */
const CHUNKS: Array<() => Promise<unknown>> = [];

function page<T extends React.ComponentType<Record<string, never>>>(
  load: () => Promise<{ default: T }>,
) {
  CHUNKS.push(load);
  return lazy(load);
}

/** Pull every route's code in the background, gently and only once. */
function warmChunks() {
  let warmed = false;
  return () => {
    if (warmed) return;
    warmed = true;
    const idle =
      (window as unknown as { requestIdleCallback?: (fn: () => void) => void })
        .requestIdleCallback || ((fn: () => void) => window.setTimeout(fn, 400));
    idle(() => {
      // One at a time: a rural connection asked for twenty chunks at once
      // serves the one the operator is waiting for last.
      void CHUNKS.reduce(
        (queue, load) => queue.then(() => load().then(() => undefined, () => undefined)),
        Promise.resolve(),
      );
    });
  };
}

const warm = warmChunks();

// Each built page is loaded lazily, so first paint never pulls the whole app
// and the next slices can add pages without growing it.
const Overview = page(() => import("@/pages/Overview").then((m) => ({ default: m.Overview })));
const Blocks = page(() => import("@/pages/Blocks").then((m) => ({ default: m.Blocks })));
const Cycles = page(() => import("@/pages/Cycles").then((m) => ({ default: m.Cycles })));
const Plan = page(() => import("@/pages/Plan").then((m) => ({ default: m.Plan })));
const ValueAdders = page(() =>
  import("@/pages/ValueAdders").then((m) => ({ default: m.ValueAdders })),
);
const Costs = page(() => import("@/pages/Costs").then((m) => ({ default: m.Costs })));
const Forecast = page(() => import("@/pages/Forecast").then((m) => ({ default: m.Forecast })));
const Settings = page(() => import("@/pages/Settings").then((m) => ({ default: m.Settings })));
const Approvals = page(() => import("@/pages/Approvals").then((m) => ({ default: m.Approvals })));
const CoverageMap = page(() =>
  import("@/pages/CoverageMap").then((m) => ({ default: m.CoverageMap })),
);
const Outlook = page(() => import("@/pages/avocado/Outlook").then((m) => ({ default: m.Outlook })));
const BlockForecast = page(() =>
  import("@/pages/avocado/BlockForecast").then((m) => ({ default: m.BlockForecast })),
);
const HarvestCalendar = page(() =>
  import("@/pages/avocado/HarvestCalendar").then((m) => ({ default: m.HarvestCalendar })),
);
const PickingPlan = page(() =>
  import("@/pages/avocado/PickingPlan").then((m) => ({ default: m.PickingPlan })),
);
const DryMatter = page(() =>
  import("@/pages/avocado/DryMatter").then((m) => ({ default: m.DryMatter })),
);

const PAGES: Record<View, React.ComponentType> = {
  overview: Overview,
  blocks: Blocks,
  cycles: Cycles,
  plan: Plan,
  "value-adders": ValueAdders,
  costs: Costs,
  forecast: Forecast,
  settings: Settings,
  approvals: Approvals,
  map: CoverageMap,
  outlook: Outlook,
  "block-forecast": BlockForecast,
  "harvest-calendar": HarvestCalendar,
  "picking-plan": PickingPlan,
  "dry-matter": DryMatter,
};

/** Says why the workspace is empty, and what to do, in place of a blank page. */
function Notice({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <Page>
      <div className="flex max-w-xl flex-col items-start gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] px-5 py-5 shadow-[var(--sd-shadow-1)]">
        <h1 className="text-[18px] font-semibold text-[var(--sd-ink)]">{title}</h1>
        {children}
      </div>
    </Page>
  );
}

export function App() {
  const state = useCrops();
  const [route, navigate] = useRoute();
  const boot = state.status === "ready" ? state.boot : null;
  const crop = boot?.crops.find((c) => c.crop_key === route.crop) ?? null;

  useEffect(warm, []);

  // No crop (or an unknown one) in the hash: land on the first crop's overview.
  useEffect(() => {
    if (boot && !crop && boot.crops.length) replaceRoute(boot.crops[0].crop_key, route.view);
  }, [boot, crop, route.view]);

  useEffect(() => {
    if (crop && !viewAllowed(route.view, crop.crop_key)) replaceRoute(crop.crop_key, "overview");
  }, [crop, route.view]);

  const Built = PAGES[route.view];

  let main: React.ReactNode;
  if (state.status === "loading" || (boot && !crop && boot.crops.length)) {
    main = <PageSkeleton />;
  } else if (state.status === "error") {
    main = (
      <Notice title="Could not load Production">
        <p className="text-[13px] text-[var(--sd-muted)]">{state.error}</p>
        <Button onClick={state.reload}>Try again</Button>
      </Notice>
    );
  } else if (boot && !boot.crops.length) {
    main = (
      <Notice title="No crops yet">
        <p className="text-[13px] text-[var(--sd-muted)]">
          Add a Production Crop in the desk and it will appear here.
        </p>
      </Notice>
    );
  } else if (boot && crop) {
    main = (
      <CropProvider crop={crop} boot={boot}>
        <Suspense fallback={<PageSkeleton />}>
          <Built key={`${crop.crop_key}/${route.view}`} />
        </Suspense>
      </CropProvider>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <ToastProvider>
        <SidebarProvider>
          <AppSidebar
            crop={crop}
            view={route.view}
            onNavigate={navigate}
          />
          {/* min-w-0 so a wide table inside the workspace scrolls in its own box
              instead of refusing to shrink and pushing the page sideways. */}
          <SidebarInset className="min-w-0">{main}</SidebarInset>
        </SidebarProvider>
      </ToastProvider>
    </TooltipProvider>
  );
}
