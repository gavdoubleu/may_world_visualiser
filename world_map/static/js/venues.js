// Venues section — grouped by VenueType, paginated per group, lazy-fetched

const venuesState = {
    currentUnit: null,
    expandedType: null,
    expandedPage: 1,
    perPage: 20,
};

async function showUnitVenues(unitName, opts = {}) {
    if (!opts.fromNav) WorldMap.panelNavigator.push({ type: 'venues', unitName });
    venuesState.currentUnit = unitName;
    venuesState.expandedType = null;
    venuesState.expandedPage = 1;
    await renderUnitVenues();
}

async function renderUnitVenues() {
    try {
        const unitName = venuesState.currentUnit;
        const unitResponse = await fetch(`/api/geography/unit/${encodeURIComponent(unitName)}`);
        const unit = await unitResponse.json();
        const venueTypes = unit.venue_types || {};

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = `
            <h2>Venues in ${unitName}</h2>
            <button class="back-button" onclick="WorldMap.goBackPanelView()">
                &larr; Back to Unit Details
            </button>
            <div class="venue-type-groups">
        `;

        const types = Object.keys(venueTypes);
        if (types.length === 0) {
            html += '<p><em>No venues</em></p>';
        }

        for (const type of types) {
            const count = venueTypes[type];
            const isExpanded = venuesState.expandedType === type;

            html += `
                <div class="venue-type-group">
                    <button class="venue-type-toggle" onclick="WorldMap.toggleVenueTypeGroup('${type}')">
                        ${isExpanded ? '&#9660;' : '&#9654;'} ${type} (${count.toLocaleString()})
                    </button>
            `;

            if (isExpanded) {
                html += await renderExpandedVenueType(unitName, type);
            }

            html += '</div>';
        }

        html += '</div>';

        content.innerHTML = html;
        panel.classList.remove('hidden');
    } catch (error) {
        console.error('Error loading unit venues:', error);
    }
}

async function renderExpandedVenueType(unitName, type) {
    const page = venuesState.expandedPage;
    const response = await fetch(
        `/api/geography/unit/${encodeURIComponent(unitName)}/venues?type=${encodeURIComponent(type)}&page=${page}&per_page=${venuesState.perPage}`
    );
    const data = await response.json();

    let html = '<div class="venue-list">';

    for (const venue of data.venues) {
        html += `
            <div class="venue-item" onclick="WorldMap.showVenueDetails(${venue.id})">
                <span class="venue-name">${venue.name}</span>
                ${venue.child_count > 0 ? `<span class="venue-child-count">${venue.child_count} sub-venues</span>` : ''}
            </div>
        `;
    }

    html += '</div>';

    if (data.total_pages > 1) {
        html += `
            <div class="pagination">
                <button class="pagination-btn" ${page <= 1 ? 'disabled' : ''} onclick="WorldMap.changeVenueTypePage(${page - 1})">
                    &larr; Prev
                </button>
                <span class="pagination-info">Page ${page} of ${data.total_pages}</span>
                <button class="pagination-btn" ${page >= data.total_pages ? 'disabled' : ''} onclick="WorldMap.changeVenueTypePage(${page + 1})">
                    Next &rarr;
                </button>
            </div>
        `;
    }

    return html;
}

function toggleVenueTypeGroup(type) {
    venuesState.expandedType = (venuesState.expandedType === type) ? null : type;
    venuesState.expandedPage = 1;
    renderUnitVenues();
}

function changeVenueTypePage(page) {
    venuesState.expandedPage = page;
    renderUnitVenues();
}

if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, {
        showUnitVenues, toggleVenueTypeGroup, changeVenueTypePage,
    });
}
