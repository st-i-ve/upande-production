/** ISO weeks, Monday start. Pure date arithmetic, no timezone surprises: all
 *  maths is done on UTC midnight of the calendar date. */

export interface IsoWeek {
  year: number;
  week: number;
}

function utc(y: number, m: number, d: number): Date {
  return new Date(Date.UTC(y, m, d));
}

export function isoWeekOf(date: Date): IsoWeek {
  const d = utc(date.getFullYear(), date.getMonth(), date.getDate());
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day); // the Thursday of this week
  const year = d.getUTCFullYear();
  const jan1 = utc(year, 0, 1);
  const week = Math.ceil(((d.getTime() - jan1.getTime()) / 86400000 + 1) / 7);
  return { year, week };
}

export function currentIsoWeek(): IsoWeek {
  return isoWeekOf(new Date());
}

/** 52 or 53. The 28th of December always falls in the year's last ISO week. */
export function weeksInYear(year: number): number {
  return isoWeekOf(new Date(year, 11, 28)).week;
}

export function shiftWeek({ year, week }: IsoWeek, delta: number): IsoWeek {
  let y = year;
  let w = week + delta;
  while (w < 1) {
    y -= 1;
    w += weeksInYear(y);
  }
  while (w > weeksInYear(y)) {
    w -= weeksInYear(y);
    y += 1;
  }
  return { year: y, week: w };
}

/** Monday of an ISO week, as a local Date. */
export function weekStart({ year, week }: IsoWeek): Date {
  const jan4 = utc(year, 0, 4);
  const monday = new Date(jan4.getTime() - ((jan4.getUTCDay() || 7) - 1) * 86400000);
  monday.setUTCDate(monday.getUTCDate() + (week - 1) * 7);
  return new Date(monday.getUTCFullYear(), monday.getUTCMonth(), monday.getUTCDate());
}
