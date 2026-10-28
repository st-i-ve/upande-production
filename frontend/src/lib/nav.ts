import {
  CalendarCheck,
  CalendarRange,
  ClipboardCheck,
  Coins,
  Droplets,
  Fish,
  FlaskConical,
  Hexagon,
  Scale,
  Waves,
  Stethoscope,
  Utensils,
  LayoutDashboard,
  LayoutGrid,
  LineChart,
  Map as MapIcon,
  Repeat,
  SlidersHorizontal,
  Sunrise,
  Table2,
  UserRoundCheck,
  Users,
} from "lucide-react";
import type { Crop } from "@/lib/api";
import { viewLabel } from "@/lib/crops";
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
  "value-adders": Users,
  blocks: LayoutGrid,
  cycles: Repeat,
  costs: Coins,
  forecast: LineChart,
  outlook: Sunrise,
  "block-forecast": Table2,
  "harvest-calendar": CalendarRange,
  "picking-plan": UserRoundCheck,
  "dry-matter": Droplets,
  settings: SlidersHorizontal,
  "hive-inspections": Stethoscope,
  "honey-harvest": Hexagon,
  "pond-batches": Fish,
  "water-quality": FlaskConical,
  feeding: Utensils,
  irrigation: Waves,
  grading: Scale,
};

/** Views only some crops have, keyed by view. Everything else is every crop's. */
const ONLY_FOR: Partial<Record<View, string[]>> = {
  outlook: ["avocado"],
  "block-forecast": ["avocado"],
  "harvest-calendar": ["avocado"],
  "picking-plan": ["avocado"],
  "dry-matter": ["avocado"],
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
  { label: "Field work", views: ["plan", "map", "value-adders"] },
  {
    label: "Field logs",
    views: ["hive-inspections", "honey-harvest", "pond-batches", "water-quality", "feeding", "irrigation", "grading"],
  },
  { label: "Blocks", views: ["blocks", "cycles", "costs"] },
  {
    label: "Forecast",
    views: ["forecast", "outlook", "block-forecast", "harvest-calendar", "picking-plan", "dry-matter"],
  },
  { label: "Setup", views: ["settings"] },
];

export function viewAllowed(view: View, cropKey: string): boolean {
  const only = ONLY_FOR[view];
  if (only && !only.includes(cropKey)) return false;
  return !(NOT_FOR[view] ?? []).includes(cropKey);
}

/** The sidebar for one crop: the app is scoped to a single crop at a time. */
export function navForCrop(crop: Crop): NavGroup[] {
  return GROUPS.map((g) => ({
    label: g.label,
    items: g.views
      .filter((v) => viewAllowed(v, crop.crop_key))
      .map((v) => ({ view: v, label: viewLabel(v, crop), icon: ICONS[v] })),
  })).filter((g) => g.items.length > 0);
}
