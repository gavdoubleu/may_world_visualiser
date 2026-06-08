"""Typed context container for WorldExplorer Flask app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import current_app

from world_reader import RecordReader

_EXPLORER_CTX_KEY = 'EXPLORER_CONTEXT'


@dataclass
class ExplorerContext:
    world: Any  # WorldStore: geography + aggregate stats, lazy people/venues
    record_reader: RecordReader


def get_explorer_context() -> ExplorerContext:
    return current_app.config[_EXPLORER_CTX_KEY]
