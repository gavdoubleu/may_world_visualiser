# Handoff — scaling `world_reader` aggregate-stats to large worlds

**Found during:** grilling session for PR6 (migrate WorldMap onto the
`world_reader` lazy backend — see
[`pr-06-migrate-worldmap-backend.md`](pr-06-migrate-worldmap-backend.md)).
**Status:** forward-looking note, not a current blocker. Current largest
fixture (`data/world_state_medieval.h5`) has ~4.75M people and ~20K geo units —
comfortably within the limits discussed below. This doc is for whoever needs to
scale to "hundreds of millions of people" worlds.

## Why this came up

PR6 adds new bulk-array aggregate-stat helpers to `world_reader`
(`compute_population_statistics`-style: `total_people`/`age_stats`/
`sex_distribution`, `geographical_distribution`, venue-type counts — see the
PR6 handoff for the byte-compatibility requirements driving these). Those new
helpers were designed to scale via integer-coded arrays + `np.bincount`/
`np.searchsorted` (no `np.unique`/sort), and should be fine into the hundreds
of millions of *people*. But while reasoning about that, two **pre-existing**
ceilings surfaced that PR6 inherits but isn't the right place to fix:

## 1. `compute_unit_statistics`'s full sort over all people

`world_reader/statistics.py:41`:

```python
sort_idx = np.argsort(person_geo_ids, kind='stable')
```

This sorts **every** person by geo-unit ID to group them for per-leaf-unit
aggregation (population/age/sex/venue-type breakdowns), then walks the sorted
runs. It's an O(N log N) pass over the full population, plus the memory for the
sort permutation and three reordered copies (`sg`, `sa`, `ss`). At hundreds of
millions of rows this is the dominant cost in the whole load path — already the
single largest contributor at ~5M rows on medieval (per ADR 0001's profiling:
the statistics passes dominate cold start).

**Open query for the next agent:** *is the sort actually necessary?* `geo_unit_ids`
are small integer codes with a known, bounded range (`geography.units_by_id`
gives the full set up front). Grouping by a bounded small-integer key is exactly
the case `np.bincount`/scatter-add (`np.add.at`) handle without sorting:
- `population` per unit → `np.bincount(person_geo_ids, minlength=n_units)`.
- `age_distribution` per unit → bucket ages into `AGE_LABELS` codes first
  (vectorised), then a 2-D scatter — e.g. `np.add.at(counts, (geo_codes, age_codes), 1)`
  or `np.bincount(geo_codes * n_age_buckets + age_codes)` reshaped — both O(N),
  no sort, no reordered copies.
- `sex_distribution` similarly via a combined `(geo_code, sex_code)` scatter.

If this works it would turn an O(N log N) sort-and-copy into a couple of O(N)
single-pass scatters — a substantial win at scale, and arguably a win even at
current size. Investigate whether there's a reason the sort-based approach was
chosen (e.g. needing contiguous runs for some other purpose downstream, or
`geo_unit_ids` not actually being densely-coded) before assuming the rewrite is
free.

## 2. `_compute_slim_statistics` / `_compute_array_stats` percentiles and `np.unique`

(To be moved into `world_reader` as part of PR6 — see PR6 handoff "app-agnostic
logic belongs in `world_reader`" decision.)

`_compute_array_stats` (`world_map/core/world_loader.py:137`) calls
`np.percentile` (requires a full sort) and, for the activity-map block,
`np.unique(activity_data[:, [0,1]], axis=0)` over potentially 30M+ rows — ADR
0001 already documents this as the ~22-25s dominant cost on medieval. At
hundreds of millions of rows this would be minutes, not seconds. No specific
fix proposed here — just flagging that moving this code doesn't change its
asymptotics, and it's the most likely next thing to need attention if world
sizes grow an order of magnitude.

## 3. Hundreds of millions of *geo units* is a different, bigger problem

This is **not** the same axis as "hundreds of millions of people" — typical
geo hierarchies (country > region > area > settlement) top out in the tens of
thousands (current: ~20K). If it ever did reach hundreds of millions:

- `GeographyManager` holds the entire tree as resident `GeoUnit` Python objects
  — memory alone (Python object overhead × 200M) would be infeasible.
- `compute_unit_statistics._aggregate` (`statistics.py:167`) **recurses** down
  the tree — would hit Python's recursion limit and be untenably slow even if
  rewritten iteratively, given the object count.
- This would require redesigning `GeographyManager`/`compute_unit_statistics`
  around an array-backed tree (e.g. parent-pointer arrays + Euler-tour
  aggregation, similar in spirit to `SubtreeIndex`) rather than resident
  objects — a `world_reader` architecture change, well beyond "scale up the
  stats helpers".

No action proposed here — just naming it so a future agent doesn't conflate
"more people" (tractable, addressed above) with "more geo units" (an
architecture rewrite).

## Suggested skills

- `diagnose` — if/when this becomes live (a real world file approaches these
  scales), profile first to confirm which of the above is actually the
  bottleneck before rewriting; don't optimise from this doc's predictions alone.
- `tdd` — any rewrite of `compute_unit_statistics`'s grouping should be covered
  by a test asserting identical output to the sort-based version on a small
  fixture, before/while replacing the implementation.
- `git_commits` — UK English, concise; no AI attribution or plan/handoff-file
  references in commit messages (repo convention — see "Conventions for all
  PRs" in `00_REFACTOR_PLAN.md`).
</content>
