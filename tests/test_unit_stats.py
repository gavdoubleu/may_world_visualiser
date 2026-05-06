"""Domain model tests for UnitStats — no Flask, no HDF5."""

from world_map.core.world_data import UnitStats, AGE_LABELS
from world_map.testing import WorldBuilder


def test_unit_stats_construction():
    stats = UnitStats(
        population=10,
        age_distribution={label: 0 for label in AGE_LABELS},
        sex_distribution={'M': 10},
        venue_types={},
    )
    assert stats.population == 10


def test_unit_statistics_populated_after_build():
    world = WorldBuilder().add_unit('Norfolk', level='county').build_world()
    assert 'Norfolk' in world._unit_statistics
    assert isinstance(world._unit_statistics['Norfolk'], UnitStats)


def test_population_count():
    world = WorldBuilder().add_unit('Norfolk', population=42).build_world()
    assert world._unit_statistics['Norfolk'].population == 42


def test_age_distribution():
    world = WorldBuilder().add_unit('Norfolk', population=5).build_world()
    stats = world._unit_statistics['Norfolk']
    assert set(stats.age_distribution.keys()) == set(AGE_LABELS)
    assert stats.people_aged('25-34') == 5   # WorldBuilder default age=30
    assert stats.people_aged('0-15') == 0


def test_parent_aggregates_descendants():
    world = (
        WorldBuilder()
        .add_unit('England', level='country')
        .add_unit('Norfolk', level='county', population=100)
        .build_world()
    )
    england = world.geography.get_unit('England')
    norfolk = world.geography.get_unit('Norfolk')
    norfolk.parent = england
    england.children.append(norfolk)
    world.compute_all_statistics()

    assert world._unit_statistics['England'].population == 100
