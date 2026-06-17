// PanelNavigator — pure view-history stack for the info panel. No DOM, no fetch.
// A "view" is an opaque descriptor (e.g. { type: 'unit', unitName }); the
// navigator only tracks order, callers decide how to render a view.

function createPanelNavigator() {
    const stack = [];

    function reset(view) {
        stack.length = 0;
        stack.push(view);
        return view;
    }

    function push(view) {
        stack.push(view);
        return view;
    }

    function pop() {
        if (stack.length > 1) stack.pop();
        return current();
    }

    function current() {
        return stack[stack.length - 1];
    }

    return { reset, push, pop, current };
}

if (typeof module !== 'undefined') {
    module.exports = { createPanelNavigator };
}
if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, {
        createPanelNavigator,
        panelNavigator: createPanelNavigator(),
    });
}
