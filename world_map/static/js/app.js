// World Map — orchestrator
// Depends on (load order): utils.js, panel_builders.js, geography.js, people.js

window.WorldMap = window.WorldMap || {};

// =============================================================================
// GLOBAL STATE
// =============================================================================

const state = {
    map: null,
    baseLayer: null,
    imageBounds: null,
    layers: {
        geography: null,
    },
    selectedLevel: null,
    showPopulation: true,
    mapConfig: null,
    panelConfig: null,
    geoUnitNameToId: {},
    baseZoom: 6,
    hasFitInitialGeographyBounds: false,
    // Marker pool: every geo_unit marker for the selected level, built once per
    // level load. state.layers.geography holds only those currently in view.
    geoUnitMarkers: [],
    geoUnitBounds: null,
    geoUnitLatitudes: null,
    geoUnitLongitudes: null,
    geoUnitOnMap: null,
    allGeoUnitMarkersOnMap: false,
    geoUnitPopup: null
};

// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        loadMapConfiguration(),
        loadPanelConfiguration()
    ]);

    initializeMap();
    loadWorldStatistics();
    loadGeographyLevels();
    setupEventListeners();
});

async function loadMapConfiguration() {
    try {
        const response = await fetch('/api/map/config');
        state.mapConfig = await response.json();
    } catch (error) {
        console.error('Error loading map configuration:', error);
        state.mapConfig = { background_type: 'osm', image_url: null, bounds: null, attribution: null };
    }
}

async function loadPanelConfiguration() {
    try {
        const response = await fetch('/api/panel/config');
        state.panelConfig = await response.json();
    } catch (error) {
        console.error('Error loading panel configuration:', error);
        state.panelConfig = getDefaultPanelConfig();
    }
}

function getDefaultPanelConfig() {
    return {
        geo_unit_panel: {
            title_field: 'name',
            popup: { enabled: true },
            detail_sections: [
                {
                    enabled: true, type: 'grid', title: null,
                    fields: [
                        { label: 'Level',          name: 'level' },
                        { label: 'Population',     name: 'population',    format: 'number' },
                        { label: 'Venues',         name: 'venues_count',  format: 'number' },
                        { label: 'Children Units', name: 'children_count' }
                    ]
                },
                {
                    enabled: true, type: 'distribution', title: 'Age Distribution',
                    source: 'age_distribution', denominator_field: 'population', show_percentage: true
                },
                {
                    enabled: true, type: 'distribution', title: 'Sex Distribution',
                    source: 'sex_distribution', denominator_field: 'population', show_percentage: true
                }
            ]
        },
        marker_styles: {
            geo_unit: {
                size: { method: 'sqrt', min_radius: 5, max_radius: 15, scale: 0.5 },
                border: { color: '#808080', width: 1, opacity: 1 },
                fill_opacity: 0.7,
                zoom_scaling: { enabled: true, base_zoom: 6, scale_exponent: 0.5, min_scale: 0.3, max_scale: 3.0 }
            }
        }
    };
}

// =============================================================================
// MAP INITIALIZATION
// =============================================================================

function _showProjectionWarning(message) {
    console.error('PROJECTION WARNING: ' + message);
    const div = document.createElement('div');
    div.style.cssText = (
        'position:fixed;top:0;left:0;right:0;z-index:9999;' +
        'background:#b00;color:#fff;padding:10px 16px;font-weight:bold;' +
        'font-family:monospace;text-align:center;'
    );
    div.textContent = '⚠ PROJECTION WARNING: ' + message;
    document.body.appendChild(div);
}

function buildLeafletCRS(crsDef, warnIfFallback) {
    if (!crsDef || crsDef.type === 'builtin') {
        return L.CRS[(crsDef && crsDef.name) || 'EPSG3857'] || L.CRS.EPSG3857;
    }
    if (crsDef.type === 'proj4') {
        if (typeof proj4 === 'undefined' || typeof L.Proj === 'undefined') {
            var msg = 'proj4.js / Proj4Leaflet not loaded. ' +
                'Falling back to Web Mercator (EPSG:3857). ' +
                'Markers and background image may be misaligned.';
            if (warnIfFallback) {
                _showProjectionWarning(msg);
            } else {
                console.warn('PROJECTION: ' + msg);
            }
            return L.CRS.EPSG3857;
        }
        proj4.defs(crsDef.code, crsDef.proj4);
        var crsOptions = {};
        if (crsDef.resolutions) { crsOptions.resolutions = crsDef.resolutions; }
        if (crsDef.origin)      { crsOptions.origin      = crsDef.origin; }
        return new L.Proj.CRS(crsDef.code, crsDef.proj4, crsOptions);
    }
    return L.CRS.EPSG3857;
}

function initializeMap() {
    const config = state.mapConfig;

    if (config.background_type === 'image' && config.image_url && config.bounds) {
        const [[south, west], [north, east]] = config.bounds;
        const centerLat = (south + north) / 2;
        const centerLon = (west + east) / 2;

        state.map = L.map('map', {
            crs: buildLeafletCRS(config.crs, true),
            minZoom: 1, maxZoom: 18, attributionControl: true,
            preferCanvas: true
        }).setView([centerLat, centerLon], 6);

        const bounds = L.latLngBounds(L.latLng(south, west), L.latLng(north, east));

        state.baseLayer = L.imageOverlay(config.image_url, bounds, {
            attribution: config.attribution || 'Custom Map Image',
            opacity: 0.9, interactive: false
        }).addTo(state.map);

        state.imageBounds = bounds;
        state.map.fitBounds(bounds);
    } else {
        state.map = L.map('map', { preferCanvas: true }).setView([51.5074, -0.1278], 6);
        state.baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors', maxZoom: 19
        }).addTo(state.map);
    }

    state.baseZoom = WorldMap.setupGeoUnitZoomListener(
        state.map,
        state.panelConfig,
        () => state.layers.geography
    ) || state.baseZoom;

    // Fires after zoomend on a zoom, so newly-visible markers are added with
    // the scale factor the rescale walk has just settled on.
    state.map.on('moveend', updateGeoUnitViewport);
}

// =============================================================================
// EVENT LISTENERS
// =============================================================================

function setupEventListeners() {
    document.getElementById('close-panel').addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('info-panel').classList.add('hidden');
        if (state.map) state.map.closePopup();
    });

    document.getElementById('show-population')?.addEventListener('change', (e) => {
        state.showPopulation = e.target.checked;
        if (state.selectedLevel) loadGeographyLevel(state.selectedLevel);
    });
}

// =============================================================================
// STATISTICS
// =============================================================================

async function loadWorldStatistics() {
    try {
        const response = await fetch('/api/world/statistics');
        const stats = await response.json();

        const summaryEl = document.getElementById('stats-summary');
        if (stats.population && stats.geography) {
            summaryEl.innerHTML = `
                📍 ${stats.geography.total_units.toLocaleString()} units |
                👥 ${stats.population.total_population.toLocaleString()} people
            `;
        }

        if (state.panelConfig?.sidebar_statistics?.enabled) {
            renderSidebarStatistics(stats);
        }
    } catch (error) {
        console.error('Error loading world statistics:', error);
    }
}

function renderSidebarStatistics(stats) {
    const totalPeople = stats.total_people;
    const ageStats    = stats.age_stats;
    const venueCounts = stats.venue_type_counts;
    if (totalPeople === undefined && !ageStats && !venueCounts) return;

    let html = '';
    if (totalPeople !== undefined) {
        html += `
            <div class="stat-item">
                <span class="stat-label">People</span>
                <span class="stat-value">${totalPeople.toLocaleString()}</span>
            </div>
        `;
    }
    if (ageStats) {
        html += `
            <div class="stat-item">
                <span class="stat-label">Mean age</span>
                <span class="stat-value">${ageStats.mean.toFixed(1)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Median age</span>
                <span class="stat-value">${ageStats.median.toFixed(1)}</span>
            </div>
        `;
    }
    if (venueCounts && Object.keys(venueCounts).length) {
        const sortedTypes = Object.entries(venueCounts).sort((a, b) => b[1] - a[1]);
        html += '<ul class="venue-type-list">';
        for (const [typeName, count] of sortedTypes) {
            html += `
                <li class="stat-item">
                    <span class="stat-label">${typeName}</span>
                    <span class="stat-value">${count.toLocaleString()}</span>
                </li>
            `;
        }
        html += '</ul>';
    }
    if (!html) return;

    let section = document.getElementById('sidebar-statistics');
    if (!section) {
        section = document.createElement('div');
        section.id = 'sidebar-statistics';
        section.className = 'sidebar-section';
        section.innerHTML = '<h3>Statistics</h3><div id="sidebar-statistics-content"></div>';
        document.getElementById('sidebar').appendChild(section);
    }
    document.getElementById('sidebar-statistics-content').innerHTML = html;
}

// =============================================================================
// GEOGRAPHY LEVELS
// =============================================================================

async function loadGeographyLevels() {
    try {
        const response = await fetch('/api/geography/levels');
        const data = await response.json();

        const defaultLevel = WorldMap.chooseDefaultGeographyLevel(data.levels, data.units_per_level);

        const container = document.getElementById('geography-levels');
        container.innerHTML = data.levels.map((level) => `
            <button class="level-button ${level === defaultLevel ? 'active' : ''}"
                    data-level="${level}"
                    onclick="WorldMap.selectGeographyLevel('${level}')">
                ${level} (${data.units_per_level[level].toLocaleString()} units)
            </button>
        `).join('');

        if (defaultLevel) {
            selectGeographyLevel(defaultLevel);
        }
    } catch (error) {
        console.error('Error loading geography levels:', error);
    }
}

async function selectGeographyLevel(level) {
    state.selectedLevel = level;

    document.querySelectorAll('.level-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.level === level);
    });

    await loadGeographyLevel(level);
}

async function loadGeographyLevel(level) {
    try {
        if (state.layers.geography) {
            state.map.removeLayer(state.layers.geography);
            state.layers.geography = null;
        }
        // The shared popup belongs to the map, not to a marker, so dropping the
        // layer no longer closes it — a stale unit name would outlive its level.
        if (state.geoUnitPopup && state.map.hasLayer(state.geoUnitPopup)) {
            state.map.closePopup(state.geoUnitPopup);
        }
        state.geoUnitMarkers = [];
        state.geoUnitBounds = null;
        state.geoUnitLatitudes = null;
        state.geoUnitLongitudes = null;
        state.geoUnitOnMap = null;
        state.allGeoUnitMarkersOnMap = false;

        if (!state.showPopulation) return;

        const response = await fetch(`/api/geography/${level}`);
        const geojson = await response.json();

        if (geojson.features.length === 0) {
            console.warn('No features returned - check if coordinates exist in HDF5');
            return;
        }

        const styleConfig = state.panelConfig?.marker_styles?.geo_unit || {};
        const zoomScale = WorldMap._getZoomScaleFactor
            ? WorldMap._getZoomScaleFactor(state.map, state.baseZoom)
            : 1;
        const borderConfig = styleConfig.border || {};

        // Coordinates are mirrored into flat arrays so the viewport scan can run
        // as plain numeric comparisons. Asking each marker for its LatLng and
        // handing that to bounds.contains() measured ~450 ms per map move at
        // 235k units — the scan, not the drawing, was the cost of panning.
        const unitCount = geojson.features.length;
        state.geoUnitLatitudes = new Float64Array(unitCount);
        state.geoUnitLongitudes = new Float64Array(unitCount);
        state.geoUnitOnMap = new Uint8Array(unitCount);

        const markerCoordinates = [];
        state.geoUnitMarkers = geojson.features.map((feature, index) => {
            const props = feature.properties;
            const [longitude, latitude] = feature.geometry.coordinates;
            const latlng = L.latLng(latitude, longitude);
            markerCoordinates.push(latlng);
            state.geoUnitLatitudes[index] = latitude;
            state.geoUnitLongitudes[index] = longitude;

            const population = props.population || 0;
            const baseRadius = WorldMap.calculateMarkerRadius(population, styleConfig.size);

            const marker = L.circleMarker(latlng, {
                radius: baseRadius * zoomScale,
                baseRadius: baseRadius,
                fillColor: WorldMap.getPopulationColor(population, styleConfig.color),
                color: borderConfig.color || '#fff',
                weight: borderConfig.width || 1,
                opacity: borderConfig.opacity || 1,
                fillOpacity: styleConfig.fill_opacity || 0.7
            });

            marker.on('click', () => {
                openGeoUnitPopup(latlng, props.name);
                WorldMap.showUnitDetails(props.name);
            });

            return marker;
        });

        state.geoUnitBounds = L.latLngBounds(markerCoordinates);
        state.allGeoUnitMarkersOnMap = false;
        state.layers.geography = L.layerGroup().addTo(state.map);

        // Build name → integer id lookup for event correlation
        state.geoUnitNameToId = {};
        geojson.features.forEach(f => {
            if (f.properties.id !== undefined) {
                state.geoUnitNameToId[f.properties.name] = f.properties.id;
            }
        });

        // Only frame the map to the geography once, on initial load — refitting
        // on every level switch snaps to a tight zoom when a level has few
        // (or one) units, since a degenerate/small bounding box has no real
        // extent to fit.
        if (!state.hasFitInitialGeographyBounds) {
            state.map.fitBounds(state.geoUnitBounds);
            state.hasFitInitialGeographyBounds = true;
        }

        updateGeoUnitViewport();

    } catch (error) {
        console.error('Error loading geography level:', error);
    }
}

// Draw only the markers currently in view. The pool is built once per level
// load; this adds and removes the markers that cross the viewport edge, so
// panning and zooming never rebuilds it.
//
// When the viewport already contains every unit there is nothing to cull, so
// the per-marker walk is skipped entirely and the whole level is drawn — the
// wide view then costs exactly what it did before culling existed. That the
// widest view stays the slowest is accepted: thinning or hiding units at low
// zoom was considered and rejected.
function updateGeoUnitViewport() {
    const layer = state.layers.geography;
    if (!layer || state.geoUnitMarkers.length === 0) return;

    const viewportBounds = state.map.getBounds();
    const markers = state.geoUnitMarkers;
    const onMap = state.geoUnitOnMap;
    const zoomScale = WorldMap._getZoomScaleFactor(state.map, state.baseZoom);

    // Markers entering the viewport missed the zoomend rescale, which only
    // walks what is drawn, so apply the current scale on the way in.
    const addMarker = (index) => {
        const marker = markers[index];
        marker.setRadius(marker.options.baseRadius * zoomScale);
        layer.addLayer(marker);
        onMap[index] = 1;
    };

    if (viewportBounds.contains(state.geoUnitBounds)) {
        if (state.allGeoUnitMarkersOnMap) return;
        for (let index = 0; index < markers.length; index++) {
            if (!onMap[index]) addMarker(index);
        }
        state.allGeoUnitMarkersOnMap = true;
        return;
    }

    state.allGeoUnitMarkersOnMap = false;

    // Compared as bare numbers rather than via bounds.contains(). No dateline
    // handling: a world spanning the antimeridian would need the longitude
    // test splitting in two.
    const south = viewportBounds.getSouth();
    const north = viewportBounds.getNorth();
    const west = viewportBounds.getWest();
    const east = viewportBounds.getEast();
    const latitudes = state.geoUnitLatitudes;
    const longitudes = state.geoUnitLongitudes;

    for (let index = 0; index < markers.length; index++) {
        const latitude = latitudes[index];
        const longitude = longitudes[index];
        const isInView = latitude >= south && latitude <= north &&
                         longitude >= west && longitude <= east;

        if (isInView) {
            if (!onMap[index]) addMarker(index);
        } else if (onMap[index]) {
            layer.removeLayer(markers[index]);
            onMap[index] = 0;
        }
    }
}

// One popup reused for every geo_unit, rather than one bound per marker: at
// ~235k units the bound-popup objects alone were a measurable share of load.
// Content is just the name — the info panel carries the statistics.
function openGeoUnitPopup(latlng, unitName) {
    if (!state.geoUnitPopup) {
        // autoPan would shift the map on open, firing moveend and re-running
        // the cull for a marker the user can already see.
        state.geoUnitPopup = L.popup({ autoPan: false });
    }

    state.geoUnitPopup
        .setLatLng(latlng)
        .setContent(`<div class="popup-title">${unitName}</div>`);
    state.map.openPopup(state.geoUnitPopup);
}

// =============================================================================
// DETAIL PANEL
// =============================================================================

async function showUnitDetails(unitName, opts = {}) {
    try {
        if (!opts.fromNav) WorldMap.panelNavigator.reset({ type: 'unit', unitName });

        const response = await fetch(`/api/geography/unit/${encodeURIComponent(unitName)}`);
        const unit = await response.json();

        if (opts.flyTo && unit.coordinates && state.map) {
            state.map.flyTo(unit.coordinates, state.map.getZoom());
        }

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = WorldMap.buildDetailPanel(unit, 'geo_unit_panel', state.panelConfig?.geo_unit_panel);

        // Venues/People are lazy-fetched from live-only routes — the static
        // export's fetch interceptor only serves the fixed pre-baked endpoint
        // set, so these buttons would dead-end there. window.STATIC_WORLD_DATA
        // is set only by export_static.py's exported bundle.
        if (typeof window.STATIC_WORLD_DATA === 'undefined') {
            html += `
                <button class="section-button" onclick="WorldMap.showUnitVenues('${unitName}')">
                    View Venues &rarr;
                </button>
                <button class="section-button" onclick="WorldMap.showUnitPeople('${unitName}')">
                    View People &rarr;
                </button>
            `;
        }

        if (typeof window.WorldMap?.getEventStatsHtmlForUnit === 'function') {
            const geoUnitId = state.geoUnitNameToId[unitName] ?? unit.id;
            if (geoUnitId !== undefined) {
                html += await WorldMap.getEventStatsHtmlForUnit(geoUnitId);
            }
        }

        content.innerHTML = html;
        panel.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading unit details:', error);
    }
}

// Re-renders whichever view is current on the PanelNavigator stack — the one
// dispatch point all "back" buttons call, so cross-navigation (e.g. Person ->
// Venue -> back) always returns to the real predecessor, not a fixed ancestor.
function renderPanelView(view) {
    switch (view.type) {
        case 'unit':   return showUnitDetails(view.unitName, { fromNav: true });
        case 'venues': return WorldMap.showUnitVenues(view.unitName, { fromNav: true });
        case 'people': return WorldMap.showUnitPeople(view.unitName, { fromNav: true });
        case 'person': return WorldMap.showPersonDetails(view.personId, { fromNav: true });
        case 'venue':  return WorldMap.showVenueDetails(view.venueId, { fromNav: true });
        default:
            console.warn(`Unknown panel view type: ${view.type}`);
    }
}

function goBackPanelView() {
    return renderPanelView(WorldMap.panelNavigator.pop());
}

// Expose functions needed by onclick handlers and other modules
// (people.js attaches showUnitPeople / showPersonDetails itself)
Object.assign(window.WorldMap, { selectGeographyLevel, showUnitDetails, renderPanelView, goBackPanelView });
