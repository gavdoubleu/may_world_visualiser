"""Tests for world_reader.geography: infer_missing_coordinates."""

from tests.support.world_builder import WorldBuilder
from world_reader.geography import infer_missing_coordinates


def test_infers_parent_coordinates_as_mean_of_children():
    world = (
        WorldBuilder()
        .add_unit('Realm', level='country', coordinates=None)
        .add_unit('North', level='region', coordinates=(52.0, 0.0), parent='Realm')
        .add_unit('South', level='region', coordinates=(50.0, 2.0), parent='Realm')
        .build_world()
    )

    infer_missing_coordinates(world.geography)

    realm = world.geography.get_unit('Realm')
    assert realm.coordinates == (51.0, 1.0)


def test_resolves_bottom_up_through_multiple_missing_levels():
    world = (
        WorldBuilder()
        .add_unit('Realm', level='country', coordinates=None)
        .add_unit('North', level='region', coordinates=None, parent='Realm')
        .add_unit('York', level='town', coordinates=(54.0, -1.0), parent='North')
        .add_unit('Leeds', level='town', coordinates=(53.0, -1.5), parent='North')
        .build_world()
    )

    infer_missing_coordinates(world.geography)

    north = world.geography.get_unit('North')
    assert north.coordinates == (53.5, -1.25)
    realm = world.geography.get_unit('Realm')
    assert realm.coordinates == (53.5, -1.25)


def test_leaf_unit_with_no_coordinates_and_no_children_stays_none():
    world = (
        WorldBuilder()
        .add_unit('Realm', level='country', coordinates=(51.0, 0.0))
        .add_unit('Lonely', level='region', coordinates=None, parent='Realm')
        .build_world()
    )

    infer_missing_coordinates(world.geography)

    assert world.geography.get_unit('Lonely').coordinates is None


def test_unit_with_real_coordinates_is_not_overwritten_by_child_mean():
    world = (
        WorldBuilder()
        .add_unit('Realm', level='country', coordinates=(1.0, 1.0))
        .add_unit('North', level='region', coordinates=(52.0, 0.0), parent='Realm')
        .build_world()
    )

    infer_missing_coordinates(world.geography)

    assert world.geography.get_unit('Realm').coordinates == (1.0, 1.0)
