const { calculateMarkerRadius, getPopulationColor } = require('../../world_map/static/js/geography');

describe('calculateMarkerRadius', () => {
    test('uses default when no config', () => {
        const r = calculateMarkerRadius(100, null);
        expect(r).toBeGreaterThanOrEqual(5);
        expect(r).toBeLessThanOrEqual(15);
    });

    test('sqrt method: scales with population', () => {
        const small = calculateMarkerRadius(100, { method: 'sqrt', min_radius: 2, max_radius: 30, scale: 1 });
        const large = calculateMarkerRadius(10000, { method: 'sqrt', min_radius: 2, max_radius: 30, scale: 1 });
        expect(large).toBeGreaterThan(small);
    });

    test('clamps to min_radius', () => {
        const r = calculateMarkerRadius(0, { method: 'sqrt', min_radius: 5, max_radius: 15, scale: 0.5 });
        expect(r).toBe(5);
    });

    test('clamps to max_radius', () => {
        const r = calculateMarkerRadius(1e12, { method: 'sqrt', min_radius: 5, max_radius: 15, scale: 0.5 });
        expect(r).toBe(15);
    });

    test('log method returns value in range', () => {
        const r = calculateMarkerRadius(1000, { method: 'log', min_radius: 2, max_radius: 20, scale: 1 });
        expect(r).toBeGreaterThanOrEqual(2);
        expect(r).toBeLessThanOrEqual(20);
    });

    test('linear method returns value in range', () => {
        const r = calculateMarkerRadius(500, { method: 'linear', min_radius: 2, max_radius: 20, scale: 1 });
        expect(r).toBeGreaterThanOrEqual(2);
        expect(r).toBeLessThanOrEqual(20);
    });

    test('unknown method falls back to sqrt', () => {
        const r1 = calculateMarkerRadius(1000, { method: 'bogus', min_radius: 2, max_radius: 30, scale: 1 });
        const r2 = calculateMarkerRadius(1000, { method: 'sqrt', min_radius: 2, max_radius: 30, scale: 1 });
        expect(r1).toBe(r2);
    });
});

describe('getPopulationColor', () => {
    test('returns default color for zero population', () => {
        expect(getPopulationColor(0, null)).toBe('#FFEDA0');
    });

    test('returns darker color for large population', () => {
        expect(getPopulationColor(50000, null)).toBe('#800026');
    });

    test('uses threshold config when provided', () => {
        const colorConfig = {
            thresholds: [
                { value: null, color: '#aaa' },
                { value: 100, color: '#bbb' },
                { value: 1000, color: '#ccc' }
            ]
        };
        expect(getPopulationColor(500, colorConfig)).toBe('#bbb');
        expect(getPopulationColor(5000, colorConfig)).toBe('#ccc');
        expect(getPopulationColor(0, colorConfig)).toBe('#aaa');
    });
});
