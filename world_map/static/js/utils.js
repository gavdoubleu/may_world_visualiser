function getFieldValue(obj, path) {
    if (!path) return undefined;

    const parts = path.split('.');
    let value = obj;

    for (const part of parts) {
        if (value === null || value === undefined) return undefined;
        value = value[part];
    }

    return value;
}

if (typeof module !== 'undefined') module.exports = { getFieldValue };
if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    window.WorldMap.getFieldValue = getFieldValue;
}
