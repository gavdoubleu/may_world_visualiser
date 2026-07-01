// Geography layer — GeoUnit markers, zoom scaling, level selection

function calculateMarkerRadius(population, sizeConfig) {
    if (!sizeConfig) {
        return Math.max(5, Math.min(15, Math.sqrt(population) / 2));
    }

    const method = sizeConfig.method || 'sqrt';
    const minRadius = sizeConfig.min_radius || 5;
    const maxRadius = sizeConfig.max_radius || 15;
    // Support both 'scale' (new) and 'scale_factor' (legacy)
    const scaleFactor = sizeConfig.scale || sizeConfig.scale_factor || 0.5;
    const characteristicPopulation = sizeConfig.characteristic_population || 1;

    let rawRadius;
    switch (method) {
        case 'sqrt':
            rawRadius = Math.sqrt(population / characteristicPopulation) * scaleFactor;
            break;
        case 'log':
            rawRadius = Math.log10(population + 1) * scaleFactor * 3;
            break;
        case 'linear':
            rawRadius = population * scaleFactor / 100;
            break;
        default:
            rawRadius = Math.sqrt(population / characteristicPopulation) * scaleFactor;
    }

    return Math.max(minRadius, Math.min(maxRadius, rawRadius));
}

function getPopulationColor(population, colorConfig) {
    if (!colorConfig || !colorConfig.thresholds) {
        return population > 10000 ? '#800026' :
               population > 5000  ? '#BD0026' :
               population > 2000  ? '#E31A1C' :
               population > 1000  ? '#FC4E2A' :
               population > 500   ? '#FD8D3C' :
               population > 200   ? '#FEB24C' :
               population > 100   ? '#FED976' :
                                    '#FFEDA0';
    }

    const thresholds = colorConfig.thresholds;
    for (let i = thresholds.length - 1; i >= 0; i--) {
        const threshold = thresholds[i];
        if (threshold.value === null || population > threshold.value) {
            return threshold.color;
        }
    }

    return thresholds[0]?.color || '#FFEDA0';
}

function createGeoUnitPopup(props, panelConfig) {
    const popupConfig = panelConfig?.geo_unit_panel?.popup;

    if (!popupConfig || !popupConfig.enabled) {
        return `
            <div class="popup-title">${props.name}</div>
            <div class="popup-info"><strong>Level:</strong> ${props.level}</div>
            <div class="popup-info"><strong>Population:</strong> ${props.population.toLocaleString()}</div>
            <div class="popup-info"><strong>Venues:</strong> ${props.venues_count}</div>
        `;
    }

    let html = '';
    const fields = popupConfig.fields || [];

    for (const field of fields) {
        const value = _getFieldValue(props, field.name);
        const formattedValue = _formatValue(value, field.format);
        if (field.name === 'name') {
            html += `<div class="popup-title">${formattedValue}</div>`;
        } else {
            html += `<div class="popup-info"><strong>${field.label}:</strong> ${formattedValue}</div>`;
        }
    }

    return html;
}

// Zoom scaling

let _zoomConfig = null;   // cached at setup time

function setupGeoUnitZoomListener(map, panelConfig, getLayerFn) {
    const zoomConfig = panelConfig?.marker_styles?.geo_unit?.zoom_scaling || {};
    if (zoomConfig.enabled === false) return null;

    _zoomConfig = zoomConfig;
    const baseZoom = zoomConfig.base_zoom || map.getZoom() || 6;

    map.on('zoomend', () => {
        const layer = getLayerFn();
        if (!layer) return;
        const scaleFactor = _getZoomScaleFactor(map, baseZoom);
        layer.eachLayer((marker) => {
            if (marker.options && marker.options.baseRadius) {
                marker.setRadius(marker.options.baseRadius * scaleFactor);
            }
        });
    });

    return baseZoom;
}

function _getZoomScaleFactor(map, baseZoom) {
    if (!_zoomConfig || _zoomConfig.enabled === false) return 1;

    const currentZoom = map.getZoom();
    const scaleExponent = _zoomConfig.scale_exponent || 0.5;
    const minScale = _zoomConfig.min_scale || 0.3;
    const maxScale = _zoomConfig.max_scale || 3.0;
    const rawScale = Math.pow(2, (currentZoom - baseZoom) * scaleExponent);

    return Math.max(minScale, Math.min(maxScale, rawScale));
}

// Thin wrappers so geography.js can call utils/panel_builders without import
function _getFieldValue(obj, path) {
    if (typeof window !== 'undefined') return window.WorldMap.getFieldValue(obj, path);
    return require('./utils').getFieldValue(obj, path);
}

function _formatValue(value, format) {
    if (typeof window !== 'undefined') return window.WorldMap.formatValue(value, format);
    return require('./panel_builders').formatValue(value, format);
}

if (typeof module !== 'undefined') {
    module.exports = { calculateMarkerRadius, getPopulationColor, createGeoUnitPopup };
}
if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, { calculateMarkerRadius, getPopulationColor, createGeoUnitPopup,
        setupGeoUnitZoomListener, _getZoomScaleFactor });
}
