/**
 * Widgets: ::: {.widget src="widgets/name.js" ...}
 *
 * The module's default export is called as
 *     mount(element, options, helpers)
 * where `element` is an empty container, `options` holds the div's other attributes
 * (e.g. matrix="1,1,0,1" -> options.matrix) and `helpers` offers { loadJSXGraph, ensureId,
 * COLORS }. The ::: {.print} fallback stays visible until mount resolves without error.
 */

import { loadJSXGraph, ensureId, whenVisible, COLORS } from './jsxgraph.js';

async function mountWidget(element, version) {
    if (element.dataset.mounted) return;
    element.dataset.mounted = 'true';
    const mountPoint = element.querySelector('.widget-mount');
    const fallback = element.querySelector('.widget-fallback');
    const { src, mounted, ...options } = element.dataset;
    try {
        const module = await import(new URL(src + version, document.baseURI));
        await module.default(mountPoint, options, { loadJSXGraph, ensureId, COLORS });
        if (fallback) fallback.hidden = true;
        element.classList.add('widget-ready');
    } catch (error) {
        console.error(`Widget ${src} failed:`, error);
        mountPoint.replaceChildren();
        element.classList.add('widget-failed');
    }
}

export function init(elements, { version }) {
    for (const element of elements) {
        whenVisible(element, () => mountWidget(element, version));
    }
}
