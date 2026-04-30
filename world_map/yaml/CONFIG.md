# YAML Configuration

All yaml files live in `world_map/yaml/`. The app loads them at startup via `create_app()`.

---

## app_config.yaml

Top-level application settings.

```yaml
theme: dark_scientific        # filename (no .yaml) from yaml/themes/

geo_unit_names:
  enabled: true
  csv_path: "data/Geo_unit_names.csv"   # relative to project root
  id_column: "MBD_Temp_ID"
  name_column: "Name"
```

**`theme`** — selects a file from `yaml/themes/`. Two themes ship: `dark_scientific`, `clean_minimal`.

**`geo_unit_names`** — maps internal IDs to human-readable names. Set `enabled: false` to use raw IDs. `csv_path` is relative to the project root.

---

## Map background and events file

These are **CLI arguments**, not yaml settings:

```bash
# Custom image background
python launch_world_map.py --world-file data/world_state.h5 \
    --map-background image \
    --map-image medieval_map.png \
    --map-bounds "56.0,2.0,49.5,-6.0" \
    --map-attribution "Medieval England 1348 AD"

# Events file
python launch_world_map.py --world-file data/world_state.h5 \
    --events-file data/simulation_events.h5

# Static export with events
python export_static.py --world-file data/world_state.h5 \
    --output map.html \
    --events-file data/simulation_events.h5
```

`--map-bounds` format is `"north,east,south,west"`. Omit `--map-background` to use OpenStreetMap (default).

---

## themes/*.yaml

Each theme file sets colors and fonts for the UI.

```yaml
title: "1348 England"
subtitle: null
logo_path: "images/June_logo_white.png"   # relative to world_map/static/; null to omit

colors:
  bg:             '#0f1117'     # page background
  surface:        '#111827'     # panel background
  surface_raised: '#1e293b'     # elevated elements (cards, dropdowns)
  border:         '#1e293b'
  text:           '#F9FAFB'
  text_muted:     '#cbd5e1'
  accent:         '#00d4ff'     # highlight color
  header_bg:      '#0d1117'
  header_text:    '#F9FAFB'
  header_gradient: 'linear-gradient(135deg, #0d1117 0%, #141d2e 100%)'
  header_border:   'rgba(0, 212, 255, 0.25)'
  header_shadow:   '0 1px 20px rgba(0, 212, 255, 0.08)'

fonts:
  display:      'IBM Plex Sans'
  display_file: 'ShareTechMono-Regular.woff2'   # filename in world_map/static/fonts/
  body:         'IBM Plex Sans'
  body_file:    'IBMPlexSans-Regular.woff2'
```

To add a new theme: create `yaml/themes/my_theme.yaml`, then set `theme: my_theme` in `app_config.yaml`. Font files must exist in `world_map/static/fonts/`.

---

## info_panel_config.yaml

Controls what appears in the side panel when clicking a geo unit or venue.

### Geo unit panel

```yaml
geo_unit_panel:
  title_field: "name"

  popup:
    enabled: true
    fields:
      - name: "population"
        label: "Population"
        type: "attribute"
        format: "number"      # adds thousand separators

  detail_sections:
    - name: "age_distribution"
      title: "Age Distribution"
      type: "distribution"
      enabled: true
      source: "age_distribution"
      show_percentage: true

    - name: "venue_breakdown"
      title: "Venue Types"
      type: "breakdown"
      enabled: true
      source: "venue_types"
      sort_by: "count"
      sort_order: "desc"
      max_items: 20
```

**Field types:** `attribute` (direct value), `computed` (derived), `distribution` (bar chart), `breakdown` (count by category), `list` (item list), `properties` (key-value from `.properties` dict).

Set `enabled: false` on any section to hide it without deleting it.

### Marker styles

Controls how geo unit and venue circles are drawn on the map.

```yaml
marker_styles:

  geo_unit:
    size:
      method: "sqrt"                  # 'sqrt', 'log', 'linear'
      characteristic_population: 100  # population where sqrt(pop/char_pop) = 1
      min_radius: 3
      max_radius: 15
      scale: 5

    color:
      method: "threshold"
      thresholds:
        - value: 100
          color: "#FFFFFF"
        - value: null     # null = no upper limit (catch-all)
          color: "#FFE4E1"

    border:
      color: "#808080"
      width: 1
      opacity: 1

    fill_opacity: 0.7

    zoom_scaling:
      enabled: true
      base_zoom: 1          # zoom level where markers are at base size
      scale_exponent: 0.7   # higher = more aggressive scaling
      min_scale: 0.3
      max_scale: 1.0

  venue:
    size:
      radius: 3             # fixed radius
    fill_opacity: 0.8
    colors:
      school:   "#e74c3c"
      hospital: "#3498db"
      default:  "#95a5a6"   # fallback for unlisted types
    zoom_scaling:
      enabled: true
      base_zoom: 6
      scale_exponent: 0.5
      min_scale: 0.3
      max_scale: 3.0
```

---

## event_visualisation.yaml

Controls display of simulation events (infections, deaths, etc.) when an events file is loaded.

### Time settings

```yaml
time:
  aggregation_window: 1.0        # time units per frame (typically days)
  playback_interval_ms: 500      # ms between frames during playback
  rolling_window_days: 1         # days shown at once
```

### Event types

Each key under `event_types` must match an event type name in the HDF5 events file.

```yaml
event_types:
  infections:
    label: "Infections"
    default_visible: true
    icon: "virus"

    marker:
      color: "#FFE4E1"
      border:
        color: "#ffffff"
        width: 2
        opacity: 0.8
      fill_opacity: 0.8
      size_scale: 0.5     # multiplier on base radius for this event type

    # Absolute count thresholds (checked in order; null = catch-all)
    color_thresholds:
      - max_count: 2
        color: "#FFA500"
        label: "Very Low"
      - max_count: null
        color: "#B22222"
        label: "Very High"

    # Alternative: relative scaling (colors rescale to current max)
    use_relative_scaling: false
    gradient:
      low:       "#fee5d9"
      medium:    "#fcae91"
      high:      "#fb6a4a"
      very_high: "#cb181d"
```

Set `use_relative_scaling: true` to use `gradient` instead of `color_thresholds`. To add a new event type, add a new key under `event_types` with the same structure. To disable an existing type without deleting it, comment it out.

### Display mode

```yaml
display:
  default_mode: "choropleth"   # 'choropleth' (color by count) or 'markers' (uniform color, size by count)

  choropleth:
    size:
      method: "sqrt"
      min_radius: 2
      max_radius: 7
      scale: 0.5
    border:
      color: "#333333"
      width: 1
      opacity: 0.8
    fill_opacity: 0.7

  zoom_scaling:
    enabled: true
    base_zoom: 1
    scale_exponent: 0.5
    min_scale: 0.3
    max_scale: 1.5
```

### Aggregation

```yaml
aggregation:
  method: "count"      # 'count' or 'rate' (per N population)
  rate_per: 100000
  cumulative: false    # true = running total from start; false = rolling window
```
