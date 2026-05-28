"""Typed context container for WorldExplorer Flask app."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from world_map.core.world_data import WorldData
from world_explorer.explorer_loader import ExplorerLoader

_EXPLORER_CTX_KEY = 'EXPLORER_CONTEXT'


@dataclass
class ExplorerContext:
    world: WorldData
    venue_index: dict
    explorer_loader: ExplorerLoader


def get_explorer_context() -> ExplorerContext:
    return current_app.config[_EXPLORER_CTX_KEY]
