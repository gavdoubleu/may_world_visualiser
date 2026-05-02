# Map Bounds for Background Image Alignment

## Format

`--map-bounds "north,east,south,west"` — always in WGS84 decimal degrees.

## Web Mercator (default)

Pass the geographic bounding box of the image in the usual sense:

```
--map-bounds "north_lat,east_lon,south_lat,west_lon"
```

## Non-geographic projection (e.g. UTM)

For a projected raster (e.g. a UTM PNG), `L.imageOverlay` positions the image
using the **geographic coordinates of the NW (top-left) and SE (bottom-right)
pixel corners** — not the SW/NE corners. In a projected coordinate system, lines
of constant projected northing are not lines of constant latitude, so these four
corners have different geographic coordinates.

Compute the correct bounds from the image's pixel extents using pyproj:

```python
from pyproj import Transformer
t = Transformer.from_crs("EPSG:<image_epsg>", "EPSG:4326", always_xy=True)

lon_nw, lat_nw = t.transform(utm_x_min, utm_y_max)   # top-left  pixel corner
lon_se, lat_se = t.transform(utm_x_max, utm_y_min)   # bottom-right pixel corner

print(f'--map-bounds "{lat_nw:.5f},{lon_se:.5f},{lat_se:.5f},{lon_nw:.5f}"')
```

`utm_x_min`, `utm_y_max`, `width`, `height`, and `cell_size` are printed by
`render_terrain.py` at the end of each run.

## Marker projection must match

The projection set in `app_config.yaml` determines how data markers are
rendered. If the background image is in UTM zone 30 (EPSG:32630), set:

```yaml
projection:
  type: utm
  zone: 30
```

Using mismatched projection and image bounds will cause markers to appear offset
from the background.
