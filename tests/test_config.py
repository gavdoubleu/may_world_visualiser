"""Tests for world_map.config.AppConfig."""

import pytest
from pathlib import Path
from world_map.config import AppConfig


def test_app_config_importable():
    assert AppConfig is not None


def test_load_returns_app_config():
    cfg = AppConfig.load(Path('world_map'))
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
    yaml_dir = tmp_path / 'yaml'
    yaml_dir.mkdir()
    themes_dir = yaml_dir / 'themes'
    themes_dir.mkdir()
    (yaml_dir / 'app_config.yaml').write_text('theme: no_such_theme\n')
    (yaml_dir / 'info_panel_config.yaml').write_text('{}')
    (yaml_dir / 'event_visualisation.yaml').write_text('{}')
    with pytest.raises(FileNotFoundError):
        AppConfig.load(tmp_path)
