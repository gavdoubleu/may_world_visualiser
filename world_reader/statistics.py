"""Per-geographic-unit statistics, computed directly from HDF5 arrays.

Shared by world_map (needs activity counts) and world_explorer (skips them —
the np.unique over the full activity map costs tens of seconds and the
explorer UI never displays activity stats).
"""

import logging

import numpy as np

from world_reader.geography import AGE_LABELS, AGE_BREAKS, UnitStats

logger = logging.getLogger("world_reader.statistics")


def compute_unit_statistics(f, geography, *, include_activity_counts: bool) -> dict:
    """Pre-compute per-geographic-unit statistics from HDF5 arrays."""
    if 'population' not in f:
        return {}

    pop             = f['population']
    person_ids_arr  = pop['ids'][:]
    person_geo_ids  = pop['geo_unit_ids'][:]
    ages            = pop['ages'][:].astype(np.float64)

    sex_raw = pop['sexes'][:]
    if sex_raw.dtype.kind in ('u', 'i'):
        _sex_labels = np.array(['male', 'female', 'unknown'])
        sexes = _sex_labels[np.clip(sex_raw.astype(np.int64), 0, 2)]
    else:
        sexes = sex_raw.astype(str)

    uid_to_name = {uid: u.name for uid, u in geography.units_by_id.items()}

    AGE_BREAKS_NP = AGE_BREAKS[:-1] + [np.inf]

    if len(person_geo_ids) == 0:
        return {}

    sort_idx = np.argsort(person_geo_ids, kind='stable')
    sg = person_geo_ids[sort_idx]
    sa = ages[sort_idx]
    ss = sexes[sort_idx]

    bounds   = np.where(np.diff(sg) != 0)[0] + 1
    g_starts = np.concatenate([[0], bounds])
    g_ends   = np.concatenate([bounds, [len(sg)]])

    direct_stats: dict = {}
    for i, geo_id in enumerate(sg[g_starts]):
        unit_name = uid_to_name.get(int(geo_id))
        if unit_name is None:
            continue
        s, e = int(g_starts[i]), int(g_ends[i])

        age_dist: dict = {}
        for j, label in enumerate(AGE_LABELS):
            lo, hi = AGE_BREAKS_NP[j], AGE_BREAKS_NP[j + 1]
            age_dist[label] = int(np.sum((sa[s:e] >= lo) & (sa[s:e] < hi)))

        sex_u, sex_c = np.unique(ss[s:e], return_counts=True)
        direct_stats[unit_name] = {
            'population':       int(e - s),
            'age_distribution': age_dist,
            'sex_distribution': {str(k): int(v) for k, v in zip(sex_u, sex_c)},
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

        if type_reg is not None and types_raw.dtype.kind in ('u', 'i') and len(types_raw):
            v_types = type_reg[types_raw.astype(int)]
        elif len(types_raw):
            v_types = types_raw.astype(str)
        else:
            v_types = np.array([])

        if len(v_types):
            v_sort    = np.argsort(v_geo_ids, kind='stable')
            svg       = v_geo_ids[v_sort]
            svt       = v_types[v_sort]
            vb        = np.where(np.diff(svg) != 0)[0] + 1
            vs_starts = np.concatenate([[0], vb])
            vs_ends   = np.concatenate([vb, [len(svg)]])

            for i, geo_id in enumerate(svg[vs_starts]):
                unit_name = uid_to_name.get(int(geo_id))
                if not unit_name:
                    continue
                s, e = int(vs_starts[i]), int(vs_ends[i])
                t_u, t_c = np.unique(svt[s:e], return_counts=True)
                # Venues attach to any GeoUnit (leaf or not), independent of
                # resident population — seed an entry for venue-only units
                # rather than dropping their counts (they'd otherwise never
                # be recovered by _aggregate).
                direct_stats.setdefault(unit_name, {
                    'population':       0,
                    'age_distribution': {},
                    'sex_distribution': {},
                    'venue_types':      {},
                    'activity_counts':  {},
                })['venue_types'] = {
                    str(k): int(cnt) for k, cnt in zip(t_u, t_c)
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
                    geo_id    = int(gas[ga_starts[k], 0])
                    act_idx   = int(gas[ga_starts[k], 1])
                    count     = int(ga_ends[k] - ga_starts[k])
                    unit_name = uid_to_name.get(geo_id)
                    if unit_name and unit_name in direct_stats:
                        direct_stats[unit_name]['activity_counts'][
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
            return all_stats.get(unit.name, {
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
        if unit.name in direct_stats:
            _add(agg, direct_stats[unit.name])
        for child in unit.children:
            _add(agg, _aggregate(child))
        all_stats[unit.name] = agg
        return agg

    for unit in geography.units_by_id.values():
        if unit.parent is None:
            _aggregate(unit)

    return {
        name: UnitStats(
            population=int(d['population']),
            age_distribution={k: int(v) for k, v in d['age_distribution'].items()},
            sex_distribution={str(k): int(v) for k, v in d['sex_distribution'].items()},
            venue_types={str(k): int(v) for k, v in d.get('venue_types', {}).items()},
            activity_counts={str(k): int(v) for k, v in d.get('activity_counts', {}).items()},
        )
        for name, d in all_stats.items()
    }


# ─── slim (whole-world) statistics ────────────────────────────────────────────

_SEX_LABELS = np.array(['male', 'female', 'unknown'])


def _compute_array_stats(data, max_categories: int = 25) -> dict:
    """Numeric or categorical summary stats for a single HDF5 dataset array."""
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
        values = data.astype(str)
        unique, counts = np.unique(values, return_counts=True)
        total = int(len(values))
        order = np.argsort(-counts)
        top_u = unique[order[:max_categories]]
        top_c = counts[order[:max_categories]]
        return {
            'type': 'categorical',
            'count': total,
            'unique_count': int(len(unique)),
            'top_values': {
                str(k): {'count': int(v), 'pct': round(100.0 * v / total, 2)}
                for k, v in zip(top_u, top_c)
            },
        }
    except Exception as exc:
        return {'type': 'unknown', 'error': str(exc)}


def compute_slim_statistics(f, compute_activity_stats: bool = False) -> dict:
    """Compute aggregate statistics from an open HDF5 file.

    `compute_activity_stats` gates the world-level activity-map breakdown
    (an `np.unique` over the full activity map costing tens of seconds) —
    skipped on live loads, computed for the static export.
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

def compute_population_statistics(f) -> dict:
    """Population-wide total/age/sex aggregates from HDF5 arrays.

    Sex codes are bounded (0/1/2), so a bincount scatter replaces the
    sort-based grouping that doesn't scale to large populations.
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


def compute_geographical_distribution(person_geo_unit_ids, geography) -> dict:
    """Per-level counts of people by their *direct* geo unit (not descendants).

    Geo-unit IDs are bounded small-integer codes, so this is a single
    id→level lookup scatter plus a bincount — O(N + units), no per-unit
    Python loop over resident people lists.
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


def compute_venue_type_counts(venue_types_arr, venue_type_names) -> dict:
    """Venue counts per type, derived from the resident type-code array."""
    if venue_types_arr is None or len(venue_types_arr) == 0:
        return {}
    counts = np.bincount(venue_types_arr.astype(np.int64), minlength=len(venue_type_names))
    return {
        venue_type_names[code]: int(counts[code])
        for code in range(len(venue_type_names))
        if counts[code] > 0
    }


def venue_type_names_present(venue_types_arr, venue_type_names) -> list[str]:
    """Distinct venue type names present, ordered by first appearance.

    Returns insertion-order-distinct names — used by `/api/world/statistics`'s
    `venue_types` list.
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
