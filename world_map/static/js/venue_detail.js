// Venue Detail view — fields + Subset member counts, expandable to paginated members

const venueDetailState = {
    venueId: null,
    expandedSubset: null,
    page: 1,
    perPage: 20,
    childrenExpanded: false,
    childrenPage: 1,
};

async function showVenueDetails(venueId, opts = {}) {
    if (!opts.fromNav) WorldMap.panelNavigator.push({ type: 'venue', venueId });
    venueDetailState.venueId = venueId;
    venueDetailState.expandedSubset = null;
    venueDetailState.page = 1;
    venueDetailState.childrenExpanded = false;
    venueDetailState.childrenPage = 1;
    await renderVenueDetails();
}

async function renderVenueDetails() {
    try {
        const venueId = venueDetailState.venueId;
        const response = await fetch(`/api/geography/venue/${venueId}/detail`);
        const venue = await response.json();

        if (venue.error) {
            console.error('Error loading venue detail:', venue.error);
            return;
        }

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = `
            <h2>${venue.name}</h2>
            <button class="back-button" onclick="WorldMap.goBackPanelView()">
                &larr; Back
            </button>

            <div class="info-grid">
                <div class="info-item">
                    <div class="info-item-label">Type</div>
                    <div class="info-item-value">${venue.type}</div>
                </div>
                ${venue.geo_unit ? `
                <div class="info-item">
                    <div class="info-item-label">Geo Unit</div>
                    <div class="info-item-value">
                        ${venue.geo_unit}
                        <button class="icon-btn" title="Go to geo unit" onclick="WorldMap.goToGeoUnitFromVenue(${venueDetailState.venueId})">
                            <img src="/static/images/to_geo_unit_icon.svg" alt="Go to geo unit">
                        </button>
                    </div>
                </div>` : ''}
                ${venue.coordinates ? `
                <div class="info-item">
                    <div class="info-item-label">Latitude</div>
                    <div class="info-item-value">${venue.coordinates[0].toFixed(4)}</div>
                </div>
                <div class="info-item">
                    <div class="info-item-label">Longitude</div>
                    <div class="info-item-value">${venue.coordinates[1].toFixed(4)}</div>
                </div>` : ''}
            </div>
        `;

        const properties = Object.entries(venue.properties || {});
        if (properties.length > 0) {
            html += `
                <h3>Properties</h3>
                <div class="properties-grid">
                    ${properties.map(([key, value]) => `
                        <div class="property-item">
                            <span class="property-key">${key}:</span>
                            <span class="property-value">${value}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        html += `
            <h3>Sub-venues</h3>
            <button class="venue-type-toggle" onclick="WorldMap.toggleVenueChildren()">
                ${venueDetailState.childrenExpanded ? '&#9660;' : '&#9654;'} Sub-venues
            </button>
            <div id="venue-children-section"></div>
        `;

        html += '<h3>Members</h3><div id="venue-members-section"><em>Loading…</em></div>';

        content.innerHTML = html;
        panel.classList.remove('hidden');

        if (venueDetailState.childrenExpanded) await renderVenueChildren();
        await renderVenueMembers();
    } catch (error) {
        console.error('Error loading venue details:', error);
    }
}

async function renderVenueMembers() {
    const venueId = venueDetailState.venueId;
    const page = venueDetailState.page;
    const response = await fetch(
        `/api/geography/venue/${venueId}/members?page=${page}&per_page=${venueDetailState.perPage}`
    );
    const data = await response.json();

    const section = document.getElementById('venue-members-section');
    if (!section) return;

    if (!data.subsets || data.subsets.length === 0) {
        section.innerHTML = '<p><em>No members</em></p>';
        return;
    }

    let html = '<div class="venue-subset-groups">';

    for (const subset of data.subsets) {
        const isExpanded = venueDetailState.expandedSubset === subset.name;

        html += `
            <div class="venue-type-group">
                <button class="venue-type-toggle" onclick="WorldMap.toggleVenueSubsetGroup('${subset.name}')">
                    ${isExpanded ? '&#9660;' : '&#9654;'} ${subset.name} (${subset.total.toLocaleString()})
                </button>
        `;

        if (isExpanded) {
            html += renderExpandedSubsetMembers(subset);
        }

        html += '</div>';
    }

    html += '</div>';

    section.innerHTML = html;
}

function renderExpandedSubsetMembers(subset) {
    let html = '<div class="venue-list">';

    for (const member of subset.members) {
        html += `
            <div class="venue-item" onclick="WorldMap.showPersonDetails(${member.id})">
                <span class="venue-name">#${member.id} — age ${member.age}, ${member.sex}</span>
            </div>
        `;
    }

    html += '</div>';

    if (subset.total_pages > 1) {
        html += `
            <div class="pagination">
                <button class="pagination-btn" ${subset.page <= 1 ? 'disabled' : ''} onclick="WorldMap.changeVenueMembersPage(${subset.page - 1})">
                    &larr; Prev
                </button>
                <span class="pagination-info">Page ${subset.page} of ${subset.total_pages}</span>
                <button class="pagination-btn" ${subset.page >= subset.total_pages ? 'disabled' : ''} onclick="WorldMap.changeVenueMembersPage(${subset.page + 1})">
                    Next &rarr;
                </button>
            </div>
        `;
    }

    return html;
}

function toggleVenueSubsetGroup(subsetName) {
    venueDetailState.expandedSubset =
        (venueDetailState.expandedSubset === subsetName) ? null : subsetName;
    venueDetailState.page = 1;
    renderVenueMembers();
}

function changeVenueMembersPage(page) {
    venueDetailState.page = page;
    renderVenueMembers();
}

async function renderVenueChildren() {
    const venueId = venueDetailState.venueId;
    const page = venueDetailState.childrenPage;
    const response = await fetch(
        `/api/geography/venue/${venueId}/children?page=${page}&per_page=${venueDetailState.perPage}`
    );
    const data = await response.json();

    const section = document.getElementById('venue-children-section');
    if (!section) return;

    if (data.total_count === 0) {
        section.innerHTML = '<p><em>No sub-venues</em></p>';
        return;
    }

    let html = '<div class="venue-list">';
    for (const venue of data.venues) {
        html += `
            <div class="venue-item" onclick="WorldMap.showVenueDetails(${venue.id})">
                <span class="venue-name">${venue.name}</span>
            </div>
        `;
    }
    html += '</div>';

    if (data.total_pages > 1) {
        html += `
            <div class="pagination">
                <button class="pagination-btn" ${page <= 1 ? 'disabled' : ''} onclick="WorldMap.changeVenueChildrenPage(${page - 1})">
                    &larr; Prev
                </button>
                <span class="pagination-info">Page ${page} of ${data.total_pages}</span>
                <button class="pagination-btn" ${page >= data.total_pages ? 'disabled' : ''} onclick="WorldMap.changeVenueChildrenPage(${page + 1})">
                    Next &rarr;
                </button>
            </div>
        `;
    }

    section.innerHTML = html;
}

function toggleVenueChildren() {
    venueDetailState.childrenExpanded = !venueDetailState.childrenExpanded;
    venueDetailState.childrenPage = 1;
    renderVenueDetails();
}

function changeVenueChildrenPage(page) {
    venueDetailState.childrenPage = page;
    renderVenueChildren();
}

if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, {
        showVenueDetails, toggleVenueSubsetGroup, changeVenueMembersPage,
        toggleVenueChildren, changeVenueChildrenPage,
    });
}
