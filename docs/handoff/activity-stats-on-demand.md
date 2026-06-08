# Handoff — future: on-demand activity statistics

**Context:** PR5 of the "collapse two HDF5 backends" series removed activity
statistics from WorldMap's live cold-start path (landing page + unit-detail
panel) — the `np.unique` over the ~30M-row activity map cost tens of seconds
and dominated load time. This doc captures the deferred on-demand design.

## What PR5 changed

- `load_world_from_hdf5` gained `compute_activity_stats: bool = False`. When
  `False` (the live WorldMap default), neither the world-level
  `slim_statistics.activity_map` block nor per-unit `activity_counts` are
  computed — `/api/world/statistics` and `/api/geography/unit/<name>` simply
  omit/empty those keys (no route changes; pure pass-through on presence).
- Two live UI blocks were removed as a result: the "Activities" section on
  the WorldMap landing page (`buildSlimStatsHtml` in `app.js`) and the
  "Activity Breakdown" bar chart in the unit-detail panel.

## Static-export finding (the investigation PR5 was asked to do)

`export_static._collect_data` drives the **same** `/api/world/statistics` and
`/api/geography/unit/<name>` endpoints via a Flask test client over the world
object built at export time. It therefore bakes **both**:
- world-level activity stats (`slim_statistics.activity_map`, via
  `_compute_slim_statistics`), and
- unit-level activity stats (`activity_counts` per geo unit, via
  `compute_unit_statistics`, embedded in each `geography_units[<name>]`
  detail blob fetched in the per-unit loop).

So the static export already pre-bakes **per-unit** activity breakdowns, not
just a world aggregate. PR5 preserves this exactly: `export_static.py` now
calls `load_world_from_hdf5(path, compute_activity_stats=True)`, paying the
`np.unique` cost once, offline, at export time — never on live cold start.
The exported site is unaffected by this change; only the *live* server got
faster.

## Goal for the on-demand feature

WorldMap landing loads fast (no activity `np.unique` at startup); activity
stats are served on demand instead, restoring (in some form) the displays
removed in PR5.

**Live server:** new endpoint, e.g. `GET /api/geography/unit/<name>/activity-stats`.
Computes the activity-map `np.unique` scoped to that unit's subtree using
`SubtreeIndex.person_rows(unit_id)` → activity-map offsets — far cheaper than
whole-world. Cache per-unit (in-memory). Frontend: a "Statistics" button in
the detail panel triggers the fetch and renders something resembling the
removed "Activity Breakdown" chart.

**Static export:** no change needed — it already pre-bakes per-unit
`activity_counts` (see finding above) plus the world-level aggregate; the
fetch interceptor can continue serving them from the baked bundle, or the
on-demand endpoint's shape can be matched to reuse the same baked data.

## Open

- Granularity: per-leaf vs aggregated-upward for the on-demand endpoint.
- Cache eviction policy for the live per-unit cache.
- Whether to also expose a world-level on-demand endpoint, or rely on the
  (currently hidden) `slim_statistics.activity_map` that export still bakes.
