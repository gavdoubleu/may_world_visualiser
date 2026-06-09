const { formatValue, buildDistributionSection, buildBreakdownSection } = require('../../world_map/static/js/panel_builders');

describe('formatValue', () => {
    test('returns dash for null', () => {
        expect(formatValue(null, null)).toBe('-');
    });

    test('returns dash for undefined', () => {
        expect(formatValue(undefined, 'number')).toBe('-');
    });

    test('formats integer with locale string', () => {
        expect(formatValue(1000, 'number')).toBe('1,000');
    });

    test('formats non-number with number format unchanged', () => {
        expect(formatValue('unknown', 'number')).toBe('unknown');
    });

    test('formats percentage', () => {
        expect(formatValue(0.756, 'percentage')).toBe('0.8%');
    });

    test('formats decimal', () => {
        expect(formatValue(3.14159, 'decimal')).toBe('3.14');
    });

    test('default: integer gets locale string', () => {
        expect(formatValue(5000, null)).toBe('5,000');
    });

    test('default: float gets 2dp', () => {
        expect(formatValue(3.14159, null)).toBe('3.14');
    });

    test('default: string returned as-is', () => {
        expect(formatValue('hello', null)).toBe('hello');
    });
});

describe('buildDistributionSection', () => {
    const makeSection = (overrides = {}) => ({
        source: 'age_distribution',
        show_percentage: true,
        ...overrides
    });

    const data = {
        population: 100,
        age_distribution: { '0-17': 20, '18-64': 60, '65+': 20 }
    };

    test('returns empty string when source missing', () => {
        const result = buildDistributionSection(makeSection(), {});
        expect(result).toBe('');
    });

    test('renders bar items for each group', () => {
        const result = buildDistributionSection(makeSection(), data);
        expect(result).toContain('0-17');
        expect(result).toContain('18-64');
        expect(result).toContain('65+');
    });

    test('uses denominator_field when specified', () => {
        const section = makeSection({ denominator_field: 'population' });
        const result = buildDistributionSection(section, data);
        expect(result).toContain('20.0%');
    });

    test('sums values as denominator when no denominator_field', () => {
        const result = buildDistributionSection(makeSection(), data);
        expect(result).toContain('20.0%');
    });

    test('returns empty string when denominator is zero', () => {
        const result = buildDistributionSection(makeSection(), { age_distribution: { a: 0 } });
        expect(result).toBe('');
    });

    test('sorts by count descending when sort_by=count', () => {
        const section = makeSection({ sort_by: 'count' });
        const result = buildDistributionSection(section, data);
        const pos18 = result.indexOf('18-64');
        const pos0 = result.indexOf('0-17');
        expect(pos18).toBeLessThan(pos0);
    });
});

describe('buildBreakdownSection', () => {
    const makeSection = (overrides = {}) => ({
        source: 'venue_types',
        ...overrides
    });

    const data = {
        venue_types: { school: 5, hospital: 2, park: 10 }
    };

    test('returns no-data message when source missing', () => {
        const result = buildBreakdownSection(makeSection(), {});
        expect(result).toContain('No data available');
    });

    test('renders a bar item for each type', () => {
        const result = buildBreakdownSection(makeSection(), data);
        expect(result).toContain('school');
        expect(result).toContain('hospital');
        expect(result).toContain('park');
    });

    test('park (max) gets 100% width', () => {
        const result = buildBreakdownSection(makeSection(), data);
        expect(result).toContain('width: 100.0%');
    });

    test('respects max_items', () => {
        const section = makeSection({ max_items: 2, sort_by: 'count', sort_order: 'desc' });
        const result = buildBreakdownSection(section, data);
        expect(result).toContain('park');
        expect(result).toContain('school');
        expect(result).not.toContain('hospital');
    });
});
