"""Application configuration loaded from a single config.yaml."""

from __future__ import annotations
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from webapp_utilities.theme_css import resolve_theme

logger = logging.getLogger(__name__)

_BUILTIN_THEMES_DIR = Path(__file__).parent / 'yaml' / 'themes'
_DEFAULT_CONFIG_PATH = Path(__file__).parent / 'yaml' / 'config.yaml'


@dataclass
class AppConfig:
    panel: dict
    theme: dict
    events: dict
    geo_unit_names: dict[str, str] | None
    geo_unit_coordinates: dict
    projection_type: str
    projection_kwargs: dict
    map: dict
    title: str | None

    @classmethod
    def load(cls, config_path: Path) -> 'AppConfig':
        """Load all config from a single config.yaml. Raises on missing required sections."""
        with open(config_path) as f:
            cfg: dict = yaml.safe_load(f) or {}

        panel = cfg.get('panel')
        if panel is None:
            raise KeyError(f"'panel' section missing from {config_path}")

        events = cfg.get('events')
        if events is None:
            raise KeyError(f"'events' section missing from {config_path}")

        theme_ref = cfg.get('theme', 'dark_scientific')
        theme = resolve_theme(theme_ref, _BUILTIN_THEMES_DIR, config_path.parent)
        logger.info(f"Loaded theme '{theme_ref}'")

        geo_unit_names = _load_geo_unit_names(cfg.get('geo_unit_names', {}), config_path.parent)
        geo_unit_coordinates = cfg.get('geo_unit_coordinates', {'enabled': True})

        proj_cfg = cfg.get('projection', {})
        projection_type = proj_cfg.get('type', 'web_mercator')
        projection_kwargs = {k: v for k, v in proj_cfg.items() if k not in ('type', 'bounds_epsg')}

        map_settings = _load_map_settings(cfg.get('map', {}), config_path.parent)
        title = cfg.get('title')

        return cls(
            panel=panel,
            theme=theme,
            events=events,
            geo_unit_names=geo_unit_names,
            geo_unit_coordinates=geo_unit_coordinates,
            projection_type=projection_type,
            projection_kwargs=projection_kwargs,
            map=map_settings,
            title=title,
        )

    @classmethod
    def minimal(cls) -> 'AppConfig':
        """Minimal instance for tests — no file I/O."""
        return cls(
            panel={},
            theme={},
            events={},
            geo_unit_names=None,
            geo_unit_coordinates={'enabled': True},
            projection_type='web_mercator',
            projection_kwargs={},
            map={'background': 'osm', 'image': None, 'bounds': None, 'attribution': None},
            title=None,
        )


def _load_map_settings(map_cfg: dict, config_dir: Path) -> dict:
    """Read the 'map' config block. Local image paths are resolved relative to config_dir."""
    image = map_cfg.get('image')
    if image and not image.startswith(('http://', 'https://')):
        image_path = Path(image)
        if not image_path.is_absolute():
            image_path = config_dir / image_path
        image = str(image_path)

    return {
        'background': map_cfg.get('background', 'osm'),
        'image': image,
        'bounds': map_cfg.get('bounds'),
        'attribution': map_cfg.get('attribution'),
    }


def _load_geo_unit_names(geo_cfg: dict, config_dir: Path) -> dict[str, str] | None:
    if not geo_cfg.get('enabled', False):
        return None

    csv_path = Path(geo_cfg.get('csv_path', ''))
    if not csv_path.is_absolute():
        csv_path = config_dir / csv_path

    id_col = geo_cfg.get('id_column', 'MBD_Temp_ID')
    name_col = geo_cfg.get('name_column', 'Name')

    mapping: dict[str, str] = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            tempid = row.get(id_col, '').strip()
            name = row.get(name_col, '').strip()
            if tempid:
                mapping[tempid] = name
    logger.info(f"Loaded {len(mapping)} geo_unit display names from {csv_path}")
    return mapping
