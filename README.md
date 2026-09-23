# Book template

A starter repository for a textbook built on the Pandoc + Python engine used by the
linear algebra book. Clone it, set seven config keys, delete the demo chapter, and start
writing sections.

One source — Pandoc Markdown in `src/` — becomes both a website and a set of PDFs.

| Task | Command |
|---|---|
| Write with live preview | `./build.py serve` → http://127.0.0.1:8000 (rebuilds and reloads on save) |
| Build the HTML site | `./build.py html` |
| Build the book PDF | `./build.py book` (writes `_build/pdf/book.pdf`) |
| Everything | `./build.py all` |
| Validate references and numbering | `./build.py check` |
| Run the engine tests | `python3 -m pytest tests/ -q` |
| Check no result cites a later section | `python3 tools/check_forward_deps.py` (after `./build.py html`) |
| Check the external tools are installed | `./build.py doctor` |
| Publish | `./build.py deploy --push` (see `DEPLOY.md`) |

`BUILD.md` is the full command and syntax reference. This file is the orientation.

## What the engine does

Each Markdown section goes through Pandoc twice — once to HTML, once to LaTeX — with the
same Lua filters both times, so the two editions cannot drift apart. The filters turn
fenced divs into numbered environments, resolve `@label` cross-references, number
equations, and compile TikZ pictures to SVG for the web (cached) while passing them
through untouched to the PDF. `latex/macros.tex` is parsed into a MathJax macro table, so
a macro defined once works in both formats. Math is rendered at build time under Node,
so pages arrive finished and load no math script.

On top of that the build generates a search index, a list of every result, a dependency
graph of which result uses which, and hover previews for every reference.

Three gates keep the book honest, and all three must pass:

- **`./build.py all`** — a LaTeX error fails the build. `pdflatex` runs in nonstopmode and
  writes a PDF even after an error, so success is judged by the error lines in the log,
  not by the file existing. (Before this gate existed, 38 sections shipped damaged.)
- **`./build.py check`** — unresolved `@refs`, duplicate labels, cross-reference links
  pointing nowhere, and any label whose number in the PDF differs from its number on the
  web. It also warns, without failing, about spelling and about a named result mentioned
  in prose without a reference.
- **`python3 -m pytest tests/ -q`** — the engine's own tests, which build
  `tests/fixture-book` end to end, plus three linters that read *this* book's `src/`:
  no blank line inside a display, no non-ASCII character inside a math span, and no proof
  that belongs to no result.

## Start a book

1. **Clone and rename.** Copy this directory, `rm -rf .git`, `git init`.
2. **Set the config keys.** `config/config.json` lists them under `_TODO`:
   `title`, `author`, `repo-url`, `issues-url`, `deploy-repo`, `deploy-domain`,
   `deploy-push-url`. The deploy keys can stay empty until there is something to publish;
   `DEPLOY.md` explains them. Leave `environment_settings` alone unless the book really
   needs a different set of environments — it is the shared inheritance of both existing
   books, and changing a colour or a counter group later means rebuilding everything.
3. **Read the demo chapter, then delete it.** `src/ch00-demo/01-every-environment.md` is
   a working page that uses every environment, cross-reference, display, table, figure and
   exercise group the engine offers, each introduced by a line saying what it is for and
   what its markup is. Read the built page next to the source. When you no longer need it:
   `rm -rf src/ch00-demo` and remove its entry from `chapters`.
4. **Rewrite `src/index.md`**, the preface, which is the site's start page.
5. **Write sections** as `src/chNN-name/NN-title.md`. See the next section for how the
   numbers come out, and `authoring/STYLE.md` for how to write one.
6. **Raid `latex/macros-linear-algebra.tex.example`** for the macros this book needs and
   paste them into `latex/macros.tex`. Nothing loads the example file; it exists so the
   next book can take what it wants without inheriting 400 lines of someone else's
   notation. Record each macro you keep in `authoring/NOTATION.md`.
7. **Grow `spelling.txt`** as you write. It starts with a dozen general words on purpose.

## Where the numbers come from

Nothing is numbered by hand. Everything is derived from names on disk.

- **Chapter number:** the digits in the chapter directory name. `src/ch07-block-matrices/`
  is Chapter 7. A directory whose name does not start with `chNN` falls back to its
  position in the `chapters` list.
- **Chapter order:** the order of the `chapters` array in `config/config.json`, not
  alphabetical order. A chapter not listed there is not built.
- **Chapter title:** the `# ` heading of the chapter's `index.md`, unless the `chapters`
  entry gives an explicit `"title"`.
- **Section number:** the position of the file among its chapter's `*.md` files in
  **sorted filename order**, counting from 1 and ignoring `index.md`. So
  `src/ch07-block-matrices/03-schur.md` is section 7.3 — as long as no file sorts between
  them. This is why every filename starts with a two-digit number. To insert a section
  between 03 and 04, renumber; to keep old URLs alive, add a `redirects` entry.
- **Section title:** the file's `# ` heading. It becomes the navigation link, the page
  title, the PDF bookmark and the running head, so it carries no mathematics.
- **Result number:** *chapter.section.serial*, where the serial runs per counter group per
  section. Theorems, lemmas, corollaries and propositions share the `main` counter;
  definitions have their own; examples, exercises and conjectures are unnumbered and are
  cited by title.
- **Parts** are cosmetic: a `"part"` key on a chapter entry starts a new part banner there.

## The standing rules

The two books built on this engine follow these. They are worth keeping, because each one
was adopted after the alternative caused a mess.

- **A result is either proved from earlier material, or marked plainly as not proved
  here.** One sentence in the place it is used, in the reader's own language. There is no
  third option, and a gap that is not marked is a lie to a reader working alone.
- **No proof rests on an exercise.** The text may not lean on something the reader was
  asked to do. Exercises may cite the text, and a later exercise may cite an earlier one.
- **No forward references.** A proof cites only what appears earlier in the book. A
  forward pointer in prose ("we will prove this in Chapter 9") is fine as long as it is
  never a step in an argument. Run `python3 tools/check_forward_deps.py` after
  `./build.py html`: it reads `_build/crossref_labels.json` and exits 1 if any result
  cites one from a later section. It is a separate command, not part of `check`, so put
  it in the routine yourself.
- **Section titles carry no mathematics.** They become links, bookmarks and running heads.
- **One notation per idea, fixed in `authoring/NOTATION.md` before first use.** A second
  notation for the same thing costs a whole-book pass to retire.
- **Every macro lives in `latex/macros.tex`**, so the PDF and the website agree. Nothing
  ad hoc in a section file.

`authoring/STYLE.md` is the full writing standard; `authoring/DRAFTING.md` is the brief
handed to a drafting agent.

## The two traps

Both of these have cost real time in this project. They are not obvious and they do not
announce themselves.

**1. The display-width harness needs a fresh Chrome profile.**

`authoring/measure-displays.md` drives headless Chrome over the built site to find
formulas that overflow the text column. Chrome caches the pages in its user-data
directory, so re-running with the same `--user-data-dir` after an edit happily re-reports
the *old* widths. An "after" measurement taken that way is a lie, and it will tell you a
formula you just fixed is still broken — or, worse, that a formula you just broke is
fine. `rm -rf "$S/measure"` before every run. Two related traps are in the same file: a
row at exactly 100% is a `\tag` artifact and not an overflow, and a site whose math was
never prerendered measures as perfectly clean because there is nothing to measure.

**2. `\qedsymbol`-style definitions must sit outside the `skipenv` block.**

`latex/latex-template.sty` takes a `skipenv` option, and `latex/preamble.tex` passes it:
it means "define no theorem styles, boxes or environments here", because
`latex/theorem-envs.sty` owns all of those and builds them from the config. The block
between `\if@skipenv\else` and `\fi` is skipped entirely under that option.

Anything the environments *use* but do not *define* must therefore live outside the block.
`\qedsymbol` is the example: `latex/theorem-envs.sty` ends every proof with `\qed` but
sets no symbol, so moving `\renewcommand{\qedsymbol}{$\blacksquare$}` inside the block
would not raise an error — it would silently give amsthm's hollow box at the end of every
proof in the book, which is the kind of thing nobody notices until the PDF is printed. The
comment at that line in `latex-template.sty` says so. Heed it for anything similar: a
shared colour, a length, a helper macro an environment body calls.

## Layout

- `src/` — the book. One directory per chapter, one file per section.
- `config/config.json` — this book's settings: chapters, environments and counters,
  deploy target. `latex/macros.tex` — this book's macros, used by both formats.
- `build/`, `filters/`, `templates/`, `latex/*.sty`, `latex/sleek/` — the engine, shared
  by any book built with it (`./build.py serve --book ../other-book`; see "Another book"
  in `BUILD.md`).
- `latex/sleek/` — François Rozet's vendored *sleek* style, which the page and the boxes
  are built on. `latex/sleek/README.md` records every change made to it and why.
- `authoring/` — the writing standard (`STYLE.md`), the agent brief (`DRAFTING.md`), the
  notation table to fill in (`NOTATION.md`), and how to hunt overflowing displays
  (`measure-displays.md`).
- `spelling.txt` — words the spell check accepts; grows per book.
- `widgets/` — JavaScript modules available to `::: {.widget}`.
- `tests/` — the engine's tests and the small fixture book they build.
- `tools/` — the forward-dependency checker and the display-width harness.
- `.github/workflows/` — build, test and check on every push; publish on `main` once the
  `DEPLOY_KEY` secret and the `SITE_REPO` variable exist.
- `_build/`, `site/` and `docs/` are build output and are gitignored.
