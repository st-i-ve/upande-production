import {
  CalendarCheck,
  CalendarRange,
  ClipboardCheck,
  Coins,
  Droplets,
  Fish,
  FlaskConical,
  Hexagon,
  Home,
  Scissors,
  ScrollText,
  PackageCheck,
  Landmark,
  TrendingUp,
  Scale,
  Waves,
  Stethoscope,
  Utensils,
  LayoutDashboard,
  LayoutGrid,
  LineChart,
  Map as MapIcon,
  Repeat,
  ScanLine,
  SlidersHorizontal,
  Sunrise,
  Table2,
  Tractor,
  UserRoundCheck,
  Users,
  Route as RouteIcon,
} from "lucide-react";
import type { Crop } from "@/lib/api";
import { isFlowerCrop, viewLabel } from "@/lib/crops";
import type { View } from "@/lib/router";

type IconType = React.ComponentType<{ className?: string }>;

export interface NavItem {
  view: View;
  label: string;
  icon: IconType;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

const ICONS: Record<View, IconType> = {
  overview: LayoutDashboard,
  approvals: ClipboardCheck,
  plan: CalendarCheck,
  map: MapIcon,
  "casual-labourers": Users,
  blocks: LayoutGrid,
  cycles: Repeat,
  costs: Coins,
  establishment: Landmark,
  "break-even": TrendingUp,
  forecast: LineChart,
  outlook: Sunrise,
  "block-forecast": Table2,
  "harvest-calendar": CalendarRange,
  "picking-plan": UserRoundCheck,
  "dry-matter": Droplets,
  "dry-matter-monitoring": Droplets,
  "dry-matter-tests": Droplets,
  settings: SlidersHorizontal,
  "hive-inspections": Stethoscope,
  "honey-harvest": Hexagon,
  "pond-batches": Fish,
  "water-quality": FlaskConical,
  feeding: Utensils,
  irrigation: Waves,
  grading: Scale,
  "flower-overview": LayoutDashboard,
  greenhouses: Home,
  "flower-cycles": Repeat,
  protocols: ScrollText,
  "cut-stages": Scissors,
  "plan-form": CalendarCheck,
  harvesting: PackageCheck,
  "farm-map": MapIcon,
  "planting-calendars": CalendarRange,
  "protocol-versions": ScrollText,
  machines: Tractor,
  allocations: RouteIcon,
  scan: ScanLine,
};

/** Machines are farm-wide: every crop's sidebar has them, flower crops included. */
export const MACHINE_VIEWS: View[] = ["machines", "allocations", "scan"];

/** The screens a flower crop has (and only those): the Crop Production ones, ported. */
export const FLOWER_VIEWS: View[] = [
  "flower-overview", "greenhouses", "flower-cycles", "protocols", "cut-stages", "plan-form", "harvesting", "farm-map",
  "planting-calendars", "protocol-versions",
];

/** The view a crop opens on. */
export function landingView(crop?: Parameters<typeof isFlowerCrop>[0]): View {
  return isFlowerCrop(crop) ? "flower-overview" : "overview";
}

/** Views only some crops have, keyed by view. Everything else is every crop's. */
const ONLY_FOR: Partial<Record<View, string[]>> = {
  outlook: ["avocado"],
  "block-forecast": ["avocado"],
  "harvest-calendar": ["avocado"],
  "picking-plan": ["avocado"],
  "dry-matter": ["avocado"],
  "dry-matter-monitoring": ["avocado"],
  "hive-inspections": ["apiary"],
  "honey-harvest": ["apiary"],
  "pond-batches": ["aquaculture"],
  "water-quality": ["aquaculture"],
  "feeding": ["aquaculture"],
  "irrigation": ["fruits-vegetables"],
  "grading": ["fruits-vegetables"],
};

/** Views some crops do not have: bees and fish run in colonies and batches, not crop cycles. */
const NOT_FOR: Partial<Record<View, string[]>> = {
  cycles: ["apiary", "aquaculture"],
};

const GROUPS: { label: string; views: View[] }[] = [
  { label: "Overview", views: ["overview", "approvals"] },
  { label: "Field work", views: ["plan", "map", "casual-labourers"] },
  {
    label: "Field logs",
    views: ["hive-inspections", "honey-harvest", "pond-batches", "water-quality", "feeding", "irrigation", "grading"],
  },
  { label: "Blocks", views: ["blocks", "cycles", "costs", "establishment", "break-even"] },
  {
    label: "Forecast",
    views: ["forecast", "outlook", "block-forecast", "harvest-calendar", "picking-plan", "dry-matter", "dry-matter-monitoring", "dry-matter-tests"],
  },
  { label: "Machines", views: MACHINE_VIEWS },
  { label: "Setup", views: ["settings"] },
];

const FLOWER_GROUPS: { label: string; views: View[] }[] = [
  { label: "Overview", views: ["flower-overview"] },
  { label: "Crop setup", views: ["protocols", "protocol-versions", "cut-stages"] },
  { label: "Planting and beds", views: ["greenhouses", "flower-cycles", "farm-map"] },
  { label: "Planning and harvest", views: ["planting-calendars", "plan-form", "harvesting"] },
  { label: "Machines", views: MACHINE_VIEWS },
];

export function viewAllowed(
  view: View,
  cropKey: string,
  crop?: (Pick<Crop, "dry_matter_testing"> & Partial<Pick<Crop, "desk_launcher" | "unit_label" | "parent_unit_label" | "sub_unit_label">>) | null,
): boolean {
  // Flower crops have their own screens and none of the others; nobody else has theirs.
  if (MACHINE_VIEWS.includes(view)) return true;
  const flower = isFlowerCrop(crop as Parameters<typeof isFlowerCrop>[0]);
  if (FLOWER_VIEWS.includes(view)) return flower;
  if (flower) return false;
  // Dry matter tests follow the crop's setting; avocado keeps its own Dry Matter page.
  if (view === "dry-matter-tests") return cropKey !== "avocado" && !!Number(crop?.dry_matter_testing);
  const only = ONLY_FOR[view];
  if (only && !only.includes(cropKey)) return false;
  return !(NOT_FOR[view] ?? []).includes(cropKey);
}

/** The sidebar for one crop: the app is scoped to a single crop at a time. */
export function navForCrop(crop: Crop): NavGroup[] {
  return (isFlowerCrop(crop) ? FLOWER_GROUPS : GROUPS).map((g) => ({
    label: g.label,
    items: g.views
      .filter((v) => viewAllowed(v, crop.crop_key, crop))
      .map((v) => ({ view: v, label: viewLabel(v, crop), icon: ICONS[v] })),
  })).filter((g) => g.items.length > 0);
}
