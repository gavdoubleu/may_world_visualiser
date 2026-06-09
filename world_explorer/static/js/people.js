import { state, PAGE_SIZE } from './state.js';
import { esc, fmt, fetchJson } from './utils.js';
import { openPersonPanel } from './person_detail.js';

export function renderPeopleSectionShell(unit) {
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

export async function loadPeople(unitId, page) {
  state.expandedPersonId = null;

  if (state.targetPeoplePage !== null) {
    page = state.targetPeoplePage;
    state.targetPeoplePage = null;
  }

  const tableWrap    = document.getElementById('people-table-wrap');
  const paginationEl = document.getElementById('people-pagination');
  if (!tableWrap) return;

  tableWrap.innerHTML = '<div style="padding:0.8rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">Loading…</div>';

  let data;
  try {
    data = await fetchJson(
      `/api/explorer/unit/${unitId}/people` +
      `?page=${page}&per_page=${PAGE_SIZE}`
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

  if (state.highlightPersonId) {
    const targetId = state.highlightPersonId;
    const found    = data.people.find(p => p.id === targetId);
    if (found) state.expandedPersonId = targetId;
    state.highlightPersonId = null;
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
