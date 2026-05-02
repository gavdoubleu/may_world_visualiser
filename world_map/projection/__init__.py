"""Coordinate projection package. Provides CRS configuration for the Leaflet frontend."""

from world_map.projection.registry import build, register
from world_map.projection.base import MapProjectionConfig

import world_map.projection.web_mercator  # noqa: F401 — triggers @register
import world_map.projection.utm           # noqa: F401 — triggers @register

__all__ = ['build', 'register', 'MapProjectionConfig']
