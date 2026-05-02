from world_map.projection.base import MapProjectionConfig
from world_map.projection.registry import register


@register('web_mercator')
class WebMercatorConfig(MapProjectionConfig):
    """Default passthrough — Leaflet renders WGS84 GeoJSON via EPSG:3857."""

    def leaflet_crs_spec(self) -> dict:
        return {'type': 'builtin', 'name': 'EPSG3857'}

    @property
    def native_epsg(self) -> int:
        return 4326

    @property
    def name(self) -> str:
        return 'Web Mercator'
