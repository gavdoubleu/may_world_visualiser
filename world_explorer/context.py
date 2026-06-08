"""Typed context container for WorldExplorer Flask app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from webapp_utilities import make_context_accessor
from world_reader import RecordReader

_EXPLORER_CTX_KEY = 'EXPLORER_CONTEXT'


@dataclass
class ExplorerContext:
    world: Any  # WorldStore: geography + aggregate stats, lazy people/venues
    record_reader: RecordReader
    theme: dict


get_explorer_context = make_context_accessor(_EXPLORER_CTX_KEY)
