"""Test factory for building WorldData and AppContext without HDF5 files."""

from __future__ import annotations

from world_map.core.world_data import (
    GeoUnit,
    GeographyManager,
    Person,
    PopulationManager,
    VenueManager,
    WorldData,
)
from world_map.context import AppContext
from world_map.config import AppConfig
from world_map.projection.web_mercator import WebMercatorConfig


class WorldBuilder:
    """Fluent builder for WorldData and AppContext in tests."""

    def __init__(self) -> None:
        self._geo = GeographyManager(levels=[])
        self._pop = PopulationManager()
        self._venues = VenueManager()
        self._next_id = 1

    def add_unit(
        self,
        name: str,
        level: str = 'region',
        coordinates: tuple[float, float] = (51.5, -0.1),
        population: int = 0,
    ) -> 'WorldBuilder':
        unit = GeoUnit(self._next_id, name, level, coordinates)
        self._next_id += 1
        if level not in self._geo.levels:
            self._geo.levels.append(level)
        self._geo.add_unit(unit)
        for _ in range(population):
            person = Person(self._next_id, age=30, sex='M', geographical_unit=unit)
            self._next_id += 1
            unit.people.append(person)
            self._pop.add_person(person)
        return self

    def build_world(self) -> WorldData:
        world = WorldData(self._geo, self._pop, self._venues)
        world.compute_all_statistics()
        return world

    def build_context(self, **overrides) -> AppContext:
        world = self.build_world()
        defaults: dict = dict(
            world=world,
            venue_index={},
            projection=WebMercatorConfig(),
            map_config={'background_type': 'osm'},
            app_config=AppConfig.minimal(),
        )
        defaults.update(overrides)
        return AppContext(**defaults)
