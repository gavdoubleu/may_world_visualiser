// Go-to-geo-unit cross-nav — resolves the owning GeoUnit for a Venue/Person,
// flies the map to it, and swaps the panel to that unit's own view.

async function goToGeoUnitFromVenue(venueId) {
    await _goToGeoUnit(`/api/geography/venue/${venueId}/locate`);
}

async function goToGeoUnitFromPerson(personId) {
    await _goToGeoUnit(`/api/geography/person/${personId}/locate`);
}

async function _goToGeoUnit(locateUrl) {
    try {
        const locateResponse = await fetch(locateUrl);
        const location = await locateResponse.json();
        if (location.error || location.geo_unit_id === null || location.geo_unit_id === undefined) {
            console.error('Error locating geo unit:', location.error);
            return;
        }

        const unitResponse = await fetch(`/api/geography/unit_by_id/${location.geo_unit_id}`);
        const unit = await unitResponse.json();
        if (unit.error) {
            console.error('Error resolving geo unit name:', unit.error);
            return;
        }

        await WorldMap.showUnitDetails(unit.name, { flyTo: true });
    } catch (error) {
        console.error('Error navigating to geo unit:', error);
    }
}

if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, { goToGeoUnitFromVenue, goToGeoUnitFromPerson });
}
