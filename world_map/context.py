"""Typed application context replacing magic-string current_app.config access."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from world_map.events.event_aggregator import EventAggregator

from webapp_utilities import make_context_accessor
from world_reader import WorldStore, RecordReader
from world_map.projection.base import MapProjectionConfig
from world_map.config import AppConfig

_CTX_KEY = 'APP_CONTEXT'


@dataclass
class AppContext:
    world: WorldStore
    record_reader: RecordReader
    projection: MapProjectionConfig
    map_config: dict
    app_config: AppConfig
    event_loader: Optional['EventAggregator'] = None

    # Serialised /api/geography/<level> response bodies, keyed by level name.
    # Built lazily on first request, never invalidated: one Flask process
    # serves one read-only world file for its whole life. `init=False` keeps
    # `dataclasses.replace` from sharing one cache across contexts backed by
    # different worlds.
    geography_geojson_cache: dict[str, bytes] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    @property
    def geo_unit_names(self) -> dict[str, str] | None:
        return self.app_config.geo_unit_names

    @property
    def geo_unit_names_enabled(self) -> bool:
        return self.app_config.geo_unit_names is not None


get_app_context = make_context_accessor(_CTX_KEY)
