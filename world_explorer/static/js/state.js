export const PAGE_SIZE = 20;

export const state = {
  nodeMap:           {},
  expandedIds:       new Set(),
  selectedUnit:      null,
  currentUnit:       null,
  venueStates:       {},
  expandedVenueId:   null,
  expandedChildVenueId: null,
  childrenStates:    {},   // {parentVenueId: {open, page, items, total, totalPages, per_page, loading}}
  expandedPersonId:  null,
  peopleData:        null,
  highlightPersonId: null,
  highlightVenueId:  null,
  highlightVenueType: null,
  highlightVenuePage: null,
  highlightParentVenueId: null,
  highlightChildVenueId:  null,
  highlightChildPage:     null,
  targetPeoplePage:   null,

  mainHistory:    [],   // [{unit}], max 10
  mainHistoryIdx: -1,

  panelStack:    [],    // [{type, id, name}]
  panelStackIdx: -1,
};
