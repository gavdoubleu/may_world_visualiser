"""Application configuration loaded from YAML. Single source of truth."""

from __future__ import annotations
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_WORLD_MAP_DIR = Path(__file__).parent


@dataclass
class AppConfig:
    panel: dict
    theme: dict
    events: dict
    geo_unit_names: dict[str, str] | None
    projection_type: str
    projection_kwargs: dict

    @classmethod
    def load(cls, world_map_dir: Path | None = None) -> 'AppConfig':
        """Load all config from yaml/. Raises FileNotFoundError for any missing file."""
        if world_map_dir is None:
            world_map_dir = _WORLD_MAP_DIR
        yaml_dir = world_map_dir / 'yaml'

        # app_config.yaml is the only optional file — missing means empty config
        try:
            with open(yaml_dir / 'app_config.yaml') as f:
                app_cfg: dict = yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning("app_config.yaml not found, using defaults")
            app_cfg = {}

        # Panel config — required
        with open(yaml_dir / 'info_panel_config.yaml') as f:
            panel = yaml.safe_load(f) or {}
        logger.info("Loaded panel config")

        # Theme — required; name comes from app_config
        theme_name = app_cfg.get('theme', 'dark_scientific')
        with open(yaml_dir / 'themes' / f'{theme_name}.yaml') as f:
            theme = yaml.safe_load(f) or {}
        logger.info(f"Loaded theme '{theme_name}'")

        # Event visualisation config — required
        with open(yaml_dir / 'event_visualisation.yaml') as f:
            events = yaml.safe_load(f) or {}
        logger.info("Loaded event visualisation config")

        # Geo unit names — optional feature; CSV required when enabled
        geo_unit_names = _load_geo_unit_names(app_cfg, world_map_dir)

        # Projection
        proj_cfg = app_cfg.get('projection', {})
        projection_type = proj_cfg.get('type', 'web_mercator')
        projection_kwargs = {k: v for k, v in proj_cfg.items() if k not in ('type', 'bounds_epsg')}

        return cls(
            panel=panel,
            theme=theme,
            events=events,
            geo_unit_names=geo_unit_names,
            projection_type=projection_type,
            projection_kwargs=projection_kwargs,
        )

    @classmethod
    def minimal(cls) -> 'AppConfig':
        """Minimal instance for tests — no file I/O."""
        return cls(
            panel={},
            theme={},
            events={},
            geo_unit_names=None,
            projection_type='web_mercator',
            projection_kwargs={},
        )


def _load_geo_unit_names(app_cfg: dict, world_map_dir: Path) -> dict[str, str] | None:
    cfg = app_cfg.get('geo_unit_names', {})
    if not cfg.get('enabled', False):
        return None

    csv_path = Path(cfg.get('csv_path', ''))
    if not csv_path.is_absolute():
        csv_path = world_map_dir.parent / csv_path

    id_col = cfg.get('id_column', 'MBD_Temp_ID')
    name_col = cfg.get('name_column', 'Name')

    # Raises FileNotFoundError if CSV missing when feature is enabled
    mapping: dict[str, str] = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            tempid = row.get(id_col, '').strip()
            name = row.get(name_col, '').strip()
            if tempid:
                mapping[tempid] = name
    logger.info(f"Loaded {len(mapping)} geo_unit display names from {csv_path}")
    return mapping
