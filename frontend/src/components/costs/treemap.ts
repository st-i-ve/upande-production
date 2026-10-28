export interface TreeItem<T> {
  value: number;
  data: T;
}
export interface Tile<T> {
  x: number;
  y: number;
  w: number;
  h: number;
  item: TreeItem<T>;
}

/** Squarified treemap (Bruls et al.): tiles fill the box, area proportional to value. */
export function squarify<T>(items: TreeItem<T>[], x: number, y: number, w: number, h: number): Tile<T>[] {
  const list = items.filter((i) => i.value > 0).sort((a, b) => b.value - a.value);
  const total = list.reduce((t, i) => t + i.value, 0);
  const out: Tile<T>[] = [];
  if (!list.length || w <= 0 || h <= 0 || total <= 0) return out;
  const scale = (w * h) / total;
  let rest = list.map((i) => ({ item: i, area: i.value * scale }));
  let rx = x, ry = y, rw = w, rh = h;

  const worst = (row: { area: number }[], side: number) => {
    const s = row.reduce((t, r) => t + r.area, 0);
    const mx = Math.max(...row.map((r) => r.area));
    const mn = Math.min(...row.map((r) => r.area));
    return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
  };

  while (rest.length) {
    const side = Math.min(rw, rh);
    let row = [rest[0]];
    let i = 1;
    while (i < rest.length && worst([...row, rest[i]], side) <= worst(row, side)) {
      row.push(rest[i]);
      i++;
    }
    rest = rest.slice(row.length);
    const s = row.reduce((t, r) => t + r.area, 0);
    if (rw >= rh) {
      const cw = s / rh;
      let cy = ry;
      row.forEach((r) => {
        const ch = r.area / cw;
        out.push({ x: rx, y: cy, w: cw, h: ch, item: r.item });
        cy += ch;
      });
      rx += cw;
      rw -= cw;
    } else {
      const ch = s / rw;
      let cx = rx;
      row.forEach((r) => {
        const cw = r.area / ch;
        out.push({ x: cx, y: ry, w: cw, h: ch, item: r.item });
        cx += cw;
      });
      ry += ch;
      rh -= ch;
    }
  }
  return out;
}
