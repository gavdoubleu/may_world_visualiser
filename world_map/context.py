"""Typed application context replacing magic-string current_app.config access."""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from world_map.events.event_loader import EventLoader

from world_map.core.world_data import WorldData, Venue
from world_map.projection.base import MapProjectionConfig
from world_map.config import AppConfig

_CTX_KEY = 'APP_CONTEXT'


@dataclass
class AppContext:
    world: WorldData
    venue_index: dict[int, Venue]
    projection: MapProjectionConfig
    map_config: dict
    app_config: AppConfig
    event_loader: Optional[EventLoader] = None

    @property
    def geo_unit_names(self) -> dict[str, str] | None:
        return self.app_config.geo_unit_names

    @property
    def geo_unit_names_enabled(self) -> bool:
        return self.app_config.geo_unit_names is not None


def get_app_context() -> AppContext:
    from flask import current_app
    return current_app.config[_CTX_KEY]
