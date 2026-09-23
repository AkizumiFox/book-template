/**
 * Function plots: ::: {.plot fn="sin(a*x)" x="-6.28,6.28" y="-2,2" params="a=1:0..3"}
 * One curve per ;-separated expression, and one slider per parameter.
 */

import { compile, parseParams, parseRange } from './expression.js';
import { loadJSXGraph, ensureId, whenVisible, COLORS } from './jsxgraph.js';

function formatValue(value) {
    return String(Math.round(value * 1000) / 1000);
}

/** Choose a y range by sampling the curves when the author gave none. */
function autoRange(functions, scope, xmin, xmax) {
    const values = [];
    for (let i = 0; i <= 200; i++) {
        const x = xmin + (xmax - xmin) * i / 200;
        for (const f of functions) {
            const y = f({ ...scope, x });
            if (Number.isFinite(y)) values.push(y);
        }
    }
    if (!values.length) return [-1, 1];
    values.sort((a, b) => a - b);
    // Ignore the extreme 2% on each side so asymptotes do not flatten the plot
    let low = values[Math.floor(values.length * 0.02)], high = values[Math.ceil(values.length * 0.98) - 1];
    if (high - low < 1e-9) { low -= 1; high += 1; }
    const pad = (high - low) * 0.1;
    return [low - pad, high + pad];
}

function showError(element, message) {
    const board = element.querySelector('.plot-board');
    board.classList.add('plot-error');
    board.textContent = `Plot error: ${message}`;
}

async function render(element) {
    if (element.dataset.rendered) return;
    element.dataset.rendered = 'true';
    let params, functions, xRange;
    try {
        params = parseParams(element.dataset.params);
        const names = params.map(p => p.name);
        functions = (element.dataset.fn || '').split(';').filter(s => s.trim()).map(source => compile(source, names));
        if (!functions.length) throw new Error('missing fn');
        xRange = parseRange(element.dataset.x || '-5,5');
        if (!xRange) throw new Error('bad x range');
    } catch (error) {
        showError(element, error.message);
        return;
    }

    const JXG = await loadJSXGraph();
    const scope = Object.fromEntries(params.map(p => [p.name, p.value]));
    const [xmin, xmax] = xRange;
    const [ymin, ymax] = parseRange(element.dataset.y) || autoRange(functions, scope, xmin, xmax);

    const boardElement = element.querySelector('.plot-board');
    const board = JXG.JSXGraph.initBoard(ensureId(boardElement), {
        boundingbox: [xmin, ymax, xmax, ymin],
        axis: true,
        keepAspectRatio: false,
        showCopyright: false,
        showNavigation: false,
        pan: { enabled: false },
        zoom: { enabled: false },
    });
    functions.forEach((f, i) => {
        board.create('functiongraph', [x => f({ ...scope, x }), xmin, xmax], {
            strokeColor: COLORS[i % COLORS.length], strokeWidth: 2, highlight: false,
        });
    });

    const controls = element.querySelector('.plot-controls');
    for (const param of params) {
        const label = document.createElement('label');
        label.className = 'plot-slider';
        const name = document.createElement('span');
        name.className = 'plot-slider-name';
        name.textContent = param.name;
        const input = document.createElement('input');
        // A power-of-ten step (0.01 for a range of 3) so round values like 1 or 0.5 can be selected
        const step = Math.pow(10, Math.floor(Math.log10((param.max - param.min) / 100)));
        Object.assign(input, { type: 'range', min: param.min, max: param.max, step, value: param.value });
        input.setAttribute('aria-label', `Parameter ${param.name}`);
        const value = document.createElement('output');
        value.textContent = formatValue(param.value);
        input.addEventListener('input', () => {
            scope[param.name] = parseFloat(input.value);
            value.textContent = formatValue(scope[param.name]);
            board.update();
        });
        label.append(name, input, value);
        controls.append(label);
    }
}

export function init(elements) {
    for (const element of elements) {
        whenVisible(element, () => render(element).catch(error => showError(element, error.message)));
    }
}
