/**
 * Renders TeX in built HTML with MathJax (CommonHTML output), so pages need no math JavaScript.
 * Called by build/math.py with a JSON job on stdin:
 *
 *   {
 *     "mathjax": "<path to MathJax's es5 directory>",
 *     "macros": {...},                 // MathJax macro table (build/macros.py)
 *     "pages": ["<html file>", ...],   // rendered in place
 *     "shards": ["<json file>", ...],  // tooltip data: "html" and "title_html" fields rendered
 *     "css": "<output path for the shared stylesheet>"
 *   }
 *
 * Prints one JSON line: {"pages": n, "shards": n, "errors": [...]}.
 */

const fs = require('fs');
const path = require('path');

const job = JSON.parse(fs.readFileSync(0, 'utf8'));

global.MathJax = {
    loader: {
        paths: { mathjax: job.mathjax },
        load: ['adaptors/liteDOM', 'input/tex-full', 'output/chtml', 'a11y/assistive-mml'],
        require,
    },
    tex: {
        // (no 'noundefined': an unknown macro is reported as an error instead of drawn in red)
        packages: { '[+]': ['ams', 'newcommand', 'configmacros', 'boldsymbol', 'mathtools', 'upgreek'] },
        inlineMath: [['\\(', '\\)']],
        displayMath: [['\\[', '\\]']],
        processEscapes: true,
        processEnvironments: true,
        tags: 'ams',
        macros: job.macros,
    },
    // Full (not per-page) CSS, shared by all pages; fonts are served next to it
    chtml: { fontURL: 'mathjax-fonts', adaptiveCSS: false },
    // Hidden MathML copies for screen readers
    options: { enableAssistiveMml: true },
    startup: { typeset: false },
};

require(path.join(job.mathjax, 'startup.js'));

MathJax.startup.promise.then(() => {
    const adaptor = MathJax.startup.adaptor;
    const { mathjax } = MathJax._.mathjax;
    const options = { InputJax: MathJax.startup.input, OutputJax: MathJax.startup.output };
    const result = { pages: 0, shards: 0, errors: [] };
    let cssWritten = false;

    const collectErrors = (html, where) => {
        for (const match of html.matchAll(/data-mjx-error="([^"]*)"/g)) {
            result.errors.push(`${where}: ${match[1]}`);
        }
    };

    // Keep each formula's TeX source in the page, so the site can put it on the clipboard.
    // The book's own macros are expanded first, so what a reader pastes compiles anywhere.
    const readGroup = (text, start) => {
        let i = start;
        while (i < text.length && /\s/.test(text[i])) i++;
        if (text[i] !== '{') return null;
        let depth = 0;
        for (let j = i; j < text.length; j++) {
            if (text[j] === '{' && text[j - 1] !== '\\') depth++;
            else if (text[j] === '}' && text[j - 1] !== '\\') {
                depth--;
                if (depth === 0) return { body: text.slice(i + 1, j), end: j + 1 };
            }
        }
        return null;
    };

    const expandMacros = tex => {
        let out = tex;
        for (let pass = 0; pass < 12; pass++) {
            let changed = false;
            out = out.replace(/\\([A-Za-z]+|[0-9])/g, (match, name, offset, whole) => {
                const macro = job.macros[name];
                if (macro === undefined) return match;
                if (typeof macro === 'string') {
                    changed = true;
                    return macro;
                }
                return match;  // macros with arguments are handled below
            });
            // macros that take arguments, one at a time so the groups can be read
            const withArgs = /\\([A-Za-z]+)/g;
            let match;
            while ((match = withArgs.exec(out)) !== null) {
                const macro = job.macros[match[1]];
                if (!Array.isArray(macro)) continue;
                const [body, count] = macro;
                const args = [];
                let cursor = match.index + match[0].length;
                for (let k = 0; k < count; k++) {
                    const group = readGroup(out, cursor);
                    if (!group) break;
                    args.push(group.body);
                    cursor = group.end;
                }
                if (args.length !== count) continue;
                const filled = body.replace(/#(\d)/g, (_, k) => args[Number(k) - 1] ?? '');
                out = out.slice(0, match.index) + filled + out.slice(cursor);
                changed = true;
                withArgs.lastIndex = 0;
            }
            if (!changed) break;
        }
        return out;
    };

    const tagSource = document => {
        for (const item of document.math) {
            if (item.typesetRoot) adaptor.setAttribute(item.typesetRoot, 'data-tex', expandMacros(item.math));
        }
    };

    const writeCss = document => {
        if (cssWritten) return;
        const sheet = MathJax.startup.output.styleSheet(document);
        fs.writeFileSync(job.css, adaptor.textContent(sheet));
        cssWritten = true;
    };

    for (const file of job.pages) {
        const html = fs.readFileSync(file, 'utf8');
        if (!/\\\(|\\\[|\\begin\{/.test(html)) {
            continue;  // nothing to render (or rendered already)
        }
        const document = mathjax.document(html, options);
        document.render();
        tagSource(document);
        writeCss(document);
        // The stylesheet is shared (mathjax.css), not inlined in every page
        const style = adaptor.elementById(adaptor.head(document.document), 'MJX-CHTML-styles');
        if (style) adaptor.remove(style);
        const output = adaptor.doctype(document.document) + adaptor.outerHTML(adaptor.root(document.document));
        collectErrors(output, path.basename(file));
        fs.writeFileSync(file, output);
        result.pages++;
    }

    const renderFragment = (fragment, where) => {
        if (!fragment || !/\\\(|\\\[|\\begin\{/.test(fragment)) return fragment;
        const document = mathjax.document(`<!DOCTYPE html><html><head></head><body>${fragment}</body></html>`, options);
        document.render();
        tagSource(document);
        writeCss(document);
        const output = adaptor.innerHTML(adaptor.body(document.document));
        collectErrors(output, where);
        return output;
    };

    for (const file of job.shards) {
        const data = JSON.parse(fs.readFileSync(file, 'utf8'));
        // One file per result (theorems/<chapter>/<label>.json) holds a single entry; the
        // older one-file-per-chapter layout held a map of them. An entry is recognised by
        // its own "html" field — without this check the map branch would iterate an entry's
        // *fields*, assign to a string primitive, and silently render nothing.
        const single = typeof data.html === 'string';
        const entries = single ? [[path.basename(file, '.json'), data]] : Object.entries(data);
        for (const [label, entry] of entries) {
            entry.html = renderFragment(entry.html, label);
            entry.title_html = renderFragment(entry.title_html, label);
        }
        fs.writeFileSync(file, JSON.stringify(data));
        result.shards++;
    }

    if (!cssWritten) {
        // No math anywhere: still provide the stylesheet the pages link to
        const document = mathjax.document('<!DOCTYPE html><html><head></head><body>\\(x\\)</body></html>', options);
        document.render();
        writeCss(document);
    }
    process.stdout.write(JSON.stringify(result) + '\n');
}).catch(error => {
    process.stderr.write(String(error && error.stack || error) + '\n');
    process.exit(1);
});
