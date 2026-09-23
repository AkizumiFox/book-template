/** Loads JSXGraph once, on demand (shared by plots and widgets). */

const JSXGRAPH_URL = 'https://cdn.jsdelivr.net/npm/jsxgraph@1.13.3/distrib/';

let loading = null;

export function loadJSXGraph() {
    if (!loading) {
        loading = new Promise((resolve, reject) => {
            const style = document.createElement('link');
            style.rel = 'stylesheet';
            style.href = JSXGRAPH_URL + 'jsxgraph.css';
            document.head.append(style);

            const script = document.createElement('script');
            script.src = JSXGRAPH_URL + 'jsxgraphcore.js';
            script.onload = () => resolve(window.JXG);
            script.onerror = () => reject(new Error('Could not load JSXGraph'));
            document.head.append(script);
        });
    }
    return loading;
}

let boardCount = 0;

/** JSXGraph needs an element id; give the element one if it has none. */
export function ensureId(element) {
    if (!element.id) element.id = `jxg-board-${++boardCount}`;
    return element.id;
}

/** Call `callback` the first time `element` comes near the viewport. */
export function whenVisible(element, callback) {
    if (!('IntersectionObserver' in window)) { callback(); return; }
    const observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
            observer.disconnect();
            callback();
        }
    }, { rootMargin: '200px' });
    observer.observe(element);
}

export const COLORS = ['#3b6eda', '#c94c6c', '#3a8a3a', '#d97706'];
