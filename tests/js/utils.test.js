const { getFieldValue } = require('../../world_map/static/js/utils');

describe('getFieldValue', () => {
    test('returns top-level value', () => {
        expect(getFieldValue({ name: 'London' }, 'name')).toBe('London');
    });

    test('returns nested value via dot path', () => {
        expect(getFieldValue({ geo: { level: 'region' } }, 'geo.level')).toBe('region');
    });

    test('returns undefined for missing key', () => {
        expect(getFieldValue({ name: 'London' }, 'population')).toBeUndefined();
    });

    test('returns undefined when intermediate key is null', () => {
        expect(getFieldValue({ geo: null }, 'geo.level')).toBeUndefined();
    });

    test('returns undefined for empty path', () => {
        expect(getFieldValue({ name: 'London' }, '')).toBeUndefined();
    });

    test('handles three-level path', () => {
        expect(getFieldValue({ a: { b: { c: 42 } } }, 'a.b.c')).toBe(42);
    });
});
