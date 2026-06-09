'use strict';

// Cross-navigation helpers — depend on state, fetchJson, loadUnit, PAGE_SIZE
// from app.js (loaded first).

async function goToPerson(personId) {
  let location;
  try {
    location = await fetchJson(`/api/explorer/person/${personId}/locate?per_page=${PAGE_SIZE}`);
  } catch (err) {
    return null;
  }
  if (!location.geo_unit_id) return null;
  state.highlightPersonId = personId;
  state.targetPeoplePage  = location.page;
  await loadUnit(location.geo_unit_id);
  return location;
}

async function goToVenue(venueId) {
  let location;
  try {
    location = await fetchJson(`/api/explorer/venue/${venueId}/locate?per_page=${PAGE_SIZE}`);
  } catch (err) {
    return null;
  }
  if (!location.geo_unit_id) return null;
  if (location.parent_venue_id) {
    state.highlightVenueId       = location.parent_venue_id;
    state.highlightVenueType     = location.venue_type;
    state.highlightVenuePage     = location.page;
    state.highlightParentVenueId = location.parent_venue_id;
    state.highlightChildVenueId  = venueId;
    state.highlightChildPage     = location.child_page;
  } else {
    state.highlightVenueId   = venueId;
    state.highlightVenueType = location.venue_type;
    state.highlightVenuePage = location.page;
  }
  await loadUnit(location.geo_unit_id);
  return location;
}

async function goToGeoUnit(unitId) {
  // Expand all ancestors of the target node in the tree, then navigate.
  const node = state.nodeMap[unitId];
  if (!node) return;

  let ancestor = state.nodeMap[node.parent_id];
  while (ancestor) {
    state.expandedIds.add(ancestor.id);
    ancestor = state.nodeMap[ancestor.parent_id];
  }

  await loadUnit(unitId);

  // Scroll the selected tree node into view after render.
  requestAnimationFrame(() => {
    document.querySelector(`[data-unit-id="${unitId}"][data-action="select"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}
