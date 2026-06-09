import { esc, fetchJson } from './utils.js';
import { pushPanelHistory } from './navigation.js';
import { handlePanelClick } from './panel.js';

export async function openPersonPanel(personId, { pushHistory = true } = {}) {
  if (pushHistory) pushPanelHistory({ type: 'person', id: personId });

  const panel   = document.getElementById('detail-panel');
  const content = document.getElementById('detail-panel-content');
  document.getElementById('detail-panel-title').textContent = `Person ${personId}`;
  content.innerHTML = '<div style="color:var(--theme-text-muted);font-size:0.82rem">Loading…</div>';
  panel.classList.add('open');

  let person;
  try {
    person = await fetchJson(`/api/explorer/person/${personId}`);
  } catch (err) {
    content.innerHTML = `<div style="color:var(--theme-text-muted);font-size:0.82rem">Error: ${esc(err.message)}</div>`;
    return;
  }

  content.innerHTML = buildPersonPanelHtml(person);

  content.querySelector('[data-action="load-full-details"]')
    ?.addEventListener('click', () => loadPersonFullDetails(personId, content));

  content.addEventListener('click', handlePanelClick);
}

function buildPersonPanelHtml(person) {
  const geo = person.geographical_unit;

  let html = `
    <div class="detail-grid">
      <div class="detail-item">
        <div class="detail-item__label">ID</div>
        <div class="detail-item__value">${person.id}</div>
      </div>
      <div class="detail-item">
        <div class="detail-item__label">Age</div>
        <div class="detail-item__value">${person.age}</div>
      </div>
      <div class="detail-item">
        <div class="detail-item__label">Sex</div>
        <div class="detail-item__value">${esc(person.sex)}</div>
      </div>
      ${geo ? `
        <div class="detail-item">
          <div class="detail-item__label">Location</div>
          <div class="detail-item__value" style="font-size:0.8rem">${esc(geo.name)}</div>
        </div>` : ''}
    </div>`;

  const props = Object.entries(person.properties || {}).filter(([, v]) => v !== null);
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

  html += `
    <div class="detail-section-title">Activities</div>
    <div id="person-activities-full">
      <button class="btn-details" data-action="load-full-details">Load activities →</button>
    </div>`;

  return html;
}

async function loadPersonFullDetails(personId, container) {
  const actContainer = container.querySelector('#person-activities-full');
  if (!actContainer) return;
  actContainer.innerHTML = '<div style="color:var(--theme-text-muted);font-size:0.82rem">Loading from file…</div>';

  let data;
  try {
    data = await fetchJson(`/api/explorer/person/${personId}/full`);
  } catch (err) {
    actContainer.innerHTML = `<div style="color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }

  actContainer.innerHTML = buildActivitiesHtml(data.activities);
}

function buildActivitiesHtml(activities) {
  if (!activities || activities.length === 0) {
    return '<div style="color:var(--theme-text-muted);font-size:0.82rem;padding:0.5rem 0">No activities found.</div>';
  }

  return activities.map(a => `
    <div class="activity-map-item">
      <div class="activity-map-header">
        <span class="activity-map-type">${esc(a.activity_name)}</span>
        <button class="icon-btn"
                data-action="go-to-venue"
                data-venue-id="${a.venue_id}"
                data-venue-name="${esc(a.venue_name)}"
                data-venue-type="${esc(a.venue_type)}"
                data-venue-geo-unit="${esc(a.venue_geo_unit)}"
                title="Go to venue in main window">
          <img src="/static/images/to_venue_logo.svg" alt="Go to venue">
        </button>
      </div>
      <div class="activity-map-venue">
        <span class="venue-type-tag">${esc(a.venue_type)}</span>
        <span class="venue-name">${esc(a.venue_name)}</span>
        <span class="subset-tag">${esc(a.subset_name)}</span>
      </div>
    </div>`).join('');
}
