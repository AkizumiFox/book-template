# Build Commands

Use `./build.py <command>` (or `python -m build <command>`) from the project root.

## Everyday

| Goal | Command |
|------|---------|
| Live preview while writing | `./build.py serve` (`--port 8000`) |
| Build the website | `./build.py html` |
| Build one page | `./build.py html src/ch00-demo/01-every-environment.md` |
| Build per-section PDFs | `./build.py pdf` (or one file, as above) |
| Build the combined book PDF | `./build.py book` |
| Build everything | `./build.py all` |
| Remove `_build/` | `./build.py clean` |

`html` and `pdf` skip pages whose inputs are unchanged: the source file, the filters,
templates, config and macros, the page's previous/next pages, and the numbers and titles
of the labels it references. `clean` forces a full rebuild.

`serve` builds the site, serves `_build/html` on http://127.0.0.1:8000, and rebuilds when
anything in `src/`, `filters/`, `templates/html/`, the config or the macros changes. Open
pages reload by themselves. Pages built by `serve` contain the reload script; the next
`html` or `deploy` rebuilds them without it.

## Checks

| Goal | Command |
|------|---------|
| Verify required tools (pandoc, pdflatex, pdftocairo) | `./build.py doctor` |
| Validate references, links, and web vs PDF numbering | `./build.py check` |
| Run the engine tests | `python3 -m unittest discover -s tests` |

`check` fails on unresolved `@refs`, duplicate labels, cross-reference links in `_build/html`
that point nowhere, component problems, and any label whose number in the PDFs differs from
the website. Run it after `./build.py all`, since the numbering comparison reads the LaTeX
`.aux` files. `deploy` runs `all` and `check` first and stops if either fails.

`check` also warns (without failing) about:

- **Spelling** (needs `aspell`): words in the prose, not in formulas or code. Add correct
  terms to `spelling.txt` in the book directory, one per line.
- **Named results without a reference**: a proof that says "by the Basis Extension Theorem"
  instead of `@thm-basis-extension`. A reference gives readers a link and a preview and makes
  the dependency graph exact.

## Writing

- Environments: `::: {#thm-name}` … `:::` (prefixes and counters in `environment_settings` in
  the config), small environments `::: {.proof}`. Environments nest. Each numbered
  environment has one `color`; the website derives the box's rule and background tint from
  it, for both light and dark mode.
- References: `@thm-name`, `@eq-name`. Numbered targets read "Theorem 1.2.3"; unnumbered
  ones (examples) read "Example (Title)".
- Equations: `\[ … \]{#eq-name}`.
- Labeled lists: `::: {.enumerate options="label=(VS\arabic*)"}` around a numbered list.
- Figures: TikZ or tikz-cd (e.g. exported from quiver) as raw LaTeX. The PDF uses it directly;
  the website gets an SVG compiled once and cached in `_build/cache/tikz/`.
- Macros: add them to `latex/macros.tex` (`\def`, `\newcommand`, `\providecommand`,
  `\DeclareMathOperator`). The website's MathJax macros are generated from this file.

## Math rendering

Formulas are rendered when the site is built (MathJax 3.2.2 under Node, `build/math.py`), so
pages show finished math immediately and load no math script. Tooltip previews and the list
of results are rendered too; search snippets load MathJax only when needed. MathJax is
downloaded once into `~/.cache/book-engine`. Without `node`, or without network access for
that download, the site falls back to rendering math in the browser; set
`"prerender-math": false` in the config to always do that. Unknown macros are reported as
build warnings.

## Generated pages

- `results.html`: every definition, theorem and example, grouped by chapter and section,
  with filters and previews.
- `graph.html`: dependency graph of the chapters. An arrow from one chapter to another
  means a *proof* in the second uses a result from the first, and its width counts those
  proofs. Citations made outside a proof -- a statement, a remark, an exercise, a written
  solution -- are carried as "soft" and shown on hover rather than drawn, as is any
  dependency a longer chain already implies. A picker computes the reading path of any one
  section and dims the chapters it never reaches.
- `paths.html` and one `path-<slug>.html` per reader profile: the sections a reader needs
  in order to reach the results that profile aims at, in reading order, with what can be
  skipped. Profiles are declared in the config under `reading-paths`; the closure is
  computed from the book's own proofs at build time. **A path that is not closed -- one
  whose sections do not carry all their own prerequisites -- fails the build.**
  `python3 tools/reading_path.py --help` is the same machinery on the command line.

## Reader features (no configuration)

Solutions start folded and proofs can be folded; visited sections get a check mark and the
start page offers "Continue reading"; ← and → go to the previous and next page; `/` opens
search; the toolbar folds the side panes and switches light/dark; on touch screens a tap on
a reference opens its preview. With `issues-url` set, each page links to a prefilled
"Report a typo" issue.

## Interactive components

Each component has a web form and a print form, so the PDF never has gaps. Pages without
components load no extra JavaScript. `./build.py check` reports bad plot expressions,
widgets without print content and missing widget files.

**Runnable Python cell**

````
```{.python .run #cell-eigen packages="numpy"}
import numpy as np
np.linalg.eigvals(np.array([[2, 1], [1, 3]]))
```
````

- Web: an editable cell with a Run button (Shift+Enter in the editor). Python runs in the
  reader's browser via Pyodide, downloaded on the first Run. Cells on a page share one
  namespace, and running a cell first runs earlier cells that have not run. Imports of
  bundled packages (numpy, scipy, sympy, pandas, matplotlib, networkx, statsmodels,
  scikit-learn, ...) load automatically; `packages` is only needed for packages that are
  not imported by name. matplotlib figures are shown as images. Stop ends a long run.
- PDF: a code listing, followed by a link to the cell online when `deploy-domain` is set.

**Function plot**

```
::: {.plot fn="sin(a*x); cos(x)" x="-6.28,6.28" y="-2,2" params="a=1:0..3"}
Optional caption.
:::
```

- `fn`: one or more expressions separated by `;`. Allowed: numbers, `x`, parameters, `pi`,
  `e`, `+ - * / ^`, parentheses, `sin cos tan asin acos atan sinh cosh tanh exp log sqrt abs`
  (`log` is natural, angles in radians). Multiplication must be written (`2*x`).
- `x`: range (default `-5,5`). `y`: range (default: chosen from the curves).
- `params`: `name=default:min..max`, comma-separated; each gets a slider.
- Web: JSXGraph. PDF: pgfplots with each parameter at its default.

**Widget** (custom JavaScript)

```
::: {.widget src="widgets/linear-map.js" matrix="2,1,0,1"}
::: {.print}
What the PDF shows instead (text, or a TikZ figure).
:::
:::
```

- `src` is a JavaScript module in the book's `widgets/` directory, or one of the engine's
  (`widgets/linear-map.js`: the image of the unit square under a 2×2 matrix whose column
  vectors can be dragged). Its default export is called as
  `mount(element, options, { loadJSXGraph, ensureId, COLORS })`, where `options` holds the
  div's other attributes. The print content is shown until the widget has mounted.
- PDF: only the `::: {.print}` content.

## Another book

The engine (`build/`, `filters/`, `templates/`, `latex/*.sty`) can build any book directory:

```
./build.py serve --book ../my-other-book
```

A book directory contains `book.json` (or `config/config.json`), its Markdown sources and a
macro file. Paths in the config are relative to the book directory, and output goes to its
own `_build/`. To change a template or style for one book, put a file at the same relative
path in the book directory (e.g. `templates/html/styles.css`); it takes precedence over the
engine's copy. `tests/fixture-book/` is a minimal example.

Config keys: `title`, `author`, `chapters` (directory strings, or `{"dir": …, "title": …}`;
the title defaults to the chapter's `index.md` heading), `src` (default `src`), `preface`
(default `src/index.md`), `macros`, `environment_settings`, `output`, `templates`, `styles`,
`repo-url` (optional source link in the sidebar), `issues-url` (optional, e.g.
`https://github.com/USER/REPO/issues/new`, for the "Report it" link), `prerender-math`
(default true), `deploy-dir`, `deploy-repo`, `deploy-domain`, `deploy-push-url`.

## Automatic deploys

`.github/workflows/build-and-deploy.yml` builds, tests and checks the book on every push, and
on `main` publishes `_build/html` to the site repository. It needs this source in a GitHub
repository and a deploy key; the setup steps are at the top of the file.

## Other

| Goal | Command |
|------|---------|
| Scan labels only | `./build.py scan` |
| Regenerate tooltip data only | `./build.py manifest` |
