'use strict';

// ── state ────────────────────────────────────────────────────────────────────

const state = {
  nodeMap:         {},     // id (number) → node
  expandedIds:     new Set(),
  selectedUnit:    null,   // unit name string
  currentUnit:     null,   // API response from /api/geography/unit/<name>
  venueStates:     {},     // venue_type → {open, page, items, total, totalPages}
  expandedVenueId: null,
  expandedPersonId: null,
  peopleData:      null,   // last response from /api/geography/unit/<name>/people
};

// ── bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('close-person-panel')
    .addEventListener('click', closePersonPanel);
  loadTree();
});

// ── helpers ──────────────────────────────────────────────────────────────────

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmt(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString();
}

async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} — ${url}`);
  return resp.json();
}

// ── tree ─────────────────────────────────────────────────────────────────────

async function loadTree() {
  let nodes;
  try {
    nodes = await fetchJson('/api/explorer/tree');
  } catch (err) {
    document.getElementById('geo-tree').innerHTML =
      `<li style="padding:1rem;color:var(--theme-text-muted);font-size:0.8rem">Failed to load: ${esc(err.message)}</li>`;
    return;
  }

  state.nodeMap = {};
  for (const node of nodes) {
    node.children = [];
    state.nodeMap[node.id] = node;
  }

  const roots = [];
  for (const node of nodes) {
    if (node.parent_id !== null && state.nodeMap[node.parent_id]) {
      state.nodeMap[node.parent_id].children.push(node);
    } else {
      roots.push(node);
    }
  }

  const totalPop = roots.reduce((s, n) => s + (n.population || 0), 0);
  document.getElementById('header-stats').textContent =
    `${fmt(nodes.length)} units · ${fmt(totalPop)} people`;

  const container = document.getElementById('geo-tree');
  container.innerHTML = renderNodeList(roots, 0);
  container.addEventListener('click', handleTreeClick);
}

function renderNodeList(nodes, depth) {
  return nodes.map(n => renderNode(n, depth)).join('');
}

function renderNode(node, depth) {
  const hasChildren = node.children.length > 0;
  const isExpanded  = state.expandedIds.has(node.id);
  const isSelected  = state.selectedUnit === node.name;
  const indent      = (0.5 + depth * 0.9) + 'rem';

  return `
    <li class="tree-node">
      <div class="tree-node__row${isSelected ? ' selected' : ''}"
           style="padding-left:${indent}"
           data-action="select" data-name="${esc(node.name)}">
        <span class="tree-toggle"
              data-action="toggle" data-id="${node.id}"
              style="pointer-events:${hasChildren ? 'auto' : 'none'}">
          ${hasChildren ? (isExpanded ? '▼' : '▶') : ''}
        </span>
        <span class="tree-name">${esc(node.name)}</span>
        <span class="tree-level-badge">${esc(node.level)}</span>
        ${node.population > 0 ? `<span class="tree-pop">${fmt(node.population)}</span>` : ''}
      </div>
      ${hasChildren && isExpanded
        ? `<ul class="tree-children">${renderNodeList(node.children, depth + 1)}</ul>`
        : ''}
    </li>`;
}

function handleTreeClick(e) {
  const toggleEl = e.target.closest('[data-action="toggle"]');
  const selectEl = e.target.closest('[data-action="select"]');

  if (toggleEl) {
    e.stopPropagation();
    const id = Number(toggleEl.dataset.id);
    if (state.expandedIds.has(id)) {
      state.expandedIds.delete(id);
    } else {
      state.expandedIds.add(id);
    }
    rerenderTree();
  } else if (selectEl) {
    loadUnit(selectEl.dataset.name);
  }
}

function rerenderTree() {
  const roots = Object.values(state.nodeMap).filter(n => n.parent_id === null);
  document.getElementById('geo-tree').innerHTML = renderNodeList(roots, 0);
}

// ── unit loading ──────────────────────────────────────────────────────────────

async function loadUnit(name) {
  if (state.selectedUnit === name) return;

  state.selectedUnit    = name;
  state.currentUnit     = null;
  state.venueStates     = {};
  state.expandedVenueId = null;
  state.expandedPersonId = null;
  state.peopleData      = null;
  closePersonPanel();
  rerenderTree();

  const placeholder = document.getElementById('unit-placeholder');
  const detail      = document.getElementById('unit-detail');
  placeholder.hidden = true;
  detail.hidden      = false;

  setDetailLoading();

  try {
    state.currentUnit = await fetchJson(`/api/geography/unit/${encodeURIComponent(name)}`);
  } catch (err) {
    detail.innerHTML = `<div style="padding:2rem;color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }

  renderUnitHeader(state.currentUnit);
  renderStatsStrip(state.currentUnit);
  renderDistributions(state.currentUnit);
  renderVenuesSection();
  renderPeopleSectionShell(state.currentUnit);

  loadPeople(name, 1);
}

function setDetailLoading() {
  document.getElementById('unit-title-row').innerHTML        = '';
  document.getElementById('stats-strip-container').innerHTML = '';
  document.getElementById('distributions-container').innerHTML = '';
  document.getElementById('venues-container').innerHTML      = '';
  document.getElementById('people-container').innerHTML      =
    '<div style="padding:1rem;color:var(--theme-text-muted);font-size:0.82rem">Loading…</div>';
}

function renderUnitHeader(unit) {
  const parentHtml = unit.parent
    ? `<span class="parent-link" data-action="select-unit" data-name="${esc(unit.parent.name)}">
         ↑ <span>${esc(unit.parent.name)}</span>
       </span>`
    : '';

  document.getElementById('unit-title-row').innerHTML = `
    <span class="unit-name">${esc(unit.name)}</span>
    <span class="unit-level-badge">${esc(unit.level)}</span>
    ${parentHtml}
  `;

  document.getElementById('unit-title-row').addEventListener('click', (e) => {
    const el = e.target.closest('[data-action="select-unit"]');
    if (el) loadUnit(el.dataset.name);
  });
}

function renderStatsStrip(unit) {
  const totalVenues = Object.values(unit.venue_types || {}).reduce((s, v) => s + v, 0);
  const childrenCount = (unit.children || []).length;

  let cards = `
    <div class="stat-card">
      <div class="stat-label">Population</div>
      <div class="stat-value">${fmt(unit.population)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Venues</div>
      <div class="stat-value">${fmt(totalVenues)}</div>
    </div>`;

  if (childrenCount > 0) {
    cards += `
      <div class="stat-card">
        <div class="stat-label">Sub-units</div>
        <div class="stat-value">${fmt(childrenCount)}</div>
      </div>`;
  }

  document.getElementById('stats-strip-container').innerHTML = cards;
}

function renderDistributions(unit) {
  const ageDist = unit.age_distribution || {};
  const sexDist = unit.sex_distribution || {};
  const ageTotal = Object.values(ageDist).reduce((s, v) => s + v, 0);
  const sexTotal = Object.values(sexDist).reduce((s, v) => s + v, 0);

  let html = '';

  if (ageTotal > 0) {
    const bars = Object.entries(ageDist).map(([label, count]) => {
      const pct = (count / ageTotal * 100).toFixed(1);
      return `
        <div class="bar-item">
          <span class="bar-label">${esc(label)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
          <span class="bar-value">${fmt(count)}</span>
        </div>`;
    }).join('');
    html += `
      <div class="distribution-block">
        <div class="distribution-title">Age Distribution</div>
        <div class="bar-chart">${bars}</div>
      </div>`;
  }

  if (sexTotal > 0) {
    const bars = Object.entries(sexDist).map(([label, count]) => {
      const pct = (count / sexTotal * 100).toFixed(1);
      return `
        <div class="bar-item">
          <span class="bar-label">${esc(label)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
          <span class="bar-value">${fmt(count)}</span>
        </div>`;
    }).join('');
    html += `
      <div class="distribution-block">
        <div class="distribution-title">Sex Distribution</div>
        <div class="bar-chart">${bars}</div>
      </div>`;
  }

  document.getElementById('distributions-container').innerHTML = html;
}

// ── venues section ────────────────────────────────────────────────────────────

function renderVenuesSection() {
  const unit = state.currentUnit;
  const venueTypes = unit.venue_types || {};
  const totalVenues = Object.values(venueTypes).reduce((s, v) => s + v, 0);

  if (totalVenues === 0) {
    document.getElementById('venues-container').innerHTML = '';
    return;
  }

  const groups = Object.entries(venueTypes).map(([type, count]) => {
    const vs = state.venueStates[type] || { open: false, page: 1, items: [], total: 0, totalPages: 1 };
    const listHtml = vs.open ? buildVenueListHtml(type, vs) : '';
    return `
      <div class="venue-group" data-venue-type="${esc(type)}">
        <div class="venue-group__header" data-action="toggle-venue-group" data-type="${esc(type)}">
          <span class="venue-group__toggle${vs.open ? ' open' : ''}">▶</span>
          <span class="venue-type-name">${esc(type)}</span>
          <span class="venue-count-badge">${fmt(count)}</span>
        </div>
        ${vs.open ? `<div class="venue-list">${listHtml}</div>` : ''}
      </div>`;
  }).join('');

  document.getElementById('venues-container').innerHTML = `
    <div class="explorer-section">
      <div class="explorer-section__header">
        <span class="section-title">Venues</span>
        <span class="section-count">${fmt(totalVenues)}</span>
      </div>
      ${groups}
    </div>`;

  document.getElementById('venues-container').addEventListener('click', handleVenueClick);
}

function buildVenueListHtml(type, vs) {
  if (vs.items.length === 0) {
    return '<div style="padding:0.6rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">Loading…</div>';
  }

  const itemsHtml = vs.items.map(v => {
    const isExpanded = state.expandedVenueId === v.id;
    const expandHtml = isExpanded ? buildVenueExpandHtml(v) : '';
    return `
      <div class="venue-item${isExpanded ? ' expanded' : ''}"
           data-action="toggle-venue" data-venue-id="${v.id}">
        <span class="venue-item__toggle">${isExpanded ? '▼' : '▶'}</span>
        <span class="venue-item__name">${esc(v.name)}</span>
      </div>
      ${expandHtml}`;
  }).join('');

  const paginationHtml = vs.total > vs.per_page * vs.page || vs.page > 1
    ? buildVenuePaginationHtml(type, vs)
    : '';

  return itemsHtml + paginationHtml;
}

function buildVenueExpandHtml(venue) {
  const subsets = (venue.subsets || []);
  const props   = Object.entries(venue.properties || {}).filter(([, v]) => v !== null && v !== undefined);

  if (subsets.length === 0 && props.length === 0) {
    return `<div class="venue-subsets"><span class="empty-hint">No subsets or properties.</span></div>`;
  }

  let lines = [];
  if (subsets.length > 0) {
    lines.push('<strong>Subsets</strong>');
    subsets.forEach(s => lines.push(`${esc(s.name)}: ${fmt(s.num_members)} members`));
  }
  if (props.length > 0) {
    if (lines.length > 0) lines.push('');
    lines.push('<strong>Properties</strong>');
    props.forEach(([k, v]) => lines.push(`${esc(k)}: ${esc(String(v))}`));
  }

  return `<div class="venue-subsets">${lines.join('<br>')}</div>`;
}

function buildVenuePaginationHtml(type, vs) {
  const showing = vs.items.length + (vs.page - 1) * 50;
  return `
    <div class="venue-pagination">
      <span>Showing ${fmt(showing)} of ${fmt(vs.total)}</span>
      ${vs.page > 1
        ? `<button data-action="venue-prev" data-type="${esc(type)}" style="margin-left:auto">← Prev</button>`
        : ''}
      ${showing < vs.total
        ? `<button data-action="venue-next" data-type="${esc(type)}" ${vs.page === 1 ? 'style="margin-left:auto"' : ''}>Next →</button>`
        : ''}
    </div>`;
}

async function handleVenueClick(e) {
  const toggleGroup = e.target.closest('[data-action="toggle-venue-group"]');
  const toggleVenue = e.target.closest('[data-action="toggle-venue"]');
  const venuePrev   = e.target.closest('[data-action="venue-prev"]');
  const venueNext   = e.target.closest('[data-action="venue-next"]');

  if (toggleGroup) {
    const type = toggleGroup.dataset.type;
    const vs = state.venueStates[type] || { open: false, page: 1, items: [], total: 0 };
    vs.open = !vs.open;
    state.venueStates[type] = vs;

    if (vs.open && vs.items.length === 0) {
      renderVenuesSection();
      await fetchVenuePage(state.selectedUnit, type, 1);
    } else {
      renderVenuesSection();
    }
    return;
  }

  if (toggleVenue) {
    const venueId = Number(toggleVenue.dataset.venueId);
    state.expandedVenueId = state.expandedVenueId === venueId ? null : venueId;
    renderVenuesSection();
    return;
  }

  if (venuePrev) {
    const type = venuePrev.dataset.type;
    const vs = state.venueStates[type];
    if (vs && vs.page > 1) await fetchVenuePage(state.selectedUnit, type, vs.page - 1);
    return;
  }

  if (venueNext) {
    const type = venueNext.dataset.type;
    const vs = state.venueStates[type];
    if (vs) await fetchVenuePage(state.selectedUnit, type, vs.page + 1);
    return;
  }
}

async function fetchVenuePage(unitName, type, page) {
  const vs = state.venueStates[type] || { open: true, page: 1, items: [], total: 0 };
  state.venueStates[type] = vs;
  renderVenuesSection(); // show loading state

  try {
    const data = await fetchJson(
      `/api/explorer/unit/${encodeURIComponent(unitName)}/venues` +
      `?type=${encodeURIComponent(type)}&page=${page}&per_page=50`
    );
    vs.items      = data.venues;
    vs.total      = data.total_count;
    vs.totalPages = data.total_pages;
    vs.page       = page;
    vs.per_page   = data.per_page;
  } catch (err) {
    vs.items = [];
    vs.total = 0;
  }
  renderVenuesSection();
}

// ── people section ────────────────────────────────────────────────────────────

function renderPeopleSectionShell(unit) {
  document.getElementById('people-container').innerHTML = `
    <div class="explorer-section" id="people-section">
      <div class="explorer-section__header">
        <span class="section-title">People</span>
        <span class="section-count">${fmt(unit.population)}</span>
      </div>
      <div id="people-table-wrap"></div>
      <div id="people-pagination"></div>
    </div>`;
  bindPeopleEvents();
}

async function loadPeople(unitName, page) {
  state.expandedPersonId = null;

  const tableWrap = document.getElementById('people-table-wrap');
  const paginationEl = document.getElementById('people-pagination');
  if (!tableWrap) return;

  tableWrap.innerHTML = '<div style="padding:0.8rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">Loading…</div>';

  let data;
  try {
    data = await fetchJson(
      `/api/geography/unit/${encodeURIComponent(unitName)}/people` +
      `?page=${page}&per_page=50&include_descendants=true`
    );
  } catch (err) {
    tableWrap.innerHTML =
      `<div style="padding:0.8rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }

  state.peopleData = data;

  if (data.people.length === 0) {
    tableWrap.innerHTML = '<div style="padding:0.8rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">No people found.</div>';
    if (paginationEl) paginationEl.innerHTML = '';
    return;
  }

  tableWrap.innerHTML = `
    <table class="people-table">
      <thead>
        <tr>
          <th>ID</th><th>Age</th><th>Sex</th><th>Activities</th><th></th>
        </tr>
      </thead>
      <tbody id="people-tbody">${renderPeopleRows(data.people)}</tbody>
    </table>`;

  if (paginationEl) paginationEl.innerHTML = renderPeoplePagination(data);
}

function renderPeopleRows(people) {
  return people.map(p => {
    const isExpanded   = state.expandedPersonId === p.id;
    const activitiesStr = (p.activities || []).join(', ') || '—';
    const expandRow     = isExpanded ? buildPersonExpandHtml(p) : '';

    return `
      <tr class="data-row${isExpanded ? ' expanded' : ''}"
          data-action="toggle-person" data-person-id="${p.id}">
        <td class="td-id">${p.id}</td>
        <td>${p.age}</td>
        <td>${esc(p.sex)}</td>
        <td class="td-activities">${esc(activitiesStr)}</td>
        <td class="td-expand">${isExpanded ? '▴' : '▾'}</td>
      </tr>
      ${expandRow}`;
  }).join('');
}

function buildPersonExpandHtml(person) {
  const activities = person.activities || [];
  const tagsHtml = activities.length > 0
    ? activities.map(a => `<span class="activity-tag">${esc(a)}</span>`).join('')
    : '<span style="color:var(--theme-text-muted)">none</span>';

  return `
    <tr class="person-expand-row">
      <td colspan="5">
        <div class="person-expand-content">
          <div>
            <strong>Age</strong>${person.age}
          </div>
          <div>
            <strong>Sex</strong>${esc(person.sex)}
          </div>
          <div>
            <strong>Activities</strong>
            <div class="activities-list">${tagsHtml}</div>
          </div>
          <div>
            <button class="btn-details"
                    data-action="open-person" data-person-id="${person.id}">
              View full details →
            </button>
          </div>
        </div>
      </td>
    </tr>`;
}

function renderPeoplePagination(data) {
  if (data.total_pages <= 1) return '';
  return `
    <div class="pagination">
      <button ${data.page <= 1 ? 'disabled' : ''}
              data-action="people-prev">← Prev</button>
      <span class="page-info">Page ${data.page} of ${data.total_pages}</span>
      <button ${data.page >= data.total_pages ? 'disabled' : ''}
              data-action="people-next">Next →</button>
      <span class="total-info">${fmt(data.total_count)} total</span>
    </div>`;
}

function bindPeopleEvents() {
  const section = document.getElementById('people-section');
  if (!section) return;

  section.addEventListener('click', async (e) => {
    const openBtn   = e.target.closest('[data-action="open-person"]');
    const toggleRow = e.target.closest('[data-action="toggle-person"]');
    const prevBtn   = e.target.closest('[data-action="people-prev"]');
    const nextBtn   = e.target.closest('[data-action="people-next"]');

    if (openBtn) {
      e.stopPropagation();
      await openPersonPanel(Number(openBtn.dataset.personId));
    } else if (toggleRow) {
      const personId = Number(toggleRow.dataset.personId);
      state.expandedPersonId = state.expandedPersonId === personId ? null : personId;
      const tbody = document.getElementById('people-tbody');
      if (tbody && state.peopleData) tbody.innerHTML = renderPeopleRows(state.peopleData.people);
    } else if (prevBtn && !prevBtn.disabled && state.peopleData) {
      await loadPeople(state.selectedUnit, state.peopleData.page - 1);
    } else if (nextBtn && !nextBtn.disabled && state.peopleData) {
      await loadPeople(state.selectedUnit, state.peopleData.page + 1);
    }
  });
}

// ── person panel ──────────────────────────────────────────────────────────────

async function openPersonPanel(personId) {
  const panel = document.getElementById('person-panel');
  const content = document.getElementById('person-panel-content');
  document.getElementById('person-panel-title').textContent = `Person ${personId}`;
  content.innerHTML = '<div style="color:var(--theme-text-muted);font-size:0.82rem">Loading…</div>';
  panel.classList.add('open');

  let person;
  try {
    person = await fetchJson(`/api/population/person/${personId}`);
  } catch (err) {
    content.innerHTML = `<div style="color:var(--theme-text-muted);font-size:0.82rem">Error: ${esc(err.message)}</div>`;
    return;
  }

  content.innerHTML = buildPersonPanelHtml(person);
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

  // Activities list
  const activities = person.activities || [];
  if (activities.length > 0) {
    html += `
      <div class="detail-section-title">Activities</div>
      <div class="activities-list" style="margin-bottom:0.75rem">
        ${activities.map(a => `<span class="activity-tag">${esc(a)}</span>`).join('')}
      </div>`;
  }

  // Activity map
  const actMap = person.activity_map || {};
  const actEntries = Object.entries(actMap);
  if (actEntries.length > 0) {
    html += `<div class="detail-section-title">Activity Map</div>`;
    for (const [actType, venuesByType] of actEntries) {
      for (const [venueType, subsets] of Object.entries(venuesByType || {})) {
        if (!subsets || subsets.length === 0) continue;
        for (const s of subsets) {
          html += `
            <div class="activity-map-item">
              <div class="activity-map-type">${esc(actType)}</div>
              <div class="activity-map-venue">
                ${esc(venueType)} — <span>${esc(s.venue_name || '—')}</span>
                (subset: ${esc(s.subset_name || '—')})
              </div>
            </div>`;
        }
      }
    }
  }

  // Properties
  const props = Object.entries(person.properties || {}).filter(([, v]) => v !== null);
  if (props.length > 0) {
    html += `<div class="detail-section-title">Properties</div>
      <div class="detail-grid">`;
    for (const [k, v] of props) {
      html += `
        <div class="detail-item">
          <div class="detail-item__label">${esc(k)}</div>
          <div class="detail-item__value" style="font-size:0.82rem">${esc(String(v))}</div>
        </div>`;
    }
    html += '</div>';
  }

  return html;
}

function closePersonPanel() {
  document.getElementById('person-panel').classList.remove('open');
}
