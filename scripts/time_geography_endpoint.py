#!/usr/bin/env python3
"""Time the cold path of /api/geography/<level>, stage by stage.

Runs the endpoint's build in-process, outside Flask, so the numbers are not
confounded by the dev server, the network, or the browser. Splits the cold
cost into the stages that have different fixes:

  units      GeographyManager.get_units_by_level
  loop       the per-unit feature-dict loop
  serialise  orjson.dumps of the FeatureCollection
  transfer   payload size, raw and gzipped (what the wire cost would be)

The client-side cost (parsing the payload, building Leaflet markers) is NOT
measured here — that needs the browser.

Usage:
  python scripts/time_geography_endpoint.py <path_to.h5> [--level LEVEL]... [--repeats N]
"""
import argparse
import gzip
import sys
import time
from pathlib import Path

import orjson

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from world_map.geojson import point_feature, feature_collection
from world_reader import build_world_store


def build_level_payload(world, level):
    """Replicate world_map/routes/geography.py's cold path for one level.

    Kept deliberately in step with the route: if the route's loop changes,
    change this too, or the measurement stops describing the endpoint.
    """
    get_stats = world.stats_for_geo_unit
    units = world.geography.get_units_by_level(level)

    start_loop = time.perf_counter()
    features = []
    append_feature = features.append
    for unit in units.values():
        coordinates = unit.coordinates
        if not coordinates:
            continue

        lat, lon = coordinates
        stats = get_stats(unit.id)
        venue_types = stats.venue_types if stats else {}

        append_feature(point_feature(lat, lon, {
            'id': unit.id,
            'name': unit.name,
            'level': unit.level,
            'population': stats.population if stats else 0,
            'venues_count': sum(venue_types.values()),
            'venue_types': venue_types,
            'has_parent': unit.parent is not None,
            'children_count': len(unit.children),
        }))
    loop_seconds = time.perf_counter() - start_loop

    start_serialise = time.perf_counter()
    body = orjson.dumps(
        feature_collection(features), option=orjson.OPT_SERIALIZE_NUMPY
    )
    serialise_seconds = time.perf_counter() - start_serialise

    return features, body, loop_seconds, serialise_seconds


def time_level(world, level, repeats):
    """Time one level's build, reporting the fastest of `repeats` runs."""
    start_units = time.perf_counter()
    units = world.geography.get_units_by_level(level)
    units_seconds = time.perf_counter() - start_units

    best_loop = best_serialise = float('inf')
    for _ in range(repeats):
        features, body, loop_seconds, serialise_seconds = build_level_payload(world, level)
        best_loop = min(best_loop, loop_seconds)
        best_serialise = min(best_serialise, serialise_seconds)

    start_gzip = time.perf_counter()
    gzipped = gzip.compress(body, compresslevel=6)
    gzip_seconds = time.perf_counter() - start_gzip

    return {
        'level': level,
        'units': len(units),
        'features': len(features),
        'units_seconds': units_seconds,
        'loop_seconds': best_loop,
        'serialise_seconds': best_serialise,
        'bytes': len(body),
        'gzip_bytes': len(gzipped),
        'gzip_seconds': gzip_seconds,
    }


def format_report(load_seconds, results):
    megabyte = 1024 * 1024
    lines = [f"world load: {load_seconds:.2f}s", ""]
    header = (
        f"{'level':<16}{'units':>9}{'feats':>9}{'units s':>9}{'loop s':>9}"
        f"{'json s':>9}{'build s':>9}{'MB':>9}{'gzip MB':>9}{'gzip s':>9}"
    )
    lines.append(header)
    lines.append('-' * len(header))
    for result in results:
        build_seconds = (
            result['units_seconds'] + result['loop_seconds'] + result['serialise_seconds']
        )
        lines.append(
            f"{result['level']:<16}{result['units']:>9,}{result['features']:>9,}"
            f"{result['units_seconds']:>9.3f}{result['loop_seconds']:>9.3f}"
            f"{result['serialise_seconds']:>9.3f}{build_seconds:>9.3f}"
            f"{result['bytes'] / megabyte:>9.1f}{result['gzip_bytes'] / megabyte:>9.1f}"
            f"{result['gzip_seconds']:>9.3f}"
        )
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('world_file', help='Path to a world_state .h5 file')
    parser.add_argument('--level', action='append', dest='levels',
                        help='Geography level to time (repeatable; default: all levels)')
    parser.add_argument('--repeats', type=int, default=3,
                        help='Timed runs per level, fastest wins (default: 3)')
    args = parser.parse_args()

    start_load = time.perf_counter()
    world = build_world_store(args.world_file)
    load_seconds = time.perf_counter() - start_load

    if not world.geography:
        parser.error(f"No geography in {args.world_file}")

    levels = args.levels or world.geography.levels
    unknown = [level for level in levels if level not in world.geography.levels]
    if unknown:
        parser.error(f"Unknown level(s) {unknown}; available: {world.geography.levels}")

    results = [time_level(world, level, args.repeats) for level in levels]
    print(format_report(load_seconds, results))


if __name__ == '__main__':
    main()
