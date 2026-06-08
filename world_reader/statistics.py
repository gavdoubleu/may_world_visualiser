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

    leaf_stats: dict = {}
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
        leaf_stats[unit_name] = {
            'population':       int(e - s),
            'age_distribution': age_dist,
            'sex_distribution': {str(k): int(v) for k, v in zip(sex_u, sex_c)},
            'venue_types':      {},
            'activity_counts':  {},
        }

    # ── venue type counts per leaf unit ──────────────────────────────────────
    if 'venues' in f:
        v           = f['venues']
        v_geo_ids   = v['geo_unit_ids'][:]
        types_raw   = v['types'][:] if 'types' in v else np.array([], dtype='u1')

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
                if unit_name and unit_name in leaf_stats:
                    s, e = int(vs_starts[i]), int(vs_ends[i])
                    t_u, t_c = np.unique(svt[s:e], return_counts=True)
                    leaf_stats[unit_name]['venue_types'] = {
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
                    if unit_name and unit_name in leaf_stats:
                        leaf_stats[unit_name]['activity_counts'][
                            str(activity_names[act_idx])
                        ] = count

    # ── aggregate upward through hierarchy ───────────────────────────────────
    all_stats = dict(leaf_stats)

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
        if unit.name in leaf_stats:
            _add(agg, leaf_stats[unit.name])
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
