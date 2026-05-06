"""Typed application context replacing magic-string current_app.config access."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from world_map.events.event_loader import EventLoader

from world_map.core.world_data import WorldData, Venue
from world_map.projection.base import MapProjectionConfig

_CTX_KEY = 'APP_CONTEXT'


@dataclass
class AppContext:
    world: WorldData
    venue_index: dict[int, Venue]
    projection: MapProjectionConfig
    map_config: dict
    panel_config: dict
    theme_config: dict
    event_config: dict
    event_loader: Optional[EventLoader] = None
    geo_unit_names: Optional[dict[str, str]] = None

    @property
    def geo_unit_names_enabled(self) -> bool:
        return self.geo_unit_names is not None


def get_app_context() -> AppContext:
    from flask import current_app
    return current_app.config[_CTX_KEY]
