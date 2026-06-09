// People list and person detail panel

const peopleState = {
    currentUnit: null,
    currentPage: 1,
    perPage: 50,
    totalCount: 0,
    totalPages: 0
};

async function showUnitPeople(unitName, page = 1) {
    try {
        peopleState.currentUnit = unitName;
        peopleState.currentPage = page;

        const response = await fetch(
            `/api/geography/unit/${encodeURIComponent(unitName)}/people?page=${page}&per_page=${peopleState.perPage}`
        );
        const data = await response.json();

        if (data.error) {
            console.error('Error loading people:', data.error);
            return;
        }

        peopleState.totalCount = data.total_count;
        peopleState.totalPages = data.total_pages;

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = `
            <h2>People in ${unitName}</h2>
            <p class="people-count">${data.total_count.toLocaleString()} people total</p>

            <button class="back-button" onclick="WorldMap.showUnitDetails('${unitName}')">
                &larr; Back to Unit Details
            </button>

            <div class="people-list">
                <table class="people-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Age</th>
                            <th>Sex</th>
                            <th>Primary Activity</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        for (const person of data.people) {
            const primaryActivity = person.primary_activity
                ? `${person.primary_activity.type}: ${person.primary_activity.venue_name}`
                : '-';

            html += `
                <tr class="person-row" onclick="WorldMap.showPersonDetails(${person.id})">
                    <td>${person.id}</td>
                    <td>${person.age}</td>
                    <td>${person.sex}</td>
                    <td>${primaryActivity}</td>
                    <td><span class="view-link">View &rarr;</span></td>
                </tr>
            `;
        }

        html += `
                    </tbody>
                </table>
            </div>
        `;

        if (data.total_pages > 1) {
            html += `
                <div class="pagination">
                    <button class="pagination-btn" ${page <= 1 ? 'disabled' : ''} onclick="WorldMap.showUnitPeople('${unitName}', ${page - 1})">
                        &larr; Prev
                    </button>
                    <span class="pagination-info">Page ${page} of ${data.total_pages}</span>
                    <button class="pagination-btn" ${page >= data.total_pages ? 'disabled' : ''} onclick="WorldMap.showUnitPeople('${unitName}', ${page + 1})">
                        Next &rarr;
                    </button>
                </div>
            `;
        }

        content.innerHTML = html;
        panel.classList.remove('hidden');

    } catch (error) {
        console.error('Error loading people list:', error);
    }
}

async function showPersonDetails(personId) {
    try {
        const response = await fetch(`/api/population/person/${personId}`);
        const person = await response.json();

        if (person.error) {
            console.error('Error loading person:', person.error);
            return;
        }

        const panel = document.getElementById('info-panel');
        const content = document.getElementById('info-content');

        let html = `
            <h2>Person #${person.id}</h2>

            <button class="back-button" onclick="WorldMap.showUnitPeople('${peopleState.currentUnit}', ${peopleState.currentPage})">
                &larr; Back to People List
            </button>

            <div class="info-grid">
                <div class="info-item">
                    <div class="info-item-label">Age</div>
                    <div class="info-item-value">${person.age}</div>
                </div>
                <div class="info-item">
                    <div class="info-item-label">Sex</div>
                    <div class="info-item-value">${person.sex}</div>
                </div>
            </div>
        `;

        if (person.geographical_unit) {
            html += `
                <h3>Location</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-item-label">Area</div>
                        <div class="info-item-value">${person.geographical_unit.name}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-item-label">Level</div>
                        <div class="info-item-value">${person.geographical_unit.level}</div>
                    </div>
                </div>
            `;
        }

        if (person.activities && person.activities.length > 0) {
            html += `
                <h3>Activities</h3>
                <div class="activities-list">
                    ${person.activities.map(activity => `
                        <span class="activity-tag">${activity}</span>
                    `).join('')}
                </div>
            `;
        }

        if (person.activity_map && Object.keys(person.activity_map).length > 0) {
            html += `<h3>Activity Map</h3>`;

            for (const [activityType, venuesByType] of Object.entries(person.activity_map)) {
                if (Object.keys(venuesByType).length === 0) continue;

                html += `
                    <div class="activity-map-section">
                        <h4>${formatActivityType(activityType)}</h4>
                        <div class="activity-venues">
                `;

                for (const [venueType, subsets] of Object.entries(venuesByType)) {
                    if (!subsets || subsets.length === 0) continue;

                    for (const subset of subsets) {
                        html += `
                            <div class="activity-venue-item">
                                <span class="venue-type-badge">${venueType}</span>
                                <span class="venue-name">${subset.venue_name}</span>
                                ${subset.subset_name !== 'default' ? `<span class="subset-name">(${subset.subset_name})</span>` : ''}
                            </div>
                        `;
                    }
                }

                html += `
                        </div>
                    </div>
                `;
            }
        }

        if (person.properties && Object.keys(person.properties).length > 0) {
            html += `
                <h3>Additional Properties</h3>
                <div class="properties-grid">
            `;

            for (const [key, value] of Object.entries(person.properties)) {
                const displayValue = typeof value === 'object' ? JSON.stringify(value) : value;
                html += `
                    <div class="property-item">
                        <span class="property-key">${key}:</span>
                        <span class="property-value">${displayValue}</span>
                    </div>
                `;
            }

            html += `</div>`;
        }

        content.innerHTML = html;
        panel.classList.remove('hidden');

    } catch (error) {
        console.error('Error loading person details:', error);
    }
}

function formatActivityType(activityType) {
    return activityType
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, { showUnitPeople, showPersonDetails });
}
