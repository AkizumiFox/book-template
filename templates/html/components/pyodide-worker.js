/**
 * Web Worker running Pyodide for code cells (see cell.js). Started as a module worker:
 * current Pyodide releases refuse to run in classic workers.
 *
 * Messages in:  {id, type: 'init', indexURL} | {id, type: 'run', code, packages}
 * Messages out: {id, type: 'ready'} | {id, type: 'progress', text}
 *               {id, type: 'result', stdout, stderr, result, figures, error} | {id, type: 'failed', error}
 */

let pyodideReady = null;

const RUNNER = `
import base64, io, sys, traceback, warnings
from pyodide.code import eval_code_async

warnings.filterwarnings("ignore", message=".*non-interactive.*")

async def __book_run_cell(source):
    try:
        value = await eval_code_async(source, globals(), filename="<cell>")
    except BaseException as exc:
        tb = exc.__traceback__
        while tb is not None and tb.tb_frame.f_code.co_filename != "<cell>":
            tb = tb.tb_next
        return {"error": "".join(traceback.format_exception(type(exc), exc, tb))}
    figures = []
    pyplot = sys.modules.get("matplotlib.pyplot")
    if pyplot is not None:
        # Warnings from the export itself are not the reader's concern
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for number in pyplot.get_fignums():
                buffer = io.BytesIO()
                pyplot.figure(number).savefig(buffer, format="png", dpi=110, bbox_inches="tight")
                figures.append(base64.b64encode(buffer.getvalue()).decode())
        pyplot.close("all")
    return {"result": None if value is None else repr(value), "figures": figures}
`;

async function initialize(indexURL) {
    const { loadPyodide } = await import(indexURL + 'pyodide.mjs');
    const pyodide = await loadPyodide({ indexURL });
    // No display in a worker: render matplotlib figures to images
    pyodide.runPython("import os; os.environ['MPLBACKEND'] = 'Agg'");
    await pyodide.runPythonAsync(RUNNER);
    return pyodide;
}

async function run(id, code, packages) {
    const pyodide = await pyodideReady;
    const progress = text => postMessage({ id, type: 'progress', text });

    const stdout = [], stderr = [];
    pyodide.setStdout({ batched: text => stdout.push(text) });
    pyodide.setStderr({ batched: text => stderr.push(text) });

    const requested = packages.split(',').map(p => p.trim()).filter(Boolean);
    if (requested.length) {
        progress(`Loading ${requested.join(', ')}…`);
        await pyodide.loadPackage(requested, { messageCallback: () => {} });
    }
    progress('Loading packages…');
    await pyodide.loadPackagesFromImports(code, { messageCallback: () => {} });
    progress('Running…');

    const runner = pyodide.globals.get('__book_run_cell');
    const proxy = await runner(code);
    runner.destroy();
    const result = proxy.toJs({ dict_converter: Object.fromEntries });
    proxy.destroy();
    return { stdout: stdout.join('\n'), stderr: stderr.join('\n'), ...result };
}

self.onmessage = async event => {
    const { id, type } = event.data;
    try {
        if (type === 'init') {
            pyodideReady = pyodideReady || initialize(event.data.indexURL);
            await pyodideReady;
            postMessage({ id, type: 'ready' });
        } else if (type === 'run') {
            const result = await run(id, event.data.code, event.data.packages || '');
            postMessage({ id, type: 'result', ...result });
        }
    } catch (error) {
        postMessage({ id, type: 'failed', error: String(error && error.message || error) });
    }
};
