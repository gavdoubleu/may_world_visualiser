import { state } from './state.js';
import { updateMainNavButtons, updatePanelNavButtons } from './navigation.js';
import { loadUnit } from './unit.js';
import { loadTree } from './tree.js';
import { renderPanelEntry, closeDetailPanel } from './panel.js';
import { showSearchError, performGeoUnitSearch, goToPerson, goToVenue } from './cross_nav.js';
import { initThemeSwitcher } from './theme.js';

function navigateMainBack() {
  if (state.mainHistoryIdx <= 0) return;
  state.mainHistoryIdx--;
  updateMainNavButtons();
  loadUnit(state.mainHistory[state.mainHistoryIdx].unit, { pushHistory: false });
}

function navigateMainForward() {
  if (state.mainHistoryIdx >= state.mainHistory.length - 1) return;
  state.mainHistoryIdx++;
  updateMainNavButtons();
  loadUnit(state.mainHistory[state.mainHistoryIdx].unit, { pushHistory: false });
}

function navigatePanelBack() {
  if (state.panelStackIdx <= 0) return;
  state.panelStackIdx--;
  updatePanelNavButtons();
  renderPanelEntry(state.panelStack[state.panelStackIdx], { pushHistory: false });
}

function navigatePanelForward() {
  if (state.panelStackIdx >= state.panelStack.length - 1) return;
  state.panelStackIdx++;
  updatePanelNavButtons();
  renderPanelEntry(state.panelStack[state.panelStackIdx], { pushHistory: false });
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('close-detail-panel').addEventListener('click', closeDetailPanel);
  document.getElementById('nav-back-btn').addEventListener('click', navigateMainBack);
  document.getElementById('nav-fwd-btn').addEventListener('click', navigateMainForward);
  document.getElementById('panel-back-btn').addEventListener('click', navigatePanelBack);
  document.getElementById('panel-fwd-btn').addEventListener('click', navigatePanelForward);
  loadTree();
  initThemeSwitcher();

  const searchInput     = document.getElementById('header-search-input');
  const searchGeoBtn    = document.getElementById('header-search-geo-btn');
  const searchPersonBtn = document.getElementById('header-search-person-btn');
  const searchVenueBtn  = document.getElementById('header-search-venue-btn');
  const searchError     = document.getElementById('header-search-error');
  const searchDropdown  = document.getElementById('header-search-dropdown');

  searchInput.addEventListener('input', () => searchError.setAttribute('hidden', ''));

  searchGeoBtn.addEventListener('click', () =>
    performGeoUnitSearch(searchInput.value, searchError, searchDropdown));

  searchPersonBtn.addEventListener('click', async () => {
    const id = parseInt(searchInput.value, 10);
    if (isNaN(id)) { showSearchError(searchError, 'Enter a numeric ID'); return; }
    const result = await goToPerson(id);
    if (!result) showSearchError(searchError, 'Person not found');
  });

  searchVenueBtn.addEventListener('click', async () => {
    const id = parseInt(searchInput.value, 10);
    if (isNaN(id)) { showSearchError(searchError, 'Enter a numeric ID'); return; }
    const result = await goToVenue(id);
    if (!result) showSearchError(searchError, 'Venue not found');
  });

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') performGeoUnitSearch(searchInput.value, searchError, searchDropdown);
  });
});
