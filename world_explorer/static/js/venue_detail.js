import { esc, fmt, fetchJson } from './utils.js';
import { pushPanelHistory } from './navigation.js';
import { handlePanelClick } from './panel.js';
import { goToPerson } from './cross_nav.js';

export async function openVenueDetailsPanel(venueId, venueName, { pushHistory = true } = {}) {
  if (pushHistory) pushPanelHistory({ type: 'venue_details', id: venueId, name: venueName });

  const panel   = document.getElementById('detail-panel');
  const content = document.getElementById('detail-panel-content');
  document.getElementById('detail-panel-title').textContent = venueName || `Venue ${venueId}`;
  content.innerHTML = '<div style="color:var(--theme-text-muted);font-size:0.82rem">Loading…</div>';
  panel.classList.add('open');

  let detail;
  try {
    detail = await fetchJson(`/api/explorer/venue/${venueId}/detail`);
  } catch (err) {
    content.innerHTML = `<div style="color:var(--theme-text-muted);font-size:0.82rem">Error: ${esc(err.message)}</div>`;
    return;
  }

  document.getElementById('detail-panel-title').textContent = detail.name || venueName;
  content.innerHTML = buildVenueDetailHtml(detail);
  loadVenueDetailMembers(venueId, content);
  content.addEventListener('click', handlePanelClick);
}

function buildVenueDetailHtml(venue) {
  const coords = venue.coordinates;
  const props  = Object.entries(venue.properties || {}).filter(([, v]) => v !== null);

  let html = `
    <div class="detail-grid">
      <div class="detail-item">
        <div class="detail-item__label">ID</div>
        <div class="detail-item__value">${venue.id}</div>
      </div>
      <div class="detail-item">
        <div class="detail-item__label">Name</div>
        <div class="detail-item__value">${esc(venue.name)}</div>
      </div>
      <div class="detail-item">
        <div class="detail-item__label">Type</div>
        <div class="detail-item__value">${esc(venue.type)}</div>
      </div>
      ${venue.geo_unit ? `
      <div class="detail-item">
        <div class="detail-item__label">Geo unit</div>
        <div class="detail-item__value" style="font-size:0.8rem">${esc(venue.geo_unit)}</div>
      </div>` : ''}
      ${coords ? `
      <div class="detail-item">
        <div class="detail-item__label">Latitude</div>
        <div class="detail-item__value">${(+coords[0]).toFixed(4)}</div>
      </div>
      <div class="detail-item">
        <div class="detail-item__label">Longitude</div>
        <div class="detail-item__value">${(+coords[1]).toFixed(4)}</div>
      </div>` : ''}
    </div>`;

  if (props.length > 0) {
    html += `<div class="detail-section-title">Properties</div><div class="detail-grid">`;
    for (const [k, v] of props) {
      html += `
        <div class="detail-item">
          <div class="detail-item__label">${esc(k)}</div>
          <div class="detail-item__value" style="font-size:0.82rem">${esc(String(v))}</div>
        </div>`;
    }
    html += '</div>';
  }

  html += `<div class="detail-section-title">Members</div>
    <div id="venue-members-section">
      <div style="color:var(--theme-text-muted);font-size:0.82rem">Loading from file…</div>
    </div>`;

  return html;
}

async function loadVenueDetailMembers(venueId, container) {
  const section = container.querySelector('#venue-members-section');
  if (!section) return;

  let data;
  try {
    data = await fetchJson(`/api/explorer/venue/${venueId}/members`);
  } catch (err) {
    section.innerHTML = `<div style="color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }

  section.innerHTML = buildVenueMembersHtml(data);
  bindVenueMembersEvents(section);
}

function buildVenueMembersHtml(data) {
  if (!data.subsets || data.subsets.length === 0) {
    return '<div style="color:var(--theme-text-muted);font-size:0.82rem">No member data.</div>';
  }

  return data.subsets.map(subset => {
    const membersHtml = subset.members.map(m => `
      <div class="member-row">
        <span class="member-id">${m.id}</span>
        <span class="member-age">${m.age}</span>
        <span class="member-sex">${esc(m.sex)}</span>
        <span class="member-unit">${esc(m.geo_unit)}</span>
        <button class="icon-btn"
                data-action="go-to-person"
                data-person-id="${m.id}"
                data-geo-unit="${esc(m.geo_unit)}"
                title="Go to person in main window">
          <img src="/static/images/to_person_logo.svg" alt="Go to person">
        </button>
      </div>`).join('');

    const hasPagination = subset.total_pages > 1;
    const paginationHtml = hasPagination ? `
      <div class="member-pagination">
        ${subset.page > 1
          ? `<button class="nav-btn" data-action="member-prev"
                    data-subset="${esc(subset.name)}"
                    data-venue-id="${data.venue_id}">← Prev</button>`
          : ''}
        <input type="number" class="page-input" data-action="member-jump"
               data-subset="${esc(subset.name)}" data-venue-id="${data.venue_id}"
               data-total="${subset.total_pages}"
               value="${subset.page}" min="1" max="${subset.total_pages}">
        <span class="page-info">of ${subset.total_pages}</span>
        ${subset.page < subset.total_pages
          ? `<button class="nav-btn" data-action="member-next"
                    data-subset="${esc(subset.name)}"
                    data-venue-id="${data.venue_id}">Next →</button>`
          : ''}
      </div>` : '';

    return `
      <details class="subset-group" open>
        <summary class="subset-group__title">
          ${esc(subset.name)}
          <span class="subset-count">${fmt(subset.total)}</span>
        </summary>
        <div class="member-list">
          <div class="member-list__header">
            <span>ID</span><span>Age</span><span>Sex</span><span>Unit</span><span></span>
          </div>
          ${membersHtml || '<div style="padding:0.5rem;color:var(--theme-text-muted)">No members on this page.</div>'}
        </div>
        ${paginationHtml}
      </details>`;
  }).join('');
}

async function handleVenueMembersClick(e) {
  const gotoBtn = e.target.closest('[data-action="go-to-person"]');
  const prevBtn = e.target.closest('[data-action="member-prev"]');
  const nextBtn = e.target.closest('[data-action="member-next"]');

  if (gotoBtn) {
    e.stopPropagation();
    await goToPerson(Number(gotoBtn.dataset.personId));
    return;
  }

  if (prevBtn || nextBtn) {
    const btn         = prevBtn || nextBtn;
    const subsetName  = btn.dataset.subset;
    const venueId     = Number(btn.dataset.venueId);
    const details     = btn.closest('details');
    const jumpInput   = details.querySelector('[data-action="member-jump"]');
    const currentPage = jumpInput ? Number(jumpInput.value) : 1;
    await loadMemberPage(venueId, subsetName, prevBtn ? currentPage - 1 : currentPage + 1);
  }
}

async function loadMemberPage(venueId, subsetName, page) {
  const content = document.getElementById('detail-panel-content');
  content.innerHTML = '<div style="color:var(--theme-text-muted);font-size:0.82rem">Loading…</div>';
  let data;
  try {
    data = await fetchJson(`/api/explorer/venue/${venueId}/members?subset=${encodeURIComponent(subsetName)}&page=${page}`);
  } catch (err) {
    content.innerHTML = `<div style="color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }
  content.innerHTML = buildVenueMembersHtml(data);
  bindVenueMembersEvents(content);
}

function bindVenueMembersEvents(container) {
  container.addEventListener('click', handleVenueMembersClick);
  container.addEventListener('keydown', async (e) => {
    const input = e.target.closest('[data-action="member-jump"]');
    if (!input || e.key !== 'Enter') return;
    const page = Math.max(1, Math.min(Number(input.value), Number(input.dataset.total)));
    await loadMemberPage(Number(input.dataset.venueId), input.dataset.subset, page);
  });
  container.addEventListener('change', async (e) => {
    const input = e.target.closest('[data-action="member-jump"]');
    if (!input) return;
    const page = Math.max(1, Math.min(Number(input.value), Number(input.dataset.total)));
    await loadMemberPage(Number(input.dataset.venueId), input.dataset.subset, page);
  });
}
