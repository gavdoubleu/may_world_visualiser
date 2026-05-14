"""Application configuration loaded from a single config.yaml."""

from __future__ import annotations
import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_BUILTIN_THEMES_DIR = Path(__file__).parent / 'yaml' / 'themes'
_DEFAULT_CONFIG_PATH = Path(__file__).parent / 'yaml' / 'config.yaml'


@dataclass
class AppConfig:
    panel: dict
    theme: dict
    events: dict
    geo_unit_names: dict[str, str] | None
    projection_type: str
    projection_kwargs: dict

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

        theme = _load_theme(cfg.get('theme', 'dark_scientific'), config_path)

        geo_unit_names = _load_geo_unit_names(cfg.get('geo_unit_names', {}), config_path.parent)

        proj_cfg = cfg.get('projection', {})
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


def _load_theme(theme_ref: str, config_path: Path) -> dict:
    """Resolve theme_ref to a YAML file and load it.

    theme_ref is either a built-in name ('dark_scientific') or a path
    relative to config_path's directory ('./my_theme.yaml').
    """
    if theme_ref.endswith('.yaml') or '/' in theme_ref or '\\' in theme_ref:
        theme_path = config_path.parent / theme_ref
    else:
        theme_path = _BUILTIN_THEMES_DIR / f'{theme_ref}.yaml'
    with open(theme_path) as f:
        theme = yaml.safe_load(f) or {}
    logger.info(f"Loaded theme '{theme_ref}'")
    return theme


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
