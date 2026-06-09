import { state } from './state.js';
import { openPersonPanel } from './person_detail.js';
import { openVenueDetailsPanel } from './venue_detail.js';
import { goToVenue } from './cross_nav.js';

export function closeDetailPanel() {
  document.getElementById('detail-panel').classList.remove('open');
}

export async function renderPanelEntry(entry, { pushHistory = true } = {}) {
  if (entry.type === 'person') {
    await openPersonPanel(entry.id, { pushHistory });
  } else if (entry.type === 'venue_details') {
    await openVenueDetailsPanel(entry.id, entry.name, { pushHistory });
  }
}

export async function handlePanelClick(e) {
  const gotoVenueBtn = e.target.closest('[data-action="go-to-venue"]');
  if (gotoVenueBtn) {
    e.stopPropagation();
    await goToVenue(Number(gotoVenueBtn.dataset.venueId));
  }
}
