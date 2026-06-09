// Panel HTML builder functions — pure data-in / HTML-out, no DOM or Leaflet deps

function formatValue(value, format) {
    if (value === undefined || value === null) return '-';

    switch (format) {
        case 'number':
            return typeof value === 'number' ? value.toLocaleString() : value;
        case 'percentage':
            return typeof value === 'number' ? `${value.toFixed(1)}%` : value;
        case 'decimal':
            return typeof value === 'number' ? value.toFixed(2) : value;
        default:
            if (typeof value === 'number') {
                return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
            }
            return value;
    }
}

function buildDetailPanel(data, panelType, panelConfig) {
    if (!panelConfig) {
        return `<h2>${data.name || ''}</h2>`;
    }

    let html = '';

    if (data.display_name) {
        html += `<h2 class="unit-display-name">${data.display_name}</h2>`;
        html += `<p class="unit-tempid">${data.name}</p>`;
    } else if (data.display_name_enabled) {
        html += `<h2>${data.name}</h2>`;
        html += `<p class="unit-tempid unit-tempid--missing">[no name]</p>`;
    } else {
        const titleField = panelConfig.title_field || 'name';
        html += `<h2>${getFieldValue(data, titleField)}</h2>`;
    }

    for (const section of (panelConfig.detail_sections || [])) {
        if (!section.enabled) continue;
        html += buildPanelSection(section, data);
    }

    return html;
}

function buildPanelSection(section, data) {
    let html = '';
    if (section.title) html += `<h3>${section.title}</h3>`;

    switch (section.type) {
        case 'grid':         html += buildGridSection(section, data); break;
        case 'distribution': html += buildDistributionSection(section, data); break;
        case 'breakdown':    html += buildBreakdownSection(section, data); break;
        case 'list':         html += buildListSection(section, data); break;
        case 'properties':   html += buildPropertiesSection(section, data); break;
        default:
            console.warn(`Unknown section type: ${section.type}`);
    }

    return html;
}

function buildGridSection(section, data) {
    let html = '<div class="info-grid">';

    for (const field of (section.fields || [])) {
        const value = getFieldValue(data, field.source || field.name);
        const formattedValue = formatValue(value, field.format);
        html += `
            <div class="info-item">
                <div class="info-item-label">${field.label}</div>
                <div class="info-item-value">${formattedValue}</div>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function buildDistributionSection(section, data) {
    const distribution = getFieldValue(data, section.source);
    if (!distribution || typeof distribution !== 'object') return '';

    let denominator;
    if (section.denominator_field) {
        denominator = getFieldValue(data, section.denominator_field) || 0;
    } else {
        denominator = Object.values(distribution).reduce((a, b) => a + b, 0);
    }
    if (denominator === 0) return '';

    let entries = Object.entries(distribution);
    if (section.sort_by === 'count') {
        entries = entries.slice().sort((a, b) => b[1] - a[1]);
    }

    let html = '<div class="bar-chart">';

    for (const [group, count] of entries) {
        const percentage = (count / denominator * 100).toFixed(1);
        const valueText = section.show_percentage
            ? `${count.toLocaleString()} (${percentage}%)`
            : count.toLocaleString();

        html += `
            <div class="bar-item">
                <div class="bar-label">${group}</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="bar-value">${valueText}</div>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function buildBreakdownSection(section, data) {
    const breakdown = getFieldValue(data, section.source);

    if (!breakdown || typeof breakdown !== 'object' || Object.keys(breakdown).length === 0) {
        return '<p><em>No data available</em></p>';
    }

    let entries = Object.entries(breakdown);
    if (section.sort_by === 'count') {
        entries.sort((a, b) => section.sort_order === 'desc' ? b[1] - a[1] : a[1] - b[1]);
    } else if (section.sort_by === 'name') {
        entries.sort((a, b) => section.sort_order === 'desc' ? b[0].localeCompare(a[0]) : a[0].localeCompare(b[0]));
    }

    if (section.max_items) {
        entries = entries.slice(0, section.max_items);
    }

    const maxValue = entries.reduce((m, [, v]) => v > m ? v : m, 0);

    let html = '<div class="bar-chart">';

    for (const [type, count] of entries) {
        const width = (count / maxValue * 100).toFixed(1);
        html += `
            <div class="bar-item">
                <div class="bar-label">${type}</div>
                <div class="bar-wrapper">
                    <div class="bar-fill" style="width: ${width}%"></div>
                </div>
                <div class="bar-value">${count.toLocaleString()}</div>
            </div>
        `;
    }

    html += '</div>';
    return html;
}

function buildListSection(section, data) {
    let items = getFieldValue(data, section.source);

    if (!items || !Array.isArray(items) || items.length === 0) {
        return '<p><em>No items</em></p>';
    }

    const originalLength = items.length;
    if (section.max_items) items = items.slice(0, section.max_items);

    const fields = section.fields || [];
    let html = '<div class="list-section">';

    for (const item of items) {
        const itemText = fields.map(f => {
            const value = getFieldValue(item, f.name);
            return value !== undefined ? value : '';
        }).filter(v => v).join(' - ');
        html += `<div class="list-item">${itemText}</div>`;
    }

    if (originalLength > items.length) {
        html += `<div class="list-item list-more">... and ${originalLength - items.length} more</div>`;
    }

    html += '</div>';
    return html;
}

function buildPropertiesSection(section, data) {
    const props = data.properties;
    if (!props || Object.keys(props).length === 0) return '';

    const exclude = section.exclude || [];
    const filtered = Object.fromEntries(
        Object.entries(props).filter(([k]) => !exclude.includes(k))
    );

    if (Object.keys(filtered).length === 0) return '';

    return `
        <pre class="props-pre">
${JSON.stringify(filtered, null, 2)}
        </pre>
    `;
}

// getFieldValue is defined in utils.js; access via module.exports in Node,
// or window.WorldMap.getFieldValue in the browser.
function getFieldValue(obj, path) {
    if (!path) return undefined;
    const parts = path.split('.');
    let value = obj;
    for (const part of parts) {
        if (value === null || value === undefined) return undefined;
        value = value[part];
    }
    return value;
}

if (typeof module !== 'undefined') {
    module.exports = {
        formatValue,
        buildDetailPanel,
        buildPanelSection,
        buildGridSection,
        buildDistributionSection,
        buildBreakdownSection,
        buildListSection,
        buildPropertiesSection,
    };
}
if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, {
        formatValue,
        buildDetailPanel,
        buildPanelSection,
        buildGridSection,
        buildDistributionSection,
        buildBreakdownSection,
        buildListSection,
        buildPropertiesSection,
    });
}
