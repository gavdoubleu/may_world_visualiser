"""Test factory: builds synthetic HDF5 worlds and AppContexts via the shared
world_reader lazy backend (ExplorerWorld/ExplorerLoader).

Writes a small synthetic world_state.h5 and loads it through the real
load_explorer_world/ExplorerLoader path, mirroring the fixture-building patterns
in tests/test_explorer_loader.py (subtree_world_h5) and tests/test_bulk_venues.py
(bulk_venues_h5) — exercises the same backend as production rather than a
duck-typed stand-in.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import h5py
import numpy as np

from world_reader.explorer_world import load_explorer_world
from world_reader.explorer_loader import ExplorerLoader
from world_map.context import AppContext
from world_map.config import AppConfig
from world_map.projection.web_mercator import WebMercatorConfig


class WorldBuilder:
    """Fluent builder for HDF5-backed ExplorerWorld/AppContext in tests."""

    def __init__(self) -> None:
        self._units: list[dict] = []
        self._levels: list[str] = []

    def add_unit(
        self,
        name: str,
        level: str = 'region',
        coordinates: tuple[float, float] = (51.5, -0.1),
        population: int = 0,
        parent: str | None = None,
    ) -> 'WorldBuilder':
        if level not in self._levels:
            self._levels.append(level)
        self._units.append(dict(
            name=name, level=level, coordinates=coordinates,
            population=population, parent=parent,
        ))
        return self

    def _write_hdf5(self, path: Path) -> None:
        dt = h5py.string_dtype()
        name_to_index = {unit['name']: index for index, unit in enumerate(self._units)}

        geo_ids     = np.arange(len(self._units), dtype=np.int32)
        parent_ids  = np.array(
            [name_to_index[unit['parent']] if unit['parent'] else -1 for unit in self._units],
            dtype=np.int32,
        )
        level_codes = np.array([self._levels.index(unit['level']) for unit in self._units],
                               dtype=np.int32)
        names       = np.array([unit['name'].encode() for unit in self._units], dtype=dt)
        latitudes   = np.array([unit['coordinates'][0] for unit in self._units], dtype=np.float64)
        longitudes  = np.array([unit['coordinates'][1] for unit in self._units], dtype=np.float64)
        level_names = np.array([level.encode() for level in self._levels], dtype=dt)

        person_ids: list[int] = []
        ages: list[int] = []
        sexes: list[int] = []
        person_geo_unit_ids: list[int] = []
        next_person_id = 0
        for unit_index, unit in enumerate(self._units):
            for _ in range(unit['population']):
                person_ids.append(next_person_id)
                ages.append(30)
                sexes.append(0)  # male — matches old WorldBuilder's Person(sex='M') default
                person_geo_unit_ids.append(unit_index)
                next_person_id += 1

        with h5py.File(path, 'w') as f:
            f.create_dataset('geography/ids', data=geo_ids)
            f.create_dataset('geography/parent_ids', data=parent_ids)
            f.create_dataset('geography/levels', data=level_codes)
            f.create_dataset('geography/latitudes', data=latitudes)
            f.create_dataset('geography/longitudes', data=longitudes)
            f.create_dataset('metadata/names/geography', data=names)
            f.create_dataset('metadata/registries/geo_levels', data=level_names)

            f.create_dataset('population/ids', data=np.array(person_ids, dtype=np.int32))
            f.create_dataset('population/ages', data=np.array(ages, dtype=np.int32))
            f.create_dataset('population/sexes', data=np.array(sexes, dtype=np.uint8))
            f.create_dataset('population/geo_unit_ids',
                             data=np.array(person_geo_unit_ids, dtype=np.int32))

            f.create_dataset('venues/ids', data=np.array([], dtype=np.int32))
            f.create_dataset('venues/geo_unit_ids', data=np.array([], dtype=np.int32))
            f.create_dataset('venues/types', data=np.array([], dtype=np.uint8))
            f.create_dataset('venues/latitudes', data=np.array([], dtype=np.float32))
            f.create_dataset('venues/longitudes', data=np.array([], dtype=np.float32))
            f.create_dataset('metadata/names/venues', data=np.array([], dtype=dt))
            f.create_dataset('metadata/registries/venue_types', data=np.array([], dtype=dt))
            f.create_dataset('venues/subsets/venue_ids', data=np.array([], dtype=np.int32))
            f.create_dataset('venues/subsets/member_counts', data=np.array([], dtype=np.int32))
            f.create_dataset('metadata/names/subsets', data=np.array([], dtype=dt))

    def build_world(self, compute_activity_stats: bool = False):
        """Write a synthetic HDF5 and load it as an ExplorerWorld.

        Pins the backing temp directory to the returned world so lazy
        ExplorerLoader reads keep working once this builder goes out of scope.
        """
        tmpdir  = tempfile.TemporaryDirectory()
        h5_path = Path(tmpdir.name) / 'world.h5'
        self._write_hdf5(h5_path)

        world = load_explorer_world(str(h5_path), compute_activity_stats=compute_activity_stats)
        world._builder_tmpdir    = tmpdir     # keep alive — deletes the .h5 on GC
        world._builder_hdf5_path = str(h5_path)
        return world

    def build_loader(self, world=None) -> ExplorerLoader:
        """Build an ExplorerLoader wired to a freshly-built (or given) world."""
        world = world if world is not None else self.build_world()
        return ExplorerLoader(
            world._builder_hdf5_path,
            world.person_id_to_idx,
            world.subset_venue_ids,
            world.geography,
            world.subtree_index,
            world.person_geo_unit_ids,
            world.venue_geo_unit_ids,
            world.venue_types_arr,
            world.venue_type_names,
            world.venue_list_position,
            world.person_list_position,
            world.venue_parent_ids,
            world.venue_child_counts,
            world.venue_child_total_members,
            world.children_by_parent_sorted,
            world.children_parent_ids_sorted,
        )

    def build_context(self, **overrides) -> AppContext:
        world  = self.build_world()
        loader = self.build_loader(world)
        defaults: dict = dict(
            world=world,
            explorer_loader=loader,
            projection=WebMercatorConfig(),
            map_config={'background_type': 'osm'},
            app_config=AppConfig.minimal(),
        )
        defaults.update(overrides)
        return AppContext(**defaults)
