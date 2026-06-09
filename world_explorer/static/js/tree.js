import { state } from './state.js';
import { esc, fmt, fetchJson } from './utils.js';
import { loadUnit } from './unit.js';

export async function loadTree() {
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

export function rerenderTree() {
  const roots = Object.values(state.nodeMap).filter(n => n.parent_id === null);
  document.getElementById('geo-tree').innerHTML = renderNodeList(roots, 0);
}

function renderNodeList(nodes, depth) {
  return nodes.map(n => renderNode(n, depth)).join('');
}

function renderNode(node, depth) {
  const hasChildren = node.children.length > 0;
  const isExpanded  = state.expandedIds.has(node.id);
  const isSelected  = state.selectedUnit === node.id;
  const indent      = (0.5 + depth * 0.9) + 'rem';

  return `
    <li class="tree-node">
      <div class="tree-node__row${isSelected ? ' selected' : ''}"
           style="padding-left:${indent}"
           data-action="select" data-unit-id="${node.id}">
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
    loadUnit(Number(selectEl.dataset.unitId));
  }
}
