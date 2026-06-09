import { state } from './state.js';

export function pushMainHistory(unitId) {
  state.mainHistory = state.mainHistory.slice(0, state.mainHistoryIdx + 1);
  state.mainHistory.push({ unit: unitId });
  if (state.mainHistory.length > 10) state.mainHistory.shift();
  state.mainHistoryIdx = state.mainHistory.length - 1;
  updateMainNavButtons();
}

export function updateMainNavButtons() {
  const back = document.getElementById('nav-back-btn');
  const fwd  = document.getElementById('nav-fwd-btn');
  if (back) back.disabled = state.mainHistoryIdx <= 0;
  if (fwd)  fwd.disabled  = state.mainHistoryIdx >= state.mainHistory.length - 1;
}

export function pushPanelHistory(entry) {
  state.panelStack = state.panelStack.slice(0, state.panelStackIdx + 1);
  state.panelStack.push(entry);
  state.panelStackIdx = state.panelStack.length - 1;
  updatePanelNavButtons();
}

export function updatePanelNavButtons() {
  const back = document.getElementById('panel-back-btn');
  const fwd  = document.getElementById('panel-fwd-btn');
  if (back) back.disabled = state.panelStackIdx <= 0;
  if (fwd)  fwd.disabled  = state.panelStackIdx >= state.panelStack.length - 1;
}
