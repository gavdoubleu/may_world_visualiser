from __future__ import annotations

import statistics

from world_map.projection.base import MapProjectionConfig
from world_map.projection.registry import register


def _zone_from_lon(lon: float) -> int:
    return int((lon + 180) / 6) % 60 + 1


@register('utm')
class UTMConfig(MapProjectionConfig):
    """
    Configures Leaflet to display in a UTM zone via Proj4Leaflet.

    Zone selection: explicit `zone` kwarg takes precedence; otherwise
    seed_from_coordinates() detects the zone from the median longitude.
    """

    def __init__(self, zone: int | None = None, **_ignored):
        try:
            from pyproj import Transformer, CRS
            self._Transformer = Transformer
            self._CRS = CRS
        except ImportError:
            raise ImportError(
                "UTM projection requires pyproj. Install with: pip install pyproj"
            )
        self._explicit_zone = zone
        self._zone: int | None = zone
        self._epsg: int | None = None
        if zone is not None:
            # Zone known at construction — build with northern hemisphere as default;
            # seed_from_coordinates() will correct hemisphere if lats are provided.
            self._epsg = 32600 + zone

    def seed_from_coordinates(self, lats: list[float], lons: list[float]) -> None:
        if not lats:
            return
        if self._explicit_zone is None:
            self._zone = _zone_from_lon(statistics.median(lons))
        median_lat = statistics.median(lats)
        hemisphere_offset = 100 if median_lat < 0 else 0
        self._epsg = 32600 + self._zone + hemisphere_offset

    @property
    def native_epsg(self) -> int:
        if self._epsg is None:
            raise RuntimeError(
                "native_epsg unavailable until seed_from_coordinates() is called."
            )
        return self._epsg

    @property
    def name(self) -> str:
        if self._zone is not None:
            hemi = 'S' if (self._epsg or 0) >= 32700 else 'N'
            return f'UTM zone {self._zone}{hemi}'
        return 'UTM (zone not yet determined)'

    def leaflet_crs_spec(self) -> dict:
        if self._epsg is None:
            raise RuntimeError(
                "leaflet_crs_spec unavailable until seed_from_coordinates() is called."
            )
        crs = self._CRS.from_epsg(self._epsg)
        # Standard Web Mercator resolutions scaled to metres.
        # Proj4Leaflet requires explicit resolutions for metric CRS; without them
        # fitBounds calculates zoom levels as if coordinates were in degrees.
        resolutions = [156543.03392 / (2 ** z) for z in range(22)]
        return {
            'type': 'proj4',
            'code': f'EPSG:{self._epsg}',
            'proj4': crs.to_proj4(),
            'resolutions': resolutions,
            'origin': [0, 0],
        }
