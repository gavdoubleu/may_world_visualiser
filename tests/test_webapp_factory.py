"""Tests for the shared webapp_utilities.make_app factory skeleton."""

from world_map.testing import WorldBuilder


def _build_world():
    return WorldBuilder().add_unit('Norfolk', population=3).build_world()


def test_world_map_app_builds_via_make_app_and_responds():
    from world_map.app import create_app
    world = _build_world()
    client = create_app(world, world._builder_hdf5_path).test_client()

    assert client.get('/').status_code == 200
    assert client.get('/api/geography/levels').status_code == 200
    assert client.get('/no-such-route').status_code == 404


def test_world_explorer_app_builds_via_make_app_and_responds():
    from world_explorer.app import create_app
    world = _build_world()
    client = create_app(world, world._builder_hdf5_path).test_client()

    assert client.get('/').status_code == 200
    assert client.get('/no-such-route').status_code == 404


def test_theme_css_routes_render_root_block_for_both_apps():
    world = _build_world()

    from world_map.app import create_app as create_map_app
    response = create_map_app(world, world._builder_hdf5_path).test_client().get('/api/theme.css')
    assert response.content_type == 'text/css; charset=utf-8'
    assert ':root {' in response.get_data(as_text=True)

    from world_explorer.app import create_app as create_explorer_app
    response = create_explorer_app(world, world._builder_hdf5_path).test_client().get('/theme.css')
    assert response.content_type == 'text/css; charset=utf-8'
    assert ':root {' in response.get_data(as_text=True)


def test_explorer_theme_arg_selects_builtin_theme():
    from world_explorer.app import create_app
    world = _build_world()

    client = create_app(world, world._builder_hdf5_path, theme='clean_minimal').test_client()
    css = client.get('/theme.css').get_data(as_text=True)
    assert ':root {' in css
