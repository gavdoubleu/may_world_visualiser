const { createPanelNavigator } = require('../../world_map/static/js/panel_navigator');

describe('PanelNavigator', () => {
    test('reset sets a single root view as current', () => {
        const nav = createPanelNavigator();
        nav.reset({ type: 'unit', unitName: 'A' });
        expect(nav.current()).toEqual({ type: 'unit', unitName: 'A' });
    });

    test('push makes the new view current, pop returns to the previous one', () => {
        const nav = createPanelNavigator();
        nav.reset({ type: 'unit', unitName: 'A' });
        nav.push({ type: 'people', unitName: 'A', page: 1 });
        expect(nav.current()).toEqual({ type: 'people', unitName: 'A', page: 1 });

        nav.pop();
        expect(nav.current()).toEqual({ type: 'unit', unitName: 'A' });
    });

    test('pop on a single-item stack is a no-op', () => {
        const nav = createPanelNavigator();
        nav.reset({ type: 'unit', unitName: 'A' });
        nav.pop();
        expect(nav.current()).toEqual({ type: 'unit', unitName: 'A' });
    });

    test('reset clears any existing stack before pushing the new root', () => {
        const nav = createPanelNavigator();
        nav.reset({ type: 'unit', unitName: 'A' });
        nav.push({ type: 'people', unitName: 'A', page: 1 });
        nav.reset({ type: 'unit', unitName: 'B' });

        expect(nav.current()).toEqual({ type: 'unit', unitName: 'B' });
        nav.pop();
        expect(nav.current()).toEqual({ type: 'unit', unitName: 'B' });
    });

    test('cross-navigation: pop returns to the actual predecessor, not a fixed ancestor', () => {
        const nav = createPanelNavigator();
        nav.reset({ type: 'unit', unitName: 'A' });
        nav.push({ type: 'people', unitName: 'A', page: 1 });
        nav.push({ type: 'person', personId: 7 });
        nav.push({ type: 'venue', venueId: 42 }); // cross-nav from person's activity map

        nav.pop();
        expect(nav.current()).toEqual({ type: 'person', personId: 7 });

        nav.pop();
        expect(nav.current()).toEqual({ type: 'people', unitName: 'A', page: 1 });

        nav.pop();
        expect(nav.current()).toEqual({ type: 'unit', unitName: 'A' });
    });
});
