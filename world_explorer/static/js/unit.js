import { state } from './state.js';
import { esc, fmt, fetchJson } from './utils.js';
import { pushMainHistory } from './navigation.js';
import { renderVenuesSection } from './venues.js';
import { renderPeopleSectionShell, loadPeople } from './people.js';
import { rerenderTree } from './tree.js';

export async function loadUnit(unitId, { pushHistory = true } = {}) {
  if (state.selectedUnit === unitId && pushHistory &&
      !state.highlightPersonId && !state.highlightVenueId) return;

  if (pushHistory) pushMainHistory(unitId);

  state.selectedUnit         = unitId;
  state.currentUnit          = null;
  state.venueStates          = {};
  state.expandedVenueId      = null;
  state.expandedChildVenueId = null;
  state.childrenStates       = {};
  state.expandedPersonId     = null;
  state.peopleData           = null;
  rerenderTree();

  const placeholder = document.getElementById('unit-placeholder');
  const detail      = document.getElementById('unit-detail');
  placeholder.hidden = true;
  detail.hidden      = false;

  setDetailLoading();

  try {
    state.currentUnit = await fetchJson(`/api/explorer/unit/${unitId}`);
  } catch (err) {
    detail.innerHTML = `<div style="padding:2rem;color:var(--theme-text-muted)">Error: ${esc(err.message)}</div>`;
    return;
  }

  renderUnitHeader(state.currentUnit);
  renderStatsStrip(state.currentUnit);
  renderDistributions(state.currentUnit);
  renderVenuesSection();
  renderPeopleSectionShell(state.currentUnit);

  loadPeople(unitId, 1);
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
    ? `<span class="parent-link" data-action="select-unit" data-unit-id="${unit.parent.id}">
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
    if (el) loadUnit(Number(el.dataset.unitId));
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
