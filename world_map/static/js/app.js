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
    baseZoom: 6
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
                },
                {
                    enabled: true, type: 'breakdown', title: 'Venue Types',
                    source: 'venue_types', sort_by: 'count', sort_order: 'desc'
                },
                {
                    enabled: true, type: 'list', title: 'Venues',
                    source: 'venue_details', max_items: 50,
                    fields: [{ name: 'name' }, { name: 'type' }]
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
            minZoom: 1, maxZoom: 18, attributionControl: true
        }).setView([centerLat, centerLon], 6);

        const bounds = L.latLngBounds(L.latLng(south, west), L.latLng(north, east));

        state.baseLayer = L.imageOverlay(config.image_url, bounds, {
            attribution: config.attribution || 'Custom Map Image',
            opacity: 0.9, interactive: false
        }).addTo(state.map);

        state.imageBounds = bounds;
        state.map.fitBounds(bounds);
    } else {
        state.map = L.map('map').setView([51.5074, -0.1278], 6);
        state.baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors', maxZoom: 19
        }).addTo(state.map);
    }

    state.baseZoom = WorldMap.setupGeoUnitZoomListener(
        state.map,
        state.panelConfig,
        () => state.layers.geography
    ) || state.baseZoom;
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

        displayWorldStats(stats);
    } catch (error) {
        console.error('Error loading world statistics:', error);
    }
}

function displayWorldStats(stats) {
    const statsEl = document.getElementById('world-stats');
    let html = '';

    if (stats.population) {
        html += `
            <div class="stat-item">
                <span class="stat-label">Total Population</span>
                <span class="stat-value">${stats.population.total_population.toLocaleString()}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Mean Age</span>
                <span class="stat-value">${stats.population.mean_age.toFixed(1)}</span>
            </div>
        `;
    }

    if (stats.geography) {
        html += `
            <div class="stat-item">
                <span class="stat-label">Geographic Units</span>
                <span class="stat-value">${stats.geography.total_units.toLocaleString()}</span>
            </div>
        `;
    }

    if (stats.venues) {
        html += `
            <div class="stat-item">
                <span class="stat-label">Venues</span>
                <span class="stat-value">${stats.venues.total_venues.toLocaleString()}</span>
            </div>
        `;
    }

    if (stats.households) {
        html += `
            <div class="stat-item">
                <span class="stat-label">Households</span>
                <span class="stat-value">${stats.households.total_households.toLocaleString()}</span>
            </div>
        `;
    }

    statsEl.innerHTML = html;
}

// =============================================================================
// GEOGRAPHY LEVELS
// =============================================================================

async function loadGeographyLevels() {
    try {
        const response = await fetch('/api/geography/levels');
        const data = await response.json();

        const container = document.getElementById('geography-levels');
        container.innerHTML = data.levels.map((level, index) => `
            <button class="level-button ${index === 0 ? 'active' : ''}"
                    data-level="${level}"
                    onclick="WorldMap.selectGeographyLevel('${level}')">
                ${level} (${data.units_per_level[level].toLocaleString()} units)
            </button>
        `).join('');

        if (data.levels.length > 0) {
            selectGeographyLevel(data.levels[0]);
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
        }

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

        state.layers.geography = L.geoJSON(geojson, {
            pointToLayer: (feature, latlng) => {
                const props = feature.properties;
                const population = props.population || 0;
                const baseRadius = WorldMap.calculateMarkerRadius(population, styleConfig.size);
                const scaledRadius = baseRadius * zoomScale;
                const fillColor = WorldMap.getPopulationColor(population, styleConfig.color);
                const borderConfig = styleConfig.border || {};

                return L.circleMarker(latlng, {
                    radius: scaledRadius,
                    baseRadius: baseRadius,
                    fillColor: fillColor,
                    color: borderConfig.color || '#fff',
                    weight: borderConfig.width || 1,
                    opacity: borderConfig.opacity || 1,
                    fillOpacity: styleConfig.fill_opacity || 0.7
                });
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties;
                layer.bindPopup(WorldMap.createGeoUnitPopup(props, state.panelConfig));
                layer.on('click', () => WorldMap.showUnitDetails(props.name));
            }
        }).addTo(state.map);

        // Build name → integer id lookup for event correlation
        state.geoUnitNameToId = {};
        geojson.features.forEach(f => {
            if (f.properties.id !== undefined) {
                state.geoUnitNameToId[f.properties.name] = f.properties.id;
            }
        });

        state.map.fitBounds(state.layers.geography.getBounds());

    } catch (error) {
        console.error('Error loading geography level:', error);
    }
}

// =============================================================================
// DETAIL PANEL
// =============================================================================

async function showUnitDetails(unitName) {
    try {
        const response = await fetch(`/api/geography/unit/${encodeURIComponent(unitName)}`);
        const unit = await response.json();

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = WorldMap.buildDetailPanel(unit, 'geo_unit_panel', state.panelConfig?.geo_unit_panel);

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

// Expose functions needed by onclick handlers and other modules
// (people.js attaches showUnitPeople / showPersonDetails itself)
Object.assign(window.WorldMap, { selectGeographyLevel, showUnitDetails });
