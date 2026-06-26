"""CSV-backed reader for calendar events, keyed by (geo_unit_id, venue_type)."""

from __future__ import annotations

import csv
from pathlib import Path


class CalendarEventReader:
    """Loads a calendar_events CSV and provides per-venue event lookups.

    Only rows whose ``venue_type_name`` appears in ``included_venue_types``
    are indexed; all other rows are discarded at load time.  The default
    restricts to ``'fair'`` venues.
    """

    _DEFAULT_INCLUDED = frozenset({'fair'})

    def __init__(self, csv_path: Path,
                 included_venue_types: frozenset[str] = _DEFAULT_INCLUDED):
        self._index: dict[tuple[int, str], list[dict]] = {}
        self._load(csv_path, included_venue_types)

    def _load(self, csv_path: Path,
              included_venue_types: frozenset[str]) -> None:
        rows_by_key: dict[tuple[int, str], list[dict]] = {}
        with open(csv_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                venue_type = row.get('venue_type_name', '').strip()
                if venue_type not in included_venue_types:
                    continue
                try:
                    geo_unit_id = int(row['hosting_geo_unit_id'])
                except (KeyError, ValueError):
                    continue
                key = (geo_unit_id, venue_type)
                rows_by_key.setdefault(key, []).append({
                    'event_name':   row.get('event_name', '').strip(),
                    'date':         row.get('date', '').strip(),
                    'duration_days': row.get('duration_days', '').strip(),
                })
        # Sort each venue's events by date ascending
        for key, events in rows_by_key.items():
            rows_by_key[key] = sorted(events, key=lambda e: e['date'])
        self._index = rows_by_key

    def events_for_venue(self, geo_unit_id: int, venue_type: str) -> list[dict]:
        """Return sorted event dicts for this venue, or [] if none."""
        return self._index.get((geo_unit_id, venue_type), [])
