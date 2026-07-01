"""Per-geographic-unit statistics, computed directly from HDF5 arrays.

Shared by world_map (needs activity counts) and world_explorer (skips them —
the np.unique over the full activity map costs tens of seconds and the
explorer UI never displays activity stats).
"""

import logging

import h5py
import numpy as np
import pandas as pd

from world_reader.geography import AGE_LABELS, AGE_BREAKS, GeographyManager, UnitStats

logger = logging.getLogger("world_reader.statistics")


def compute_unit_statistics(
    f: h5py.File, geography: GeographyManager, *, include_activity_counts: bool
) -> dict[int, UnitStats]:
    """Pre-compute per-GeoUnit statistics, aggregated up the hierarchy.

    Direct (own-assignment) stats are computed per unit from the population
    and venues arrays, then summed into each ancestor so every unit's
    UnitStats covers its whole subtree.

    Args:
        f: Open HDF5 world file.
        geography: GeographyManager with the GeoUnit hierarchy already loaded.
        include_activity_counts: Compute per-unit activity-type counts (an
            `np.unique` over the full activity map costing tens of seconds).
            WorldExplorer skips these; the static export needs them.

    Returns:
        `{unit_id: UnitStats}` covering every unit with a direct assignment
        or a descendant with one. Empty dict if `f` has no `population` group.
    """
    if 'population' not in f:
        return {}

    pop             = f['population']
    person_ids_arr  = pop['ids'][:]
    person_geo_ids  = pop['geo_unit_ids'][:]
    ages            = pop['ages'][:].astype(np.float64)

    sex_raw = pop['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        # Already integer-coded — use the codes directly rather than
        # materialising a full string array just to re-discover them below.
        sex_labels_all = np.array(['male', 'female', 'unknown'])
        sex_codes_all  = np.clip(sex_raw.astype(np.int64), 0, 2)
    else:
        sex_codes_all, sex_labels_all = pd.factorize(sex_raw.astype(str))
        sex_labels_all = np.asarray(sex_labels_all)
    num_sex_labels = len(sex_labels_all)

    AGE_BREAKS_NP = AGE_BREAKS[:-1] + [np.inf]

    if len(person_geo_ids) == 0:
        return {}

    sort_idx = np.argsort(person_geo_ids, kind='stable')
    sg = person_geo_ids[sort_idx]
    sa = ages[sort_idx]

    bounds   = np.where(np.diff(sg) != 0)[0] + 1
    g_starts = np.concatenate([[0], bounds])
    g_ends   = np.concatenate([bounds, [len(sg)]])

    # Per-unit sex-distribution counts, all groups at once — group boundaries
    # are already known from the geo-id sort above, so a single bincount over
    # (group_index, sex_code) replaces one np.unique call per geo unit with
    # no sorting at all (cheaper than a lexsort+diff groupby for this few-
    # category case).
    sc             = sex_codes_all[sort_idx]
    group_idx      = np.repeat(np.arange(len(g_starts)), g_ends - g_starts)
    sex_counts     = np.bincount(
        group_idx.astype(np.int64) * num_sex_labels + sc,
        minlength=len(g_starts) * num_sex_labels,
    ).reshape(len(g_starts), num_sex_labels)

    sex_distribution_by_unit: dict[int, dict] = {}
    for k in range(len(g_starts)):
        unit_id = int(sg[g_starts[k]])
        nz = np.nonzero(sex_counts[k])[0]
        if len(nz):
            sex_distribution_by_unit[unit_id] = {
                str(sex_labels_all[j]): int(sex_counts[k, j]) for j in nz
            }

    direct_stats: dict = {}
    for i, geo_id in enumerate(sg[g_starts]):
        unit_id = int(geo_id)
        if unit_id not in geography.units_by_id:
            continue
        s, e = int(g_starts[i]), int(g_ends[i])

        age_dist: dict = {}
        for j, label in enumerate(AGE_LABELS):
            lo, hi = AGE_BREAKS_NP[j], AGE_BREAKS_NP[j + 1]
            age_dist[label] = int(np.sum((sa[s:e] >= lo) & (sa[s:e] < hi)))

        direct_stats[unit_id] = {
            'population':       int(e - s),
            'age_distribution': age_dist,
            'sex_distribution': sex_distribution_by_unit.get(unit_id, {}),
            'venue_types':      {},
            'activity_counts':  {},
        }

    # ── venue type counts per directly-assigned unit (leaf or not) ───────────
    # ChildVenues never appear in a unit's top-level venue list (they're only
    # reachable by expanding their ParentVenue) — exclude them here too, or
    # WorldExplorer renders an unreachable section that never finishes loading.
    if 'venues' in f:
        v           = f['venues']
        v_geo_ids   = v['geo_unit_ids'][:]
        types_raw   = v['types'][:] if 'types' in v else np.array([], dtype='u1')

        num_venues_total = len(v_geo_ids)
        v_parent_ids = (v['parent_ids'][:] if 'parent_ids' in v
                        else np.full(num_venues_total, -1, dtype=np.int32))
        top_level_mask = v_parent_ids == -1
        v_geo_ids = v_geo_ids[top_level_mask]
        types_raw = types_raw[top_level_mask]

        type_reg = None
        try:
            type_reg = f['metadata']['registries']['venue_types'][:].astype(str)
        except Exception:
            pass

        # Already integer-coded when a registry is present — use the codes
        # directly rather than materialising a full string array just to
        # re-discover them below.
        if len(types_raw) == 0:
            type_codes_all, type_labels_all = np.array([], dtype=np.int64), np.array([])
        elif type_reg is not None and types_raw.dtype.kind in ('u', 'i'):
            type_codes_all, type_labels_all = types_raw.astype(np.int64), type_reg
        else:
            type_codes_all, type_labels_all = pd.factorize(types_raw.astype(str))
            type_labels_all = np.asarray(type_labels_all)

        if len(type_codes_all):
            v_sort    = np.argsort(v_geo_ids, kind='stable')
            svg       = v_geo_ids[v_sort]

            vb        = np.where(np.diff(svg) != 0)[0] + 1
            vs_starts = np.concatenate([[0], vb])
            vs_ends   = np.concatenate([vb, [len(svg)]])

            # Per-unit venue-type counts, all groups at once — same
            # sort-free bincount approach as sex_distribution above.
            num_type_labels = len(type_labels_all)
            tc              = type_codes_all[v_sort]
            v_group_idx     = np.repeat(np.arange(len(vs_starts)), vs_ends - vs_starts)
            type_counts     = np.bincount(
                v_group_idx.astype(np.int64) * num_type_labels + tc,
                minlength=len(vs_starts) * num_type_labels,
            ).reshape(len(vs_starts), num_type_labels)

            for k in range(len(vs_starts)):
                unit_id = int(svg[vs_starts[k]])
                if unit_id not in geography.units_by_id:
                    continue
                nz = np.nonzero(type_counts[k])[0]
                if not len(nz):
                    continue
                # Venues attach to any GeoUnit (leaf or not), independent of
                # resident population — seed an entry for venue-only units
                # rather than dropping their counts (they'd otherwise never
                # be recovered by _aggregate).
                direct_stats.setdefault(unit_id, {
                    'population':       0,
                    'age_distribution': {},
                    'sex_distribution': {},
                    'venue_types':      {},
                    'activity_counts':  {},
                })['venue_types'] = {
                    str(type_labels_all[j]): int(type_counts[k, j]) for j in nz
                }

    # ── activity counts per leaf unit ────────────────────────────────────────
    if include_activity_counts:
        act_grp = 'activity_mappings' if 'activity_mappings' in f else 'relationships'
        if act_grp in f and 'activity_map' in f[act_grp]:
            am             = f[act_grp]['activity_map']
            activity_names = am['activity_names'][:].astype(str)
            act_data       = am['activity_data'][:]

            max_pid    = int(np.max(person_ids_arr))
            pid_to_geo = np.full(max_pid + 1, -1, dtype=np.int64)
            pid_to_geo[person_ids_arr.astype(np.int64)] = person_geo_ids.astype(np.int64)

            pa_pairs = np.unique(act_data[:, [0, 1]].astype(np.int64), axis=0)
            pa_pids  = pa_pairs[:, 0]
            valid    = pa_pids <= max_pid
            pa_pids, pa_acts = pa_pids[valid], pa_pairs[valid, 1]
            geo_ids  = pid_to_geo[pa_pids]
            valid2   = geo_ids >= 0

            geo_act = np.column_stack([geo_ids[valid2], pa_acts[valid2]])
            if len(geo_act):
                ga_sort   = np.lexsort((geo_act[:, 1], geo_act[:, 0]))
                gas       = geo_act[ga_sort]
                ga_b      = np.where(np.any(np.diff(gas, axis=0) != 0, axis=1))[0] + 1
                ga_starts = np.concatenate([[0], ga_b])
                ga_ends   = np.concatenate([ga_b, [len(gas)]])

                for k in range(len(ga_starts)):
                    unit_id = int(gas[ga_starts[k], 0])
                    act_idx = int(gas[ga_starts[k], 1])
                    count   = int(ga_ends[k] - ga_starts[k])
                    if unit_id in direct_stats:
                        direct_stats[unit_id]['activity_counts'][
                            str(activity_names[act_idx])
                        ] = count

    # ── aggregate upward through hierarchy ───────────────────────────────────
    all_stats = dict(direct_stats)

    def _add(dst: dict, src: dict) -> None:
        dst['population'] = dst.get('population', 0) + src.get('population', 0)
        for label in AGE_LABELS:
            dst.setdefault('age_distribution', {})[label] = (
                dst.get('age_distribution', {}).get(label, 0)
                + src.get('age_distribution', {}).get(label, 0)
            )
        for sex, cnt in src.get('sex_distribution', {}).items():
            dst.setdefault('sex_distribution', {})[sex] = (
                dst.get('sex_distribution', {}).get(sex, 0) + cnt
            )
        for vt, cnt in src.get('venue_types', {}).items():
            dst.setdefault('venue_types', {})[vt] = (
                dst.get('venue_types', {}).get(vt, 0) + cnt
            )
        for act, cnt in src.get('activity_counts', {}).items():
            dst.setdefault('activity_counts', {})[act] = (
                dst.get('activity_counts', {}).get(act, 0) + cnt
            )

    def _aggregate(unit) -> dict:
        if not unit.children:
            return all_stats.get(unit.id, {
                'population': 0,
                'age_distribution': {k: 0 for k in AGE_LABELS},
                'sex_distribution': {},
                'venue_types': {},
                'activity_counts': {},
            })
        agg: dict = {
            'population': 0,
            'age_distribution': {k: 0 for k in AGE_LABELS},
            'sex_distribution': {},
            'venue_types': {},
            'activity_counts': {},
        }
        if unit.id in direct_stats:
            _add(agg, direct_stats[unit.id])
        for child in unit.children:
            _add(agg, _aggregate(child))
        all_stats[unit.id] = agg
        return agg

    for unit in geography.units_by_id.values():
        if unit.parent is None:
            _aggregate(unit)

    return {
        unit_id: UnitStats(
            population=int(d['population']),
            age_distribution={k: int(v) for k, v in d['age_distribution'].items()},
            sex_distribution={str(k): int(v) for k, v in d['sex_distribution'].items()},
            venue_types={str(k): int(v) for k, v in d.get('venue_types', {}).items()},
            activity_counts={str(k): int(v) for k, v in d.get('activity_counts', {}).items()},
        )
        for unit_id, d in all_stats.items()
    }


# ─── slim (whole-world) statistics ────────────────────────────────────────────

_SEX_LABELS = np.array(['male', 'female', 'unknown'])


def _compute_array_stats(data, max_categories: int = 25) -> dict:
    """Numeric or categorical summary stats for a single HDF5 dataset array.

    Args:
        data: Numeric or string-like HDF5 dataset (already read into memory).
        max_categories: Max number of distinct values to report for
            categorical data, by descending frequency.

    Returns:
        For numeric data: `{type: 'numeric', count, mean, std, min, max,
        p25, median, p75}`. For categorical data: `{type: 'categorical',
        count, unique_count, top_values}`. On error: `{type: 'unknown',
        error}`.
    """
    if data.dtype.kind in ('f', 'u', 'i'):
        arr = data.astype(np.float64).ravel()
        finite = arr[np.isfinite(arr)]
        if len(finite) == 0:
            return {'type': 'numeric', 'count': 0}
        return {
            'type': 'numeric',
            'count': int(len(finite)),
            'mean': round(float(np.mean(finite)), 4),
            'std': round(float(np.std(finite)), 4),
            'min': float(np.min(finite)),
            'max': float(np.max(finite)),
            'p25': float(np.percentile(finite, 25)),
            'median': float(np.median(finite)),
            'p75': float(np.percentile(finite, 75)),
        }
    try:
        counts = pd.Series(data).value_counts()
        total = int(len(data))
        top = counts.head(max_categories)
        return {
            'type': 'categorical',
            'count': total,
            'unique_count': int(len(counts)),
            'top_values': {
                str(k): {'count': int(v), 'pct': round(100.0 * v / total, 2)}
                for k, v in top.items()
            },
        }
    except (TypeError, ValueError) as exc:
        logger.warning("Categorical stats failed for property: %s", exc)
        return {'type': 'unknown', 'error': str(exc)}


def compute_slim_statistics(f: h5py.File, compute_activity_stats: bool = False) -> dict:
    """Compute world-level summary statistics from an open HDF5 file.

    Args:
        f: Open HDF5 world file.
        compute_activity_stats: Compute the world-level activity-map
            breakdown (an `np.unique` over the full activity map costing
            tens of seconds) — skipped on live loads, computed for the
            static export.

    Returns:
        A dict with keys `person_properties`, `subset_sizes` (if any
        non-empty subsets), `activity_map` (if `compute_activity_stats`),
        and `venue_properties`. Each `*_properties` value is keyed by
        property name with `_compute_array_stats` output.
    """
    stats: dict = {}

    # ── person properties ────────────────────────────────────────────────────
    person_stats: dict = {}
    if 'population' in f:
        pop = f['population']
        if 'ages' in pop:
            person_stats['age'] = _compute_array_stats(pop['ages'][:])
        if 'sexes' in pop:
            sex_raw = pop['sexes'][:]
            if sex_raw.dtype.kind in ('u', 'i'):
                sexes = _SEX_LABELS[np.clip(sex_raw.astype(np.int64), 0, 2)]
            else:
                sexes = sex_raw.astype(str)
            person_stats['sex'] = _compute_array_stats(sexes)
        if 'properties' in pop:
            for prop_name in pop['properties'].keys():
                try:
                    person_stats[prop_name] = _compute_array_stats(
                        pop['properties'][prop_name][:]
                    )
                except Exception as exc:
                    person_stats[prop_name] = {'type': 'error', 'error': str(exc)}
    stats['person_properties'] = person_stats

    # ── subset sizes ─────────────────────────────────────────────────────────
    if 'venues' in f and 'subsets' in f['venues']:
        mc = f['venues']['subsets']['member_counts'][:].astype(np.int64)
        non_empty = mc[mc > 0]
        if len(non_empty):
            stats['subset_sizes'] = {
                'mean': round(float(np.mean(non_empty)), 2),
                'median': float(np.median(non_empty)),
                'min': int(np.min(non_empty)),
                'max': int(np.max(non_empty)),
                'total_subsets': int(len(mc)),
                'non_empty_subsets': int(len(non_empty)),
            }

    # ── activity map ─────────────────────────────────────────────────────────
    activity_group_name = (
        'activity_mappings' if 'activity_mappings' in f else 'relationships'
    )
    if (
        compute_activity_stats
        and activity_group_name in f
        and 'activity_map' in f[activity_group_name]
    ):
        am               = f[activity_group_name]['activity_map']
        activity_names   = am['activity_names'][:].astype(str)
        activity_offsets = am['activity_offsets'][:]
        activity_data    = am['activity_data'][:]

        n_people = len(activity_offsets)
        n_rows   = len(activity_data)

        if n_rows > 0:
            pairs = np.unique(activity_data[:, [0, 1]].astype(np.int64), axis=0)
            people_per_act = np.zeros(len(activity_names), dtype=np.int64)
            np.add.at(people_per_act, pairs[:, 1], 1)
            unique_people    = int(len(np.unique(pairs[:, 0])))
            mean_unique_acts = len(pairs) / unique_people if unique_people else 0.0
        else:
            people_per_act   = np.zeros(len(activity_names), dtype=np.int64)
            unique_people    = 0
            mean_unique_acts = 0.0

        mean_assignments = n_rows / n_people if n_people else 0.0

        if 'venues' in f and 'subsets' in f['venues'] and n_rows > 0:
            mc_arr       = f['venues']['subsets']['member_counts'][:].astype(np.float64)
            non_empty_mc = mc_arr[mc_arr > 0]
            mean_contacts_est = (
                round(float(np.mean(non_empty_mc - 1)) * mean_assignments, 1)
                if len(non_empty_mc) else 0.0
            )
        else:
            mean_contacts_est = 0.0

        stats['activity_map'] = {
            'activity_counts': {
                str(activity_names[i]): int(people_per_act[i])
                for i in range(len(activity_names))
            },
            'total_people_with_activities': unique_people,
            'mean_activity_types_per_person': round(float(mean_unique_acts), 2),
            'mean_venue_assignments_per_person': round(float(mean_assignments), 2),
            'mean_contacts_estimate': mean_contacts_est,
        }

    # ── venue properties ─────────────────────────────────────────────────────
    venue_prop_stats: dict = {}
    if 'venues' in f and 'properties' in f['venues']:
        for venue_type in f['venues']['properties'].keys():
            vt_stats: dict = {}
            for prop_name in f['venues']['properties'][venue_type].keys():
                try:
                    vt_stats[prop_name] = _compute_array_stats(
                        f['venues']['properties'][venue_type][prop_name][:]
                    )
                except Exception as exc:
                    vt_stats[prop_name] = {'type': 'error', 'error': str(exc)}
            if vt_stats:
                venue_prop_stats[venue_type] = vt_stats
    stats['venue_properties'] = venue_prop_stats

    return stats


# ─── whole-world aggregate helpers (bulk-array, no sort/np.unique over N) ──────

def compute_population_statistics(f: h5py.File) -> dict:
    """Population-wide total/age/sex aggregates from HDF5 arrays.

    Sex codes are bounded (0/1/2), so a bincount scatter replaces the
    sort-based grouping that doesn't scale to large populations.

    Args:
        f: Open HDF5 world file.

    Returns:
        `{total_people: 0}` if there is no population. Otherwise
        `{total_people, age_stats: {mean, min, max}, sex_distribution}`.
    """
    if 'population' not in f:
        return {'total_people': 0}

    pop  = f['population']
    ages = pop['ages'][:]
    total = len(ages)
    if not total:
        return {'total_people': 0}

    sex_raw = pop['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        sex_codes  = np.clip(sex_raw.astype(np.int64), 0, 2)
        sex_counts = np.bincount(sex_codes, minlength=3)
        sex_distribution = {
            label: int(sex_counts[code])
            for code, label in enumerate(_SEX_LABELS)
            if sex_counts[code] > 0
        }
    else:
        sex_unique, sex_counts = np.unique(sex_raw.astype(str), return_counts=True)
        sex_distribution = {str(k): int(v) for k, v in zip(sex_unique, sex_counts)}

    return {
        'total_people': int(total),
        'age_stats': {
            'mean': round(float(np.mean(ages)), 2),
            'min': int(np.min(ages)),
            'max': int(np.max(ages)),
        },
        'sex_distribution': sex_distribution,
    }


def compute_geographical_distribution(
    person_geo_unit_ids: np.ndarray, geography: GeographyManager
) -> dict:
    """Per-level counts of people by their *direct* geo unit (not descendants).

    Geo-unit IDs are bounded small-integer codes, so this is a single
    id→level lookup scatter plus a bincount — O(N + units), no per-unit
    Python loop over resident people lists.

    Args:
        person_geo_unit_ids: int array, one direct geo-unit id per person.
        geography: GeographyManager with the GeoUnit hierarchy already loaded.

    Returns:
        `{level_name: count}` for levels with at least one person directly
        assigned. Empty dict if `person_geo_unit_ids` is empty.
    """
    if person_geo_unit_ids is None or len(person_geo_unit_ids) == 0:
        return {}

    levels = list(geography.levels)
    level_to_code = {level: code for code, level in enumerate(levels)}

    max_id = int(person_geo_unit_ids.max())
    geoid_to_level_code = np.full(max_id + 1, -1, dtype=np.int64)
    for unit_id, unit in geography.units_by_id.items():
        if 0 <= unit_id <= max_id:
            geoid_to_level_code[unit_id] = level_to_code.get(unit.level, -1)

    level_codes = geoid_to_level_code[person_geo_unit_ids.astype(np.int64)]
    valid       = level_codes >= 0
    counts      = np.bincount(level_codes[valid], minlength=len(levels))

    return {levels[code]: int(counts[code]) for code in range(len(levels)) if counts[code] > 0}


def compute_venue_type_counts(venue_types_arr: np.ndarray, venue_type_names: list[str]) -> dict:
    """Venue counts per type, derived from the resident type-code array.

    Args:
        venue_types_arr: int array of per-venue type codes.
        venue_type_names: Type names indexed by code.

    Returns:
        `{venue_type_name: count}` for types with at least one venue. Empty
        dict if `venue_types_arr` is empty.
    """
    if venue_types_arr is None or len(venue_types_arr) == 0:
        return {}
    counts = np.bincount(venue_types_arr.astype(np.int64), minlength=len(venue_type_names))
    return {
        venue_type_names[code]: int(counts[code])
        for code in range(len(venue_type_names))
        if counts[code] > 0
    }


def venue_type_names_present(venue_types_arr: np.ndarray, venue_type_names: list[str]) -> list[str]:
    """Distinct venue type names present, ordered by first appearance.

    Used by `/api/world/statistics`'s `venue_types` list.

    Args:
        venue_types_arr: int array of per-venue type codes.
        venue_type_names: Type names indexed by code.

    Returns:
        Distinct type names in order of first appearance in
        `venue_types_arr`. Empty list if `venue_types_arr` is empty.
    """
    if venue_types_arr is None or len(venue_types_arr) == 0:
        return []
    codes = venue_types_arr.astype(np.int64)
    n     = len(venue_type_names)
    first_pos = np.full(n, len(codes), dtype=np.int64)
    np.minimum.at(first_pos, codes, np.arange(len(codes), dtype=np.int64))
    present = np.where(first_pos < len(codes))[0]
    order   = present[np.argsort(first_pos[present])]
    return [venue_type_names[code] for code in order]
