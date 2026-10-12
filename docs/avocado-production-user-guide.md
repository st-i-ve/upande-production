# Avocado Production — User Guide

A plain-language guide to the whole Avocado Production module: every page,
where the numbers come from, and where to type in your own.

No technical knowledge needed — this is written for farm and estate staff,
not IT.

---

## Table of contents

1. [What this module is for](#1-what-this-module-is-for)
2. [Where the numbers come from](#2-where-the-numbers-come-from)
3. [Season Outlook — the big picture](#3-season-outlook--the-big-picture)
4. [Production Forecast — Automatic vs Manual, and Budget](#4-production-forecast--automatic-vs-manual-and-budget)
5. [Dry Matter Test — is it ready to pick?](#5-dry-matter-test--is-it-ready-to-pick)
6. [Harvest Calendar — when each block gets picked](#6-harvest-calendar--when-each-block-gets-picked)
7. [Picking Plan — how many pickers, and what it costs](#7-picking-plan--how-many-pickers-and-what-it-costs)
8. [The Avocado Trail phone app](#8-the-avocado-trail-phone-app)
9. [Who can do what](#9-who-can-do-what)
10. [Quick answers](#10-quick-answers)

---

## 1. What this module is for

The avocado orchard has 80+ blocks of trees — different ages, different
varieties, spread across more than one farm — picked twice a year (an
"Early" crop and a "Late" crop). This module answers, for every block and
for the whole estate:

- **How much fruit is coming, and when?**
- **Is it legally ready to pick yet?** (avocados have a minimum ripeness —
  "dry matter" — below which they cannot be exported)
- **How many pickers does that need, and what will it cost?**
- **How does what we expected compare with what actually got delivered?**

It's reached from the **Upande · Avocado** menu on the left of the screen,
which has five pages:

| Page | Web address | What it's for |
|---|---|---|
| Season Outlook | `/avocado-outlook` | The one-screen summary of the whole estate |
| Forecast & Blocks | `/avocado-production` | The detailed forecast, block by block, with the Automatic/Manual toggle and Budget |
| Dry Matter Test | `/avocado-maturity` | Where ripeness readings are typed in |
| Harvest Calendar | `/avocado-calendar` | Which block gets picked which week |
| Picking Plan | `/avocado-labour` | How many pickers are needed, and the wage bill |

## 2. Where the numbers come from

Every figure on every page above traces back to something typed into one
of the records below. This is the map of where to go to change what the
system knows.

| Record (find it on the desk, under its own name) | What it holds | Who can add or edit it | What it changes |
|---|---|---|---|
| **Avocado Yield Block** | The block master: farm, variety, area, trees planted/live/bearing/sick, planting year | Agriculture Manager | Everything. Bearing trees size every forecast — a block with no bearing trees forecasts nothing, however big it is on paper |
| **Avocado Fruit Count** | A real count of fruit on a sample of trees in one block — walk it, count it, save it | Agriculture User and above (desk, or the phone app) | Overrides the age-based estimate for that block with a real, current count — the strongest evidence the system has for that block |
| **Avocado Maturity Test** | Dry matter (ripeness) readings, one row per visit | Agriculture User and above | Whether a block is legally pickable (24% minimum), and which week it lands on in the Harvest Calendar |
| **Avocado Ripening Test** | Shelf trials — fruit picked, then timed until it softens | Agriculture User and above | Recorded as a second check alongside dry matter, on the record for whoever wants to compare the two |
| **Avocado Yield History** | The estate's own historical delivered kilograms, per block, per year | Loaded from the estate's records by an administrator — not something typed in day to day | "Estimate vs delivered," and how a block's next crop is expected to swing between an on-year and an off-year |
| **Avocado Production Forecast** | Your own kilogram estimate for one block, one season, one crop | Agriculture User and above (desk, or the phone app) | The Manual view on Forecast & Blocks |
| **Avocado Production Budget** | The season's target, month by month | Agriculture Manager | The Season Budget card on Forecast & Blocks |

If a number on a page looks wrong, this table says which record to open
and fix — the pages themselves never let you type a number directly onto
them; they only display what these records add up to.

## 3. Season Outlook — the big picture

This is the page to open first — one screen that answers "how's the season
going?" without digging into any one block.

**Six headline numbers** across the top:
- **Season crop** — the total kilograms expected this crop.
- **Crop value** — what that's worth, at the price you type in.
- **Ready to pick** — how much of the forecast is already legally pickable
  (dry matter has crossed the export minimum).
- **Crew next week** — how many pickers next week's volume needs.
- **Estimate accuracy** — how close the estate's past estimates have
  landed against what was actually delivered, so you know how much to
  trust the forecast.
- **Stale readings** — dry matter tests that are too old to safely date a
  pick from any more, and need a fresh sample.

**The season timeline** — a strip showing the whole crop's shape over time:
which weeks are lightest, which are heaviest.

**The orchard map** — every block plotted on a satellite map, shaded by how
it's performing against what its own age normally gives — a block sitting
far above what its age band expects is worth a second look (it might be
under- or over-counted). Click any block to see its detail without leaving
the map.

**Three gauges** — Dry matter (how much of the crop is ready vs. still
maturing), Pickers (how the crew requirement is trending), and Lost to
sick trees (kilograms the estate won't get because of sick trees or gaps
in a block, priced at what that block would otherwise have given).

**Blocks** — the full block list underneath, for dropping from the big
picture into one block's detail.

The **price** and **crew size** boxes at the top adjust every money and
staffing figure on the page live — they're assumptions you're trying, not
saved settings.

## 4. Production Forecast — Automatic vs Manual, and Budget

This is the detailed version of the Season Outlook — one page, every
block, with the option to see either the computer's own numbers or your
own typed numbers side by side. Open it at `/avocado-production`.

### The Automatic / Manual switch

At the top of the page, next to the price box, there are two buttons:
**Manual** and **Automatic**. This is the single most important thing to
understand about this page.

- **Automatic** — the number the computer works out from the records in
  Section 2 above: how many trees are bearing fruit, how old they are, any
  fruit counts done in the field, and dry matter test results. Nobody has
  to type anything for this to appear.
- **Manual** — a number a person has typed into Avocado Production
  Forecast themselves, block by block, because they walked the orchard and
  have their own view of what it will give. This never gets overwritten by
  the computer's calculation — the two are always kept side by side, never
  mixed together.

**Manual is the default view.** If nobody has entered any manual figures
yet, the page tells you so in a small note under the toggle, and shows the
Automatic figures are just a click away.

Everything on the page that is a real measurement — the yield curve, the
pick schedule, dry matter test results, losses from sick trees, and how
last season's estimate compared with what was actually delivered — stays
the same in both views, because those are facts, not forecasts. Only the
**Forecast**, **Value**, **Bearing** and **Blocks** figures near the top,
and the block-by-block table further down, change depending on which
button is selected.

### The rest of the page

Underneath the toggle and the Season Budget (below), the same page also
shows, always calculated, never toggled:

- **Estimate vs delivered** — for blocks that have both an estimate and an
  actual harvest, how the estate's number compared to what the scale said.
- **By planting year** — the same comparison, grouped by how old the trees
  were when planted, because young and old blocks miss their estimate for
  different reasons.
- **Yield curve** — kilograms per tree by age band.
- **Pick schedule** — each block's kilograms, dated to the week its dry
  matter crosses the legal minimum, spread over about six picks.
- **Losses** — sick trees and gaps, priced at what that block's own age
  band would otherwise have given.
- **Maturity** — every block's latest dry matter reading against the 24%
  export minimum.
- **Data gaps** — reported rather than guessed at: any block missing a
  tree count, a variety, or a planting year is listed here, not silently
  estimated around.

### Season Budget

Just under the top numbers is a **Season Budget** card — the target agreed
for the season, set once by whoever plans it, entered into Avocado
Production Budget (Section 2). It is always a typed number; the computer
never invents a budget on its own.

**A budget is entered month by month, not as one lump number.** You say
what each month is expected to give (for example: August 150 t, September
400 t, October 350 t for the late crop) and the season total is simply
those months added up. You don't need to fill in every month — just the
ones the crop actually runs in (roughly Aug–Nov for the late crop, Jan–Jun
for the early one).

The card shows:
- **Budget** — the season total, added up from the months.
- **Manual/Automatic forecast** — whichever forecast you currently have
  selected above, so you can compare like with like.
- **Vs budget** — how far over or under the target the current forecast
  is, in kilograms and as a percentage.
- **Budget value** — what the budget is worth in money, if a price was
  agreed when the budget was set.
- **A month-by-month table** underneath, showing each month's target, its
  share of the total (as a bar), and its value.

If nothing has been budgeted yet for the season, the card says so.

## 5. Dry Matter Test — is it ready to pick?

This is where ripeness readings get typed in, at `/avocado-maturity`.
Every other page's "is it ready" answer comes from what's entered here —
nothing about ripeness is guessed.

**How to enter a test:**
1. Name the block the fruit came off. A block-level reading dates that
   block's own pick. A planting-area reading is inherited by every block
   planted that year — only use that when the test really was done for a
   whole area, not one block.
2. Enter the moisture, either as a fraction (0.77) or a percentage (77) —
   both read the same, and the dry matter figure is worked out for you.
   Leave a fruit size blank if you didn't test it — never enter zero for
   something you didn't measure.
3. Save the test.

**Why more than one visit matters:** one row is logged per visit to a
block. Two visits a fortnight apart let the system measure how fast that
particular block's dry matter is actually rising, instead of assuming the
estate's usual rate — blocks don't all mature at the same speed.

The **24% dry matter minimum** is the legal export threshold for Hass —
below it, fruit cannot ship however big or good-looking it is. This is the
one number in the whole module that is never adjustable.

## 6. Harvest Calendar — when each block gets picked

A week-by-week picture of the whole estate, at `/avocado-calendar` — one
row per block, one column per week (weeks start Monday).

- **Hatched weeks** mean that block is locked: it's under the 24% dry
  matter minimum and picking it that week would cost the export.
- **Dotted rows** mean a block has never been sampled — that's a missing
  measurement, not a verdict that it isn't ready.
- The **farm**, **year** and **metric** filters at the top narrow the grid
  down to what you're planning around.

Two lists sit alongside the grid:
- **No pick date** — forecast fruit that can't yet be placed on a week,
  because that block has no dry matter reading to date it from. Sample it
  (Section 5) and it joins the calendar.
- **No forecast** — blocks carrying no kilograms this season at all,
  either because they're too young to bear yet or because they have no
  planting year recorded (Section 2).

## 7. Picking Plan — how many pickers, and what it costs

The staffing and cost side of the same forecast, at `/avocado-labour`.

**Week by week**, each block's kilograms are divided by that block's own
picking rate (kilograms a picker takes off in a day — a property of the
block, nobody is ranked on it) to get the picker-days that week needs.
Bars that cross the crew-size line are the weeks worth having a staffing
conversation about ahead of time.

The **crew size**, **work days a week**, and **pay per day** boxes at the
top are assumptions you can try — they update the whole page's staffing
and wage numbers live, the same way price does on the other pages.

Two lists explain what's excluded, rather than silently folding it in:
- **Cannot staff yet** — fruit with no pick date, because its block has no
  dry matter sample.
- **Refused records** — past harvest records whose picker count couldn't
  possibly reflect one day's work. These are left out of the picking-rate
  calculation entirely rather than averaged in, because one bad record
  would throw off the whole crew estimate for a season.

## 8. The Avocado Trail phone app

A phone app for people out in the orchard, so fruit counts can be typed in
on the spot instead of on a notebook that gets copied later.

What it's for:

1. **Log in** with your usual Upande account.
2. **Pick a block or farm** from the list (searchable), from the app's
   menu.
3. **Count Fruit — one tree at a time.** Rather than typing an average
   figure from memory, you count each tree as you reach it: enter that
   tree's fruit count, tap **Next Tree**, and the running total and average
   climb as you go — capturing the walk itself, not a guess at the end of
   it. Finish when you've done enough trees (ten is the usual minimum for
   a reliable count, and the app gently reminds you if you stop earlier).
   When you finish, add the average fruit weight and expected drop if you
   know them, and save.
4. **Next block, straight away.** Once a block's count is saved, the app
   offers to jump straight into the next block rather than sending you
   back to a home screen.
5. **My Entries** — a simple list of everything you've logged, so you can
   check nothing was missed.
6. **Sync** — shows what's queued and what's already made it to the
   system, and whether you're online or offline right now.
7. **Works without signal.** If you're in a part of the orchard with no
   data connection, everything you enter is saved on the phone and sent to
   the system automatically as soon as it reconnects — nothing is lost,
   and nothing gets entered twice.

Setting your own block forecast or a budget is desk-only (Section 2) — the
phone app is kept to the one job of fast, accurate fruit counts from the
field.

## 9. Who can do what

| Role | Can do |
|---|---|
| **Agriculture User** | View every page above, including both Automatic and Manual figures; add fruit counts and their own block forecasts, from the desk or the phone app |
| **Agriculture Manager** | Everything above, plus edit the block master (Avocado Yield Block), set the Season Budget, edit or delete anyone's entries |
| **System Manager** | Full access, for IT/admin use |

If a screen or button seems to be missing, it's almost always a missing
role — ask an administrator to add **Agriculture User** (or **Agriculture
Manager**) to your account.

## 10. Quick answers

**Q: I typed a forecast for a block but I don't see it change on the desk
page.**
A: Make sure the toggle at the top of Forecast & Blocks is set to
**Manual**, not Automatic — typed figures only ever show in Manual view.

**Q: Can I change a forecast I already entered?**
A: Yes — find it in the Avocado Production Forecast list and edit it,
rather than creating a new one for the same block/season/crop (the system
stops duplicates and tells you which entry to edit instead).

**Q: Why is there no "Automatic" budget?**
A: A budget is a decision someone makes for the season, not something that
can be calculated from tree counts — so there's only ever one kind of
budget, and it's always the one a person typed in.

**Q: The phone app has no signal in part of the orchard — is my count
lost?**
A: No. It's saved on the phone and uploaded automatically once you're back
in signal. You can see what's still waiting to sync on the app's Sync
screen.

**Q: A block shows "no forecast" on the Harvest Calendar — is that a
bug?**
A: Usually not — it means the block is too young to bear yet, or has no
planting year recorded in Avocado Yield Block. Check the block's record
if it should be bearing by now.

**Q: What's the difference between "no pick date" and "no forecast"?**
A: "No forecast" means a block has no kilograms expected at all this
season. "No pick date" means a block does have expected kilograms, but
nobody has taken a dry matter sample yet to say which week it's ready.

**Q: I want to change a block's bearing tree count — where?**
A: Avocado Yield Block, and it needs an Agriculture Manager — it's the one
record every forecast on every page is built on, so it's kept to fewer
hands than day-to-day counts and tests.
