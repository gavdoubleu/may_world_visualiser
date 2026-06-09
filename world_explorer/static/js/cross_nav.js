import { state, PAGE_SIZE } from './state.js';
import { esc, fetchJson } from './utils.js';
import { loadUnit } from './unit.js';

export function showSearchError(errorEl, message) {
  errorEl.textContent = message;
  errorEl.removeAttribute('hidden');
  clearTimeout(errorEl._dismissTimer);
  errorEl._dismissTimer = setTimeout(() => errorEl.setAttribute('hidden', ''), 3000);
}

export async function performGeoUnitSearch(query, errorEl, dropdownEl) {
  dropdownEl.setAttribute('hidden', '');
  dropdownEl.innerHTML = '';
  if (!query.trim()) return;
  let results;
  try {
    results = await fetchJson(`/api/explorer/geo_unit/search?name=${encodeURIComponent(query)}`);
  } catch {
    showSearchError(errorEl, 'Search failed');
    return;
  }
  if (results.length === 0) {
    showSearchError(errorEl, 'Not found');
    return;
  }
  if (results.length === 1) {
    goToGeoUnit(results[0].id);
    return;
  }
  dropdownEl.innerHTML = results.map(r =>
    `<li data-unit-id="${r.id}">${esc(r.name)} · ${esc(r.level)}${r.parent_name ? ' · ' + esc(r.parent_name) : ''}</li>`
  ).join('');
  dropdownEl.removeAttribute('hidden');
  dropdownEl.addEventListener('click', e => {
    const li = e.target.closest('li[data-unit-id]');
    if (!li) return;
    dropdownEl.setAttribute('hidden', '');
    goToGeoUnit(Number(li.dataset.unitId));
  }, { once: true });
}

export async function goToPerson(personId) {
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

export async function goToVenue(venueId) {
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

export async function goToGeoUnit(unitId) {
  const node = state.nodeMap[unitId];
  if (!node) return;

  let ancestor = state.nodeMap[node.parent_id];
  while (ancestor) {
    state.expandedIds.add(ancestor.id);
    ancestor = state.nodeMap[ancestor.parent_id];
  }

  await loadUnit(unitId);

  requestAnimationFrame(() => {
    document.querySelector(`[data-unit-id="${unitId}"][data-action="select"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}
