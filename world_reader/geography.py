"""Geography tree, per-unit statistics, and the HDF5 geography loader.

App-agnostic: no dependency on world_map or world_explorer.
"""

import logging
import math
from dataclasses import dataclass, field

import numpy as np

from world_reader.convert import convert_numpy_value

logger = logging.getLogger("world_reader.geography")

AGE_LABELS: list[str] = ['0-15', '16-24', '25-34', '35-49', '50-64', '65+']
AGE_BREAKS: list[float] = [0, 16, 25, 35, 50, 65, math.inf]


def age_label(age: int | float) -> str:
    for i in range(len(AGE_LABELS) - 1):
        if age < AGE_BREAKS[i + 1]:
            return AGE_LABELS[i]
    return AGE_LABELS[-1]


@dataclass
class UnitStats:
    population: int
    age_distribution: dict[str, int]
    sex_distribution: dict[str, int]
    venue_types: dict[str, int]
    activity_counts: dict[str, int] = field(default_factory=dict)

    @property
    def venues_count(self) -> int:
        return sum(self.venue_types.values())

    def people_aged(self, label: str) -> int:
        return self.age_distribution.get(label, 0)

    def venues_of_type(self, venue_type: str) -> int:
        return self.venue_types.get(str(venue_type), 0)

    def to_dict(self) -> dict:
        return {
            'population':       self.population,
            'age_distribution': self.age_distribution,
            'sex_distribution': self.sex_distribution,
            'venues_count':     self.venues_count,
            'venue_types':      self.venue_types,
            'activity_counts':  self.activity_counts,
        }


class GeoUnit:
    def __init__(self, unit_id, name, level, coordinates=None, properties=None):
        self.id = unit_id
        self.name = name
        self.level = level
        self.coordinates = coordinates
        self.parent = None
        self.children = []
        self.people = []
        self.venues = []
        self.properties = properties or {}

    def get_people(self):
        all_people = list(self.people)
        for child in self.children:
            all_people.extend(child.get_people())
        return all_people

    def get_descendants(self):
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class GeographyManager:
    def __init__(self, levels=None):
        self.levels = levels or []
        self.units_by_id = {}
        self._units_by_name = {}
        self._units_by_level = {}

    def add_unit(self, unit):
        self.units_by_id[unit.id] = unit
        self._units_by_name[unit.name] = unit
        if unit.level not in self._units_by_level:
            self._units_by_level[unit.level] = {}
        self._units_by_level[unit.level][unit.name] = unit

    def get_unit(self, name):
        return self._units_by_name.get(name)

    def get_units_by_level(self, level):
        return self._units_by_level.get(level, {})


def load_geography(geo_group, geo_names=None, level_registry=None):
    """Reconstruct GeographyManager from HDF5 geography group."""
    ids = geo_group['ids'][:]

    names = geo_names if geo_names is not None else geo_group['names'][:].astype(str)

    if level_registry is not None:
        levels = np.array([level_registry[int(v)] for v in geo_group['levels'][:]])
    else:
        levels = geo_group['levels'][:].astype(str)

    unique_levels = list(dict.fromkeys(str(lvl) for lvl in levels))
    parent_ids    = geo_group['parent_ids'][:]

    latitudes  = None
    longitudes = None
    if 'latitudes' in geo_group and 'longitudes' in geo_group:
        latitudes  = geo_group['latitudes'][:]
        longitudes = geo_group['longitudes'][:]

    properties_by_unit = {}
    if 'properties' in geo_group:
        for prop_name in geo_group['properties'].keys():
            properties_by_unit[prop_name] = geo_group['properties'][prop_name][:]

    geography = GeographyManager(levels=unique_levels)

    units_by_id = {}
    for i, (unit_id, name, level) in enumerate(zip(ids, names, levels)):
        coordinates = None
        if latitudes is not None and not np.isnan(latitudes[i]):
            coordinates = (float(latitudes[i]), float(longitudes[i]))

        properties = {
            prop_name: convert_numpy_value(prop_array[i])
            for prop_name, prop_array in properties_by_unit.items()
        }

        unit = GeoUnit(
            unit_id=int(unit_id),
            name=str(name),
            level=str(level),
            coordinates=coordinates,
            properties=properties,
        )
        units_by_id[int(unit_id)] = unit

    for unit_id, parent_id in zip(ids, parent_ids):
        if int(parent_id) != -1:
            child  = units_by_id[int(unit_id)]
            parent = units_by_id[int(parent_id)]
            child.parent = parent
            parent.children.append(child)

    for unit in units_by_id.values():
        geography.add_unit(unit)

    logger.info(f"  Loaded {len(units_by_id)} geographical units")
    return geography
