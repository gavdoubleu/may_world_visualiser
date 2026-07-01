"""Geography tree, per-unit statistics, and the HDF5 geography loader.

App-agnostic: no dependency on world_map or world_explorer.
"""

import logging
import math
from dataclasses import dataclass, field

import h5py
import numpy as np

from world_reader.convert import convert_numpy_value

logger = logging.getLogger("world_reader.geography")

AGE_LABELS: list[str] = ['0-15', '16-24', '25-34', '35-49', '50-64', '65+']
AGE_BREAKS: list[float] = [0, 16, 25, 35, 50, 65, math.inf]


def age_label(age: int | float) -> str:
    """Map an age to its AGE_LABELS bucket (e.g. 16 -> '16-24').

    Args:
        age: A person's age in years.

    Returns:
        The matching label from `AGE_LABELS`.
    """
    for i in range(len(AGE_LABELS) - 1):
        if age < AGE_BREAKS[i + 1]:
            return AGE_LABELS[i]
    return AGE_LABELS[-1]


@dataclass
class UnitStats:
    """Pre-computed, hierarchy-aggregated statistics for one GeoUnit.

    Attributes:
        population: Total resident population of the unit's subtree.
        age_distribution: Counts keyed by `AGE_LABELS` bucket.
        sex_distribution: Counts keyed by sex label (e.g. 'male').
        venue_types: Venue counts keyed by VenueType name.
        activity_counts: Counts keyed by activity name (empty unless
            activity stats were requested at load time).
    """

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
    """A node in the geographical hierarchy.

    Attributes:
        id: Logical geo-unit ID.
        name: Display name.
        level: Hierarchy level name (e.g. 'country', 'region', 'area').
        coordinates: (lat, lon) tuple, or None if the unit has none.
        parent: Parent GeoUnit, or None for a root.
        children: Direct child GeoUnits.
        people: Always empty — Person objects are not materialised here;
            see `WorldStore`/`RecordReader` for lazy population access.
        venues: Always empty — Venue objects are not materialised here.
        properties: Arbitrary unit properties from the HDF5 geography group.
    """

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

    def get_descendants(self) -> list['GeoUnit']:
        """All descendant GeoUnits (children, grandchildren, ...), depth-first."""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants


class GeographyManager:
    """Holds the GeoUnit hierarchy and indices for lookup by name/id/level.

    Attributes:
        levels: Distinct level names, in first-seen order.
        units_by_id: All units, keyed by id.
    """

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

    def get_unit_by_id(self, unit_id: int):
        return self.units_by_id.get(unit_id)

    def get_units_by_level(self, level):
        return self._units_by_level.get(level, {})

    def search_units_by_name(self, query: str) -> list[dict]:
        """Find units whose name matches `query` exactly (case-insensitive).

        Args:
            query: Search string, compared case-insensitively after stripping.

        Returns:
            A list of `{id, name, level, parent_name}` dicts, one per match.
        """
        lower = query.strip().lower()
        results = []
        for unit in self.units_by_id.values():
            if unit.name.lower() == lower:
                results.append({
                    'id':          unit.id,
                    'name':        unit.name,
                    'level':       unit.level,
                    'parent_name': unit.parent.name if unit.parent else None,
                })
        return results

    def geo_unit_coords(self) -> dict[int, tuple[float, float]]:
        """{unit_id: (lat, lon)} for every unit carrying coordinates.

        Single source of truth for "all units with coordinates" — shared by
        WorldMap projection seeding and event geo-aggregation. Flat O(units)
        pass over units_by_id (replaces the per-level nested iteration idiom).
        """
        return {
            unit.id: unit.coordinates
            for unit in self.units_by_id.values()
            if unit.coordinates
        }


def infer_missing_coordinates(geography: 'GeographyManager') -> int:
    """Fill in GeoUnit.coordinates for units missing them, as the arithmetic
    mean of each unit's children's coordinates (resolved bottom-up, so a
    parent can use children whose own coordinates were just inferred).

    Args:
        geography: The GeographyManager to mutate in place.

    Returns:
        Count of units whose coordinates were newly inferred.
    """
    inferred_count = 0

    def resolve(unit: GeoUnit) -> tuple[float, float] | None:
        nonlocal inferred_count
        if unit.coordinates is not None:
            return unit.coordinates

        child_coordinates = [
            coordinates for child in unit.children
            if (coordinates := resolve(child)) is not None
        ]
        if not child_coordinates:
            return None

        mean_lat = sum(lat for lat, _ in child_coordinates) / len(child_coordinates)
        mean_lon = sum(lon for _, lon in child_coordinates) / len(child_coordinates)
        unit.coordinates = (mean_lat, mean_lon)
        inferred_count += 1
        return unit.coordinates

    for unit in geography.units_by_id.values():
        if unit.parent is None:
            resolve(unit)

    logger.info(f"Inferred coordinates for {inferred_count} geo units missing them")
    return inferred_count


def load_geography(
    geo_group: h5py.Group,
    geo_names: np.ndarray | None = None,
    level_registry: np.ndarray | None = None,
) -> GeographyManager:
    """Build a GeographyManager from an HDF5 `geography` group.

    Args:
        geo_group: The open `geography` HDF5 group.
        geo_names: Pre-decoded unit names, or None to read `geo_group['names']`.
        level_registry: Array mapping level codes to level name strings, or
            None if `geo_group['levels']` already stores level names directly.

    Returns:
        A GeographyManager with the full GeoUnit tree (parent/children links
        and coordinates/properties where present) populated.
    """
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
