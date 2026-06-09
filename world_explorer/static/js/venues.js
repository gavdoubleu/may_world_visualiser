import { state, PAGE_SIZE } from './state.js';
import { esc, fmt, fetchJson } from './utils.js';
import { openVenueDetailsPanel } from './venue_detail.js';

export function renderVenuesSection() {
  const unit        = state.currentUnit;
  const venueTypes  = unit.venue_types || {};
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
  const jumpToChildrenPage = async (input) => {
    const parentId = Number(input.dataset.parentId);
    const total    = Number(input.dataset.total);
    const page     = Math.max(1, Math.min(Number(input.value), total));
    if (parentId && page) await fetchVenueChildren(parentId, page);
  };
  venuesContainer.addEventListener('keydown', async (e) => {
    const venueInput    = e.target.closest('[data-action="venue-jump"]');
    const childrenInput = e.target.closest('[data-action="venue-children-jump"]');
    if (venueInput    && e.key === 'Enter') await jumpToVenuePage(venueInput);
    if (childrenInput && e.key === 'Enter') await jumpToChildrenPage(childrenInput);
  });
  venuesContainer.addEventListener('change', async (e) => {
    const venueInput    = e.target.closest('[data-action="venue-jump"]');
    const childrenInput = e.target.closest('[data-action="venue-children-jump"]');
    if (venueInput)    await jumpToVenuePage(venueInput);
    if (childrenInput) await jumpToChildrenPage(childrenInput);
  });

  if (state.highlightVenueId && state.highlightVenueType) {
    const targetType = state.highlightVenueType;
    const targetId   = state.highlightVenueId;
    const targetPage = state.highlightVenuePage || 1;
    const childId    = state.highlightChildVenueId;
    const childPage  = state.highlightChildPage || 1;
    state.highlightVenueId       = null;
    state.highlightVenueType     = null;
    state.highlightVenuePage     = null;
    state.highlightParentVenueId = null;
    state.highlightChildVenueId  = null;
    state.highlightChildPage     = null;

    const vs = state.venueStates[targetType] || { open: false, page: 1, items: [], total: 0, loading: true };
    vs.open = true;
    state.venueStates[targetType] = vs;
    renderVenuesSection();
    fetchVenuePage(state.selectedUnit, targetType, targetPage).then(() => {
      const vs2 = state.venueStates[targetType];
      if (!vs2 || vs2.items.length === 0) return;
      state.expandedVenueId = targetId;
      renderVenuesSection();

      if (childId) {
        const cs = state.childrenStates[targetId] || { open: true, page: 1, items: [], total: 0, totalPages: 1, loading: true };
        state.childrenStates[targetId] = cs;
        renderVenuesSection();
        fetchVenueChildren(targetId, childPage).then(() => {
          state.expandedChildVenueId = childId;
          renderVenuesSection();
          document.querySelector(`[data-venue-id="${childId}"]`)
            ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
      } else {
        document.querySelector(`[data-venue-id="${targetId}"]`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }
}

function buildVenueListHtml(type, vs) {
  if (vs.items.length === 0) {
    const message = vs.loading ? 'Loading…' : 'No venues found.';
    return `<div style="padding:0.6rem 1rem;font-size:0.8rem;color:var(--theme-text-muted)">${message}</div>`;
  }

  const itemsHtml = vs.items.map(v => {
    const isExpanded = state.expandedVenueId === v.id;
    const childCount = v.child_count || 0;
    const childBadge = childCount > 0
      ? `<span class="venue-child-count">${fmt(childCount)} sub-venues · ${fmt(v.total_child_members)} members</span>`
      : '';
    const expandHtml = isExpanded ? buildVenueExpandHtml(v) : '';
    return `
      <div class="venue-item${isExpanded ? ' expanded' : ''}"
           data-action="toggle-venue" data-venue-id="${v.id}">
        <span class="venue-item__toggle">${isExpanded ? '▼' : '▶'}</span>
        <span class="venue-item__name">${esc(v.name)}</span>
        ${childBadge}
      </div>
      ${expandHtml}`;
  }).join('');

  const showing = vs.items.length + (vs.page - 1) * PAGE_SIZE;
  const paginationHtml = vs.total > vs.per_page * vs.page || vs.page > 1
    ? buildVenuePaginationHtml(type, vs)
    : '';

  return itemsHtml + paginationHtml;
}

function buildVenueExpandHtml(venue) {
  if ((venue.child_count || 0) > 0) {
    return buildParentVenueExpandHtml(venue);
  }
  return buildLeafVenueExpandHtml(venue);
}

function buildLeafVenueExpandHtml(venue) {
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

function buildParentVenueExpandHtml(venue) {
  const cs = state.childrenStates[venue.id] || { open: false, page: 1, items: [], total: 0, totalPages: 1, loading: true };

  let childrenHtml = '';
  if (cs.loading && cs.items.length === 0) {
    childrenHtml = '<div class="venue-children-loading">Loading…</div>';
  } else if (cs.items.length === 0) {
    childrenHtml = '<div class="venue-children-loading">No sub-venues found.</div>';
  } else {
    const rows = cs.items.map(child => {
      const isChildExpanded = state.expandedChildVenueId === child.id;
      const childExpandHtml = isChildExpanded ? buildLeafVenueExpandHtml(child) : '';
      return `
        <div class="venue-child-item${isChildExpanded ? ' expanded' : ''}"
             data-action="toggle-child-venue" data-venue-id="${child.id}">
          <span class="venue-item__toggle">${isChildExpanded ? '▼' : '▶'}</span>
          <span class="venue-item__name">${esc(child.name)}</span>
        </div>
        ${isChildExpanded ? childExpandHtml.replace('venue-subsets', 'venue-child-subsets') : ''}`;
    }).join('');

    const totalPages = Math.max(1, Math.ceil(cs.total / (cs.per_page || PAGE_SIZE)));
    const showing    = cs.items.length + (cs.page - 1) * (cs.per_page || PAGE_SIZE);
    const paginationHtml = cs.total > (cs.per_page || PAGE_SIZE) || cs.page > 1
      ? `<div class="venue-pagination venue-children-pagination">
           <span>Showing ${fmt(showing)} of ${fmt(cs.total)}</span>
           ${cs.page > 1 ? `<button data-action="venue-children-prev" data-parent-id="${venue.id}" style="margin-left:auto">← Prev</button>` : ''}
           <input type="number" class="page-input" data-action="venue-children-jump"
                  data-parent-id="${venue.id}" data-total="${totalPages}"
                  value="${cs.page}" min="1" max="${totalPages}">
           ${showing < cs.total ? `<button data-action="venue-children-next" data-parent-id="${venue.id}">Next →</button>` : ''}
         </div>`
      : '';

    childrenHtml = rows + paginationHtml;
  }

  return `
    <div class="venue-subsets venue-parent-expand">
      <div class="venue-children">${childrenHtml}</div>
      <div style="padding-top:0.3rem">
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
  const showing    = vs.items.length + (vs.page - 1) * PAGE_SIZE;
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
  const openDetails      = e.target.closest('[data-action="open-venue-details"]');
  const toggleGroup      = e.target.closest('[data-action="toggle-venue-group"]');
  const toggleVenue      = e.target.closest('[data-action="toggle-venue"]');
  const toggleChildVenue = e.target.closest('[data-action="toggle-child-venue"]');
  const venuePrev        = e.target.closest('[data-action="venue-prev"]');
  const venueNext        = e.target.closest('[data-action="venue-next"]');
  const childrenPrev     = e.target.closest('[data-action="venue-children-prev"]');
  const childrenNext     = e.target.closest('[data-action="venue-children-next"]');
  const childrenJump     = e.target.closest('[data-action="venue-children-jump"]');

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
    const vs = state.venueStates[type] || { open: false, page: 1, items: [], total: 0, loading: true };
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
    const venueId    = Number(toggleVenue.dataset.venueId);
    const wasExpanded = state.expandedVenueId === venueId;
    state.expandedVenueId       = wasExpanded ? null : venueId;
    state.expandedChildVenueId  = null;
    renderVenuesSection();
    if (!wasExpanded) {
      let venue = null;
      for (const vs of Object.values(state.venueStates)) {
        venue = (vs.items || []).find(v => v.id === venueId);
        if (venue) break;
      }
      if (venue && (venue.child_count || 0) > 0) {
        const cs = state.childrenStates[venueId] || { open: true, page: 1, items: [], total: 0, totalPages: 1, loading: true };
        state.childrenStates[venueId] = cs;
        if (cs.items.length === 0) {
          renderVenuesSection();
          await fetchVenueChildren(venueId, 1);
        }
      }
    }
    return;
  }

  if (toggleChildVenue) {
    const childId = Number(toggleChildVenue.dataset.venueId);
    state.expandedChildVenueId = state.expandedChildVenueId === childId ? null : childId;
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

  if (childrenPrev) {
    const parentId = Number(childrenPrev.dataset.parentId);
    const cs = state.childrenStates[parentId];
    if (cs && cs.page > 1) await fetchVenueChildren(parentId, cs.page - 1);
    return;
  }

  if (childrenNext) {
    const parentId = Number(childrenNext.dataset.parentId);
    const cs = state.childrenStates[parentId];
    if (cs) await fetchVenueChildren(parentId, cs.page + 1);
    return;
  }

  if (childrenJump) {
    e.stopPropagation();
  }
}

export async function fetchVenuePage(unitId, type, page) {
  const vs = state.venueStates[type] || { open: true, page: 1, items: [], total: 0 };
  vs.loading = true;
  state.venueStates[type] = vs;
  renderVenuesSection();

  try {
    const data = await fetchJson(
      `/api/explorer/unit/${unitId}/venues` +
      `?type=${encodeURIComponent(type)}&page=${page}&per_page=${PAGE_SIZE}`
    );
    vs.items      = data.venues;
    vs.total      = data.total_count;
    vs.totalPages = data.total_pages;
    vs.page       = page;
    vs.per_page   = data.per_page;
    vs.loading    = false;
  } catch (err) {
    vs.items   = [];
    vs.total   = 0;
    vs.loading = false;
  }
  renderVenuesSection();
}

export async function fetchVenueChildren(parentVenueId, page) {
  const cs = state.childrenStates[parentVenueId] || { open: true, page: 1, items: [], total: 0, totalPages: 1, loading: true };
  cs.loading = true;
  state.childrenStates[parentVenueId] = cs;
  renderVenuesSection();

  try {
    const data = await fetchJson(
      `/api/explorer/venue/${parentVenueId}/children?page=${page}&per_page=${PAGE_SIZE}`
    );
    cs.items      = data.venues;
    cs.total      = data.total_count;
    cs.totalPages = data.total_pages;
    cs.page       = page;
    cs.per_page   = data.per_page;
    cs.loading    = false;
  } catch (err) {
    cs.items   = [];
    cs.total   = 0;
    cs.loading = false;
  }
  renderVenuesSection();
}
