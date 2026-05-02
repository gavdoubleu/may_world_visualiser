from __future__ import annotations

from abc import ABC, abstractmethod


class MapProjectionConfig(ABC):
    """
    Provides CRS configuration for the Leaflet frontend.

    This class never transforms coordinates. Flask routes always emit
    WGS84 [lon, lat]; Leaflet's CRS (configured from leaflet_crs_spec)
    handles the display projection internally.
    """

    @abstractmethod
    def leaflet_crs_spec(self) -> dict:
        """
        JSON-serialisable dict describing the Leaflet CRS.

        For web_mercator: {'type': 'builtin', 'name': 'EPSG3857'}
        For utm:          {'type': 'proj4', 'code': 'EPSG:32630', 'proj4': '...'}
        """
        ...

    @property
    @abstractmethod
    def native_epsg(self) -> int:
        """
        EPSG code of the CRS this projection uses for display.
        Background image bounds should be supplied in this CRS for
        pixel-perfect alignment.
        """
        ...

    def seed_from_coordinates(self, lats: list[float], lons: list[float]) -> None:
        """Called once at startup with all geo-unit coordinates. Override for auto-config."""
        pass

    @property
    @abstractmethod
    def name(self) -> str: ...
