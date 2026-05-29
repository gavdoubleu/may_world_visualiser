'use strict';

// ── state ─────────────────────────────────────────────────────────────────────

const state = {
  nodeMap:           {},
  expandedIds:       new Set(),
  selectedUnit:      null,
  currentUnit:       null,
  venueStates:       {},
  expandedVenueId:   null,
  expandedPersonId:  null,
  peopleData:        null,
  highlightPersonId: null,
  highlightVenueId:  null,
  highlightVenueType: null,

  mainHistory:    [],   // [{unit}], max 10
  mainHistoryIdx: -1,

  panelStack:    [],    // [{type, id, name}]
  panelStackIdx: -1,
};

// ── bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('close-detail-panel')
    .addEventListener('click', closeDetailPanel);
  document.getElementById('nav-back-btn')
    .addEventListener('click', navigateMainBack);
  document.getElementById('nav-fwd-btn')
    .addEventListener('click', navigateMainForward);
  document.getElementById('panel-back-btn')
    .addEventListener('click', navigatePanelBack);
  document.getElementById('panel-fwd-btn')
    .addEventListener('click', navigatePanelForward);
  loadTree();
});

// ── helpers ───────────────────────────────────────────────────────────────────

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

// ── main window history ────────────────────────────────────────────────────────

function pushMainHistory(unitName) {
  state.mainHistory = state.mainHistory.slice(0, state.mainHistoryIdx + 1);
  state.mainHistory.push({ unit: unitName });
  if (state.mainHistory.length > 10) state.mainHistory.shift();
  state.mainHistoryIdx = state.mainHistory.length - 1;
  updateMainNavButtons();
}

function updateMainNavButtons() {
  const back = document.getElementById('nav-back-btn');
  const fwd  = document.getElementById('nav-fwd-btn');
  if (back) back.disabled = state.mainHistoryIdx <= 0;
  if (fwd)  fwd.disabled  = state.mainHistoryIdx >= state.mainHistory.length - 1;
}

function navigateMainBack() {
  if (state.mainHistoryIdx <= 0) return;
  state.mainHistoryIdx--;
  updateMainNavButtons();
  const entry = state.mainHistory[state.mainHistoryIdx];
  loadUnit(entry.unit, { pushHistory: false });
}

function navigateMainForward() {
  if (state.mainHistoryIdx >= state.mainHistory.length - 1) return;
  state.mainHistoryIdx++;
  updateMainNavButtons();
  const entry = state.mainHistory[state.mainHistoryIdx];
  loadUnit(entry.unit, { pushHistory: false });
}

// ── panel history ─────────────────────────────────────────────────────────────

function pushPanelHistory(entry) {
  state.panelStack = state.panelStack.slice(0, state.panelStackIdx + 1);
  state.panelStack.push(entry);
  state.panelStackIdx = state.panelStack.length - 1;
  updatePanelNavButtons();
}

function updatePanelNavButtons() {
  const back = document.getElementById('panel-back-btn');
  const fwd  = document.getElementById('panel-fwd-btn');
  if (back) back.disabled = state.panelStackIdx <= 0;
  if (fwd)  fwd.disabled  = state.panelStackIdx >= state.panelStack.length - 1;
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

async function renderPanelEntry(entry, { pushHistory = true } = {}) {
  if (entry.type === 'person') {
    await openPersonPanel(entry.id, { pushHistory });
  } else if (entry.type === 'venue_details') {
    await openVenueDetailsPanel(entry.id, entry.name, { pushHistory });
  }
}

// ── tree ──────────────────────────────────────────────────────────────────────

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

// ── unit loading ───────────────────────────────────────────────────────────────

async function loadUnit(name, { pushHistory = true } = {}) {
  if (state.selectedUnit === name && pushHistory &&
      !state.highlightPersonId && !state.highlightVenueId) return;

  if (pushHistory) pushMainHistory(name);

  state.selectedUnit     = name;
  state.currentUnit      = null;
  state.venueStates      = {};
  state.expandedVenueId  = null;
  state.expandedPersonId = null;
  state.peopleData       = null;
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
  document.getElementById('unit-title-row').innerHTML          = '';
  document.getElementById('stats-strip-container').innerHTML   = '';
  document.getElementById('distributions-container').innerHTML = '';
  document.getElementById('venues-container').innerHTML        = '';
  document.getElementById('people-container').innerHTML        =
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
  const totalVenues   = Object.values(unit.venue_types || {}).reduce((s, v) => s + v, 0);
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
  const ageDist  = unit.age_distribution || {};
  const sexDist  = unit.sex_distribution || {};
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

// ── venues section ─────────────────────────────────────────────────────────────

function renderVenuesSection() {
  const unit       = state.currentUnit;
  const venueTypes = unit.venue_types || {};
  const totalVenues = Object.values(venueTypes).reduce((s, v) => s + v, 0);

  if (totalVenues === 0) {
    document.getElementById('venues-container').innerHTML = '';
    return;
  }

  const groups = Object.entries(venueTypes).map(([type, count]) => {
    const vs       = state.venueStates[type] || { open: false, page: 1, items: [], total: 0, totalPages: 1 };
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

  const venuesContainer = document.getElementById('venues-container');
  venuesContainer.addEventListener('click', handleVenueClick);

  const jumpToVenuePage = async (input) => {
    const type  = input.dataset.type;
    const total = Number(input.dataset.total);
    const page  = Math.max(1, Math.min(Number(input.value), total));
    if (type && page) await fetchVenuePage(state.selectedUnit, type, page);
  };
  venuesContainer.addEventListener('keydown', async (e) => {
    const input = e.target.closest('[data-action="venue-jump"]');
    if (input && e.key === 'Enter') await jumpToVenuePage(input);
  });
  venuesContainer.addEventListener('change', async (e) => {
    const input = e.target.closest('[data-action="venue-jump"]');
    if (input) await jumpToVenuePage(input);
  });

  // Auto-highlight target venue after navigation
  if (state.highlightVenueId && state.highlightVenueType) {
    const targetType = state.highlightVenueType;
    const targetId   = state.highlightVenueId;
    state.highlightVenueId   = null;
    state.highlightVenueType = null;

    const vs = state.venueStates[targetType] || { open: false, page: 1, items: [], total: 0 };
    vs.open = true;
    state.venueStates[targetType] = vs;
    renderVenuesSection();
    fetchVenuePage(state.selectedUnit, targetType, 1).then(() => {
      const vs2 = state.venueStates[targetType];
      if (vs2 && vs2.items.length > 0) {
        state.expandedVenueId = targetId;
        renderVenuesSection();
        document.querySelector(`[data-venue-id="${targetId}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }
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

  const showing = vs.items.length + (vs.page - 1) * 50;
  const paginationHtml = vs.total > vs.per_page * vs.page || vs.page > 1
    ? buildVenuePaginationHtml(type, vs)
    : '';

  return itemsHtml + paginationHtml;
}

function buildVenueExpandHtml(venue) {
  const subsets = (venue.subsets || []);
  const props   = Object.entries(venue.properties || {}).filter(([, v]) => v !== null && v !== undefined);

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

  const bodyHtml = lines.length > 0
    ? `<div>${lines.join('<br>')}</div>`
    : '<span class="empty-hint">No subsets or properties.</span>';

  return `
    <div class="venue-subsets">
      ${bodyHtml}
      <div>
        <button class="btn-details"
                data-action="open-venue-details"
                data-venue-id="${venue.id}"
                data-venue-name="${esc(venue.name)}">
          View full details →
        </button>
      </div>
    </div>`;
}

function buildVenuePaginationHtml(type, vs) {
  const showing = vs.items.length + (vs.page - 1) * 50;
  const totalPages = Math.max(1, Math.ceil(vs.total / vs.per_page));
  return `
    <div class="venue-pagination">
      <span>Showing ${fmt(showing)} of ${fmt(vs.total)}</span>
      ${vs.page > 1
        ? `<button data-action="venue-prev" data-type="${esc(type)}" style="margin-left:auto">← Prev</button>`
        : ''}
      <input type="number" class="page-input" data-action="venue-jump"
             data-type="${esc(type)}" data-total="${totalPages}"
             value="${vs.page}" min="1" max="${totalPages}" ${vs.page === 1 && showing >= vs.total ? 'style="margin-left:auto"' : ''}>
      ${showing < vs.total
        ? `<button data-action="venue-next" data-type="${esc(type)}">Next →</button>`
        : ''}
    </div>`;
}

async function handleVenueClick(e) {
  const openDetails  = e.target.closest('[data-action="open-venue-details"]');
  const toggleGroup  = e.target.closest('[data-action="toggle-venue-group"]');
  const toggleVenue  = e.target.closest('[data-action="toggle-venue"]');
  const venuePrev    = e.target.closest('[data-action="venue-prev"]');
  const venueNext    = e.target.closest('[data-action="venue-next"]');

  if (openDetails) {
    e.stopPropagation();
    await openVenueDetailsPanel(
      Number(openDetails.dataset.venueId),
      openDetails.dataset.venueName
    );
    return;
  }

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
  renderVenuesSection();

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

  const tableWrap    = document.getElementById('people-table-wrap');
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

  // Check if we need to scroll-to a highlighted person
  if (state.highlightPersonId) {
    const targetId = state.highlightPersonId;
    const found    = data.people.find(p => p.id === targetId);
    if (found) {
      state.expandedPersonId  = targetId;
      state.highlightPersonId = null;
    } else if (data.page < data.total_pages) {
      // Person not on this page — try next page
      await loadPeople(unitName, page + 1);
      return;
    } else {
      state.highlightPersonId = null;
    }
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

  // Scroll to highlighted person if found
  if (state.expandedPersonId) {
    const row = tableWrap.querySelector(`[data-person-id="${state.expandedPersonId}"]`);
    row?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function renderPeopleRows(people) {
  return people.map(p => {
    const isExpanded    = state.expandedPersonId === p.id;
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
  return `
    <tr class="person-expand-row">
      <td colspan="5">
        <div class="person-expand-content">
          <div><strong>Age</strong>${person.age}</div>
          <div><strong>Sex</strong>${esc(person.sex)}</div>
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
      <span class="page-info">
        Page <input type="number" class="page-input" data-action="people-jump"
                    data-total="${data.total_pages}" value="${data.page}" min="1" max="${data.total_pages}">
        of ${data.total_pages}
      </span>
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

  section.addEventListener('keydown', async (e) => {
    const input = e.target.closest('[data-action="people-jump"]');
    if (!input || e.key !== 'Enter') return;
    const page = Math.max(1, Math.min(Number(input.value), Number(input.dataset.total)));
    if (page && state.selectedUnit) await loadPeople(state.selectedUnit, page);
  });

  section.addEventListener('change', async (e) => {
    const input = e.target.closest('[data-action="people-jump"]');
    if (!input) return;
    const page = Math.max(1, Math.min(Number(input.value), Number(input.dataset.total)));
    if (page && state.selectedUnit) await loadPeople(state.selectedUnit, page);
  });
}

// ── side panel ────────────────────────────────────────────────────────────────

function closeDetailPanel() {
  document.getElementById('detail-panel').classList.remove('open');
}

// ── person detail panel ───────────────────────────────────────────────────────

async function openPersonPanel(personId, { pushHistory = true } = {}) {
  if (pushHistory) pushPanelHistory({ type: 'person', id: personId });

  const panel   = document.getElementById('detail-panel');
  const content = document.getElementById('detail-panel-content');
  document.getElementById('detail-panel-title').textContent = `Person ${personId}`;
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

  // Bind "View full details" button
  content.querySelector('[data-action="load-full-details"]')
    ?.addEventListener('click', () => loadPersonFullDetails(personId, content));

  // Bind venue icon buttons in any pre-rendered activity map items
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

  // Properties
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

// ── venue details panel ───────────────────────────────────────────────────────

async function openVenueDetailsPanel(venueId, venueName, { pushHistory = true } = {}) {
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

// ── venue members rendering ───────────────────────────────────────────────────

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
  const gotoBtn  = e.target.closest('[data-action="go-to-person"]');
  const prevBtn  = e.target.closest('[data-action="member-prev"]');
  const nextBtn  = e.target.closest('[data-action="member-next"]');

  if (gotoBtn) {
    e.stopPropagation();
    const personId   = Number(gotoBtn.dataset.personId);
    const geoUnitName = gotoBtn.dataset.geoUnit;
    await goToPerson(personId, geoUnitName);
    return;
  }

  if (prevBtn || nextBtn) {
    const btn        = prevBtn || nextBtn;
    const subsetName = btn.dataset.subset;
    const venueId    = Number(btn.dataset.venueId);
    const details    = btn.closest('details');
    const jumpInput  = details.querySelector('[data-action="member-jump"]');
    const currentPage = jumpInput ? Number(jumpInput.value) : 1;
    await loadMemberPage(venueId, subsetName, prevBtn ? currentPage - 1 : currentPage + 1);
    return;
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

// ── panel click dispatcher ────────────────────────────────────────────────────

async function handlePanelClick(e) {
  const gotoVenueBtn = e.target.closest('[data-action="go-to-venue"]');
  if (gotoVenueBtn) {
    e.stopPropagation();
    await goToVenue(
      Number(gotoVenueBtn.dataset.venueId),
      gotoVenueBtn.dataset.venueType,
      gotoVenueBtn.dataset.venueGeoUnit,
    );
  }
}

// ── cross-navigation ──────────────────────────────────────────────────────────

async function goToPerson(personId, geoUnitName) {
  state.highlightPersonId = personId;
  await loadUnit(geoUnitName);
}

async function goToVenue(venueId, venueType, geoUnitName) {
  state.highlightVenueId   = venueId;
  state.highlightVenueType = venueType;
  await loadUnit(geoUnitName);
}
