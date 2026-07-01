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

function clampPageNumber(rawValue, totalPages) {
    const page = Math.trunc(Number(rawValue));
    if (!Number.isFinite(page) || page < 1) return null;
    return Math.min(page, Math.max(1, totalPages));
}

function buildPaginationHtml(page, totalPages, onChangeExpr) {
    const jumpHandler = onChangeExpr.replace('__PAGE__', 'this.value');
    return `
        <div class="pagination">
            <button class="pagination-btn" ${page <= 1 ? 'disabled' : ''} onclick="${onChangeExpr.replace('__PAGE__', page - 1)}">
                &larr; Prev
            </button>
            <span class="pagination-info">
                Page <input type="number" class="page-input" min="1" max="${totalPages}" value="${page}"
                    onchange="${jumpHandler}"
                    onkeydown="if (event.key === 'Enter') { ${jumpHandler} }">
                of ${totalPages}
            </span>
            <button class="pagination-btn" ${page >= totalPages ? 'disabled' : ''} onclick="${onChangeExpr.replace('__PAGE__', page + 1)}">
                Next &rarr;
            </button>
        </div>
    `;
}

if (typeof module !== 'undefined') module.exports = { getFieldValue, clampPageNumber, buildPaginationHtml };
if (typeof window !== 'undefined') {
    window.WorldMap = window.WorldMap || {};
    Object.assign(window.WorldMap, { getFieldValue, clampPageNumber, buildPaginationHtml });
}
