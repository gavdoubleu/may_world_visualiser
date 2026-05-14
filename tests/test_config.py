"""Tests for world_map.config.AppConfig."""

import pytest
from pathlib import Path
from world_map.config import AppConfig


def test_app_config_importable():
    assert AppConfig is not None


def test_load_returns_app_config():
    cfg = AppConfig.load(Path('world_map/yaml/config.yaml'))
    assert isinstance(cfg.panel, dict)
    assert isinstance(cfg.theme, dict)
    assert isinstance(cfg.events, dict)
    assert isinstance(cfg.projection_type, str)


def test_panel_config_route(client_for):
    from dataclasses import replace
    from world_map.testing import WorldBuilder
    cfg = replace(AppConfig.minimal(), panel={'geo_unit_panel': {'title_field': 'name'}})
    ctx = WorldBuilder().build_context(app_config=cfg)
    client = client_for(ctx)
    resp = client.get('/api/panel/config')
    assert resp.status_code == 200
    assert resp.get_json()['geo_unit_panel']['title_field'] == 'name'


def test_load_raises_for_missing_theme(tmp_path):
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(
        'theme: no_such_theme\npanel:\n  title: test\nevents:\n  time: {}\n'
    )
    with pytest.raises(FileNotFoundError):
        AppConfig.load(config_path)


def test_load_raises_for_missing_panel(tmp_path):
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('theme: dark_scientific\nevents:\n  time: {}\n')
    with pytest.raises(KeyError, match="panel"):
        AppConfig.load(config_path)


def test_load_raises_for_missing_events(tmp_path):
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('theme: dark_scientific\npanel:\n  title: test\n')
    with pytest.raises(KeyError, match="events"):
        AppConfig.load(config_path)
