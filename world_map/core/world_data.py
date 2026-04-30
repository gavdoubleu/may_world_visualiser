"""
Standalone data classes for world_map. No may dependencies.
Duck-type compatible with the interface that app.py expects.
"""


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


class Person:
    def __init__(self, person_id, age, sex, geographical_unit=None, properties=None):
        self.id = person_id
        self.age = age
        self.sex = sex
        self.activities = []
        self.activity_map = {}
        self.geographical_unit = geographical_unit
        self.properties = properties or {}


class Subset:
    def __init__(self, name, num_members):
        self.name = name
        self.num_members = num_members
        self.capacity = None


class Venue:
    def __init__(self, venue_id, name, venue_type, geographical_unit=None,
                 coordinates=None, properties=None):
        self.id = venue_id
        self.name = name
        self.type = venue_type
        self.geographical_unit = geographical_unit
        self.coordinates = coordinates
        self.subsets = {}
        self.parent = None
        self.properties = properties or {}


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


class PopulationManager:
    def __init__(self):
        self._people_by_id = {}

    def add_person(self, person):
        self._people_by_id[person.id] = person

    def get_person(self, person_id):
        return self._people_by_id.get(int(person_id))

    def get_statistics(self):
        total = len(self._people_by_id)
        if not total:
            return {'total_people': 0}
        ages = [p.age for p in self._people_by_id.values()]
        sex_dist = {}
        for p in self._people_by_id.values():
            sex_dist[p.sex] = sex_dist.get(p.sex, 0) + 1
        return {
            'total_people': total,
            'age_stats': {
                'mean': round(sum(ages) / total, 2),
                'min': int(min(ages)),
                'max': int(max(ages)),
            },
            'sex_distribution': sex_dist,
        }


class VenueManager:
    def __init__(self):
        self._venues_by_id = {}
        self._venues_by_type = {}

    def add_venue(self, venue):
        self._venues_by_id[venue.id] = venue
        venue_type = str(venue.type)
        if venue_type not in self._venues_by_type:
            self._venues_by_type[venue_type] = []
        self._venues_by_type[venue_type].append(venue)

    def get_all_venues(self):
        return self._venues_by_id

    def get_venue_types(self):
        return list(self._venues_by_type.keys())

    def get_venues_by_type(self, venue_type):
        return self._venues_by_type.get(str(venue_type), [])


class WorldData:
    def __init__(self, geography, population, venues):
        self.geography = geography
        self.population = population
        self.venues = venues
        self.households = None      # not serialised; /api/households returns 404
        self._slim_statistics = None
        self._unit_statistics = None

    def get_statistics(self):
        stats = {}
        if self.population:
            stats.update(self.population.get_statistics())
        if self.geography:
            stats['total_geo_units'] = len(self.geography.units_by_id)
            stats['geography_levels'] = self.geography.levels
        if self.venues:
            stats['total_venues'] = len(self.venues.get_all_venues())
            stats['venue_types'] = self.venues.get_venue_types()
        return stats

    def __str__(self):
        n_units  = len(self.geography.units_by_id) if self.geography else 0
        n_people = len(self.population._people_by_id) if self.population else 0
        n_venues = len(self.venues.get_all_venues()) if self.venues else 0
        return f'<WorldData: {n_units} units, {n_people:,} people, {n_venues:,} venues>'
