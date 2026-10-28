# Map components

One map format (ported from SCP kaitet): full-width MapLibre map, floating panels docked
bottom-right, KPI pill on top, small (i) credit bottom-left. Import from `@/components/map`.

The container that holds the map must be `relative` with a height; everything below is placed
inside it, as siblings of `MapBase` (which fills its parent).

```tsx
<div className="relative h-[calc(100vh-14rem)]">
  <MapBase initialBounds={data?.bounds ?? undefined} onReady={(map) => { mapRef.current = map; setReady(true); }} />
  <MapKpiPill>{data.totals.blocks} blocks · {formatQty(data.totals.remaining)} left</MapKpiPill>
  <MapPanelDock>
    <MapControlPanel title="Status" count={data.totals.blocks}>…legend rows…</MapControlPanel>
    <MapControlPanel title="Work remaining">…per block list…</MapControlPanel>
    {selected && <MapFloatingCard eyebrow={selected.parent} title={selected.name} onClose={() => setSel(null)}>…</MapFloatingCard>}
  </MapPanelDock>
</div>
```

## Components

- `MapBase` props: `onReady(map)` (required; fires after the style loads, so add layers there),
  `initialCenter` `[lng, lat]` (default Mutara `[36.75, 0.06]`), `initialZoom` (14),
  `initialBounds` `[[minLng,minLat],[maxLng,maxLat]]` (wins over centre/zoom), `basemap`
  `"satellite" | "street"` (default satellite), `className`. Has zoom buttons (top-right), a
  satellite/street toggle under them (flips layer visibility, so your layers survive) and the
  ⓘ credit. Fit later with `map.fitBounds(data.bounds, { padding: 48 })`.
- `MapPanelDock` props: `children`, `className`, `testId`. Bottom-right column, bottom sheet on
  phones. Panels inside it flow rather than float. List/legend panels first, detail card last.
- `MapControlPanel` props: `title`, `count?`, `children`, `defaultOpen` (true), `className`,
  `bodyClassName` (scroll box, default max 30vh), `testId`. Collapsible; legend, filters, lists.
- `MapFloatingCard` props: `title`, `eyebrow?`, `onClose` (button and Esc), `children`, `label?`,
  `closeLabel?`, `className`, `testId`. The detail card for a clicked unit.
- `MapKpiPill` props: `children`, `className`. Top-centre totals; not clickable.
- `useEscapeClose(onClose, active?)`, `useInMapPanelDock()` for custom panels.

## Coverage layers (`coverage-layer.ts`)

- `setCoverageData(map, data, selectedName?)`: adds (first call) or updates the sources/layers
  for a `CoverageMap`: pivot outlines, unit fills coloured by `state`, white borders, selection ring.
  Call it from `onReady` and again whenever data changes.
- `setCoverageSelected(map, name | null)`: moves the selection ring.
- `COVERAGE_FILL_LAYER`: layer id for events:
  `map.on("click", COVERAGE_FILL_LAYER, (e) => setSel(e.features?.[0]?.properties?.name))`,
  plus `mouseenter`/`mouseleave` for the pointer cursor. Feature properties: `name`, `state`,
  `color`, `progress`.

## Data (`@/lib/map-api`)

`coverageMap({ crop, year, week, farm?, operation?, status? })` returns `Envelope<CoverageMap>`
(check `isError`). Also exports `COVERAGE_STATE_COLOR`, `COVERAGE_STATE_LABEL`, `COVERAGE_STATES`
(legend order) and `formatQty(qtyByUom)` ("120 Bed · 6 Hectare").

Key fields: `units[]` (leaf blocks/slices/ponds: `name`, `parent`, `state`, `progress_pct`,
`remaining_qty` by UOM, `tasks[]`, `item`), `outlines[]` (pivot circles), `totals`
(`blocks`, qty by UOM for `planned|done|remaining|pending`, `late` blocks, `by_state` counts),
`operations[]` for the operation filter, `center`, `bounds` (null when nothing has geometry:
show an empty state). Quantities are never summed across UOMs. Pending quantity is not counted
as done; `pending_qty` is null on tasks until the approvals change lands.
