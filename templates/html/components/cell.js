/**
 * Runnable Python cells, executed in the browser by Pyodide in a Web Worker.
 *
 * All cells on a page share one Python namespace, like a notebook. Running a cell first
 * runs any earlier cells that have not run yet, so later cells can use earlier variables.
 * Pyodide (and the packages a cell imports) is downloaded on the first Run.
 */

const PYODIDE_INDEX_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';

let worker = null;
let nextRequest = 0;
const requests = new Map();          // request id -> {resolve, reject}
let queue = Promise.resolve();       // cells run one at a time, in click order
let cells = [];
let assetVersion = '';            // "?v=<hash>" for the worker script
const executed = new Set();          // cells run in the current Python session

function startWorker(version) {
    worker = new Worker(new URL(`pyodide-worker.js${version}`, import.meta.url), { type: 'module' });
    worker.onmessage = event => {
        const { id, ...message } = event.data;
        const request = requests.get(id);
        if (!request) return;
        if (message.type === 'progress') { request.onProgress?.(message.text); return; }
        requests.delete(id);
        message.type === 'failed' ? request.reject(new Error(message.error)) : request.resolve(message);
    };
    worker.onerror = event => {
        for (const request of requests.values()) request.reject(new Error(event.message || 'Python worker failed'));
        requests.clear();
    };
    return send({ type: 'init', indexURL: PYODIDE_INDEX_URL });
}

function send(message, onProgress) {
    const id = nextRequest++;
    return new Promise((resolve, reject) => {
        requests.set(id, { resolve, reject, onProgress });
        worker.postMessage({ id, ...message });
    });
}

function stopWorker() {
    if (worker) worker.terminate();
    worker = null;
    for (const request of requests.values()) request.reject(new Error('Stopped'));
    requests.clear();
    executed.clear();
    queue = Promise.resolve();
    for (const cell of cells) setRunning(cell, false);
}

// ---------------------------------------------------------------------------
// Cell UI
// ---------------------------------------------------------------------------

function parts(cell) {
    return {
        run: cell.querySelector('.code-cell-run'),
        reset: cell.querySelector('.code-cell-reset'),
        status: cell.querySelector('.code-cell-status'),
        output: cell.querySelector('.code-cell-output'),
    };
}

function currentCode(cell) {
    const editor = cell.querySelector('textarea.code-cell-editor');
    return editor ? editor.value : cell.dataset.originalCode;
}

function setRunning(cell, running) {
    const { run } = parts(cell);
    run.textContent = running ? 'Stop' : 'Run';
    run.classList.toggle('running', running);
    cell.classList.toggle('running', running);
}

/** Replace the highlighted listing with a plain editor the first time the code is clicked. */
function makeEditable(cell) {
    const listing = cell.querySelector('div.sourceCode, pre');
    if (!listing || cell.querySelector('textarea.code-cell-editor')) return;
    const editor = document.createElement('textarea');
    editor.className = 'code-cell-editor';
    editor.spellcheck = false;
    editor.value = cell.dataset.originalCode;
    const resize = () => { editor.style.height = 'auto'; editor.style.height = editor.scrollHeight + 'px'; };
    editor.addEventListener('input', () => { resize(); parts(cell).reset.hidden = editor.value === cell.dataset.originalCode; });
    editor.addEventListener('keydown', event => {
        if (event.key === 'Enter' && event.shiftKey) {
            event.preventDefault();
            runFromButton(cell);
        } else if (event.key === 'Tab' && !event.shiftKey) {
            event.preventDefault();
            editor.setRangeText('    ', editor.selectionStart, editor.selectionEnd, 'end');
            editor.dispatchEvent(new Event('input'));
        }
    });
    listing.replaceWith(editor);
    resize();
    editor.focus();
}

function showOutput(cell, result) {
    const { output } = parts(cell);
    output.replaceChildren();
    const addText = (text, className) => {
        if (!text) return;
        const pre = document.createElement('pre');
        pre.className = className;
        pre.textContent = text;
        output.append(pre);
    };
    addText(result.stdout, 'code-cell-stdout');
    addText(result.stderr, 'code-cell-stderr');
    addText(result.result, 'code-cell-result');
    for (const png of result.figures || []) {
        const img = document.createElement('img');
        img.className = 'code-cell-figure';
        img.alt = 'Figure produced by the code';
        img.src = `data:image/png;base64,${png}`;
        output.append(img);
    }
    addText(result.error, 'code-cell-error');
    output.hidden = output.childElementCount === 0;
}

async function runCell(cell) {
    const { status, output } = parts(cell);
    setRunning(cell, true);
    status.textContent = 'Running…';
    try {
        const result = await send(
            { type: 'run', code: currentCode(cell), packages: cell.dataset.packages || '' },
            text => { status.textContent = text; },
        );
        showOutput(cell, result);
        status.textContent = result.error ? 'Error' : '';
        executed.add(cell);
        return !result.error;
    } catch (error) {
        showOutput(cell, { error: error.message });
        status.textContent = error.message === 'Stopped' ? 'Stopped' : 'Error';
        output.hidden = error.message === 'Stopped';
        return false;
    } finally {
        setRunning(cell, false);
    }
}

function runFromButton(cell) {
    if (cell.classList.contains('running')) {
        stopWorker();
        return;
    }
    const target = cells.indexOf(cell);
    queue = queue.then(async () => {
        if (!worker) {
            parts(cell).status.textContent = 'Starting Python…';
            setRunning(cell, true);
            try {
                await startWorker(assetVersion);
            } catch (error) {
                setRunning(cell, false);
                parts(cell).status.textContent = 'Could not start Python';
                showOutput(cell, { error: error.message });
                return;
            }
        }
        // Earlier cells that have not run yet, then this one
        for (const earlier of cells.slice(0, target)) {
            if (!executed.has(earlier) && !(await runCell(earlier))) return;
        }
        await runCell(cell);
    });
}

export function init(elements, { version }) {
    assetVersion = version;
    cells = elements;
    for (const cell of cells) {
        const code = cell.querySelector('code');
        cell.dataset.originalCode = code ? code.textContent.replace(/\n$/, '') : '';
        const { run, reset } = parts(cell);
        run.addEventListener('click', () => runFromButton(cell));
        reset.addEventListener('click', () => {
            const editor = cell.querySelector('textarea.code-cell-editor');
            if (editor) { editor.value = cell.dataset.originalCode; editor.dispatchEvent(new Event('input')); }
        });
        const listing = cell.querySelector('div.sourceCode, pre');
        listing?.addEventListener('click', () => makeEditable(cell));
        listing?.setAttribute('title', 'Click to edit');
    }
}
