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
| Work out what a reader needs | `python3 tools/reading_path.py --list-profiles`, then `--profile <slug>` |
| Check nothing is proved from an optional result | `python3 tools/check_optional.py` (also run by `check`) |
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
graph of which result uses which, hover previews for every reference, and a reading-path
page per reader profile (see "Reading paths" below).

Three gates keep the book honest, and all three must pass:

- **`./build.py all`** — a LaTeX error fails the build. `pdflatex` runs in nonstopmode and
  writes a PDF even after an error, so success is judged by the error lines in the log,
  not by the file existing. (Before this gate existed, 38 sections shipped damaged.)
- **`./build.py check`** — unresolved `@refs`, duplicate labels, cross-reference links
  pointing nowhere, any label whose number in the PDF differs from its number on the
  web, and any proof that rests on a result marked `.optional`. It also warns, without
  failing, about spelling and about a named result mentioned in prose without a reference.
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

## Reading paths

The build knows which environment made every citation — a proof, a proof idea and a claim
are *hard*, a statement, a remark, an exercise or a written solution are *soft* — so it can
answer the question a reader actually asks: **if I want that theorem, what must I read
first?** Following the hard citations backwards from a section gives the smallest set of
sections whose proofs are all complete, and nothing else.

A **reader profile** is a name and a handful of target sections. Declare them in
`config/config.json` under `reading-paths`, which is the whole interface — no code:

```json
"reading-paths": [
  {
    "slug": "example",
    "name": "The worked section",
    "description": "One sentence naming what this reader is after, in their language.",
    "targets": ["ch00-demo/01"]
  }
]
```

- `slug` — lowercase letters, digits and hyphens. It names the page, `path-<slug>.html`.
- `targets` — sections written the way the files name them, `<chapter directory>/<section
  number>`: `ch07-block-matrices/03`, or `ch07-block-matrices/index` for a chapter's index
  page. **Choose the sections, not the chapters**; a chapter-level answer is roughly twice
  as long, and it is a section that a reader actually turns to.

Pick each target by reading what the section *contains*, not by its title: the target is
the result this reader came for. Two or three to half a dozen per profile is the usual
shape, and a profile whose path is nearly the whole book is telling you it is aimed too
broadly.

Each build then writes `paths.html`, listing every profile with its two lengths, and one
`path-<slug>.html` per profile giving the sections in reading order, what can be skipped,
and where the path hangs on a single proof. The two lengths are the same path counted two
ways: the reading path, and the path for a reader who also works the exercises, since a
written solution is the proof of its exercise. Nothing here picks one for the reader.

**Every generated path is checked before it is written, and an unclosed path fails the
build.** Closed means every result a proof on the path uses is proved by another section
on the path. That is the whole point: a path with a gap in it is worse than no path.

On the command line, without building the pages:

```
python3 tools/reading_path.py --list-profiles
python3 tools/reading_path.py --profile example
python3 tools/reading_path.py ch00-demo/01 --with-exercises --weakest 2
python3 tools/reading_path.py ch00-demo/01 --verify
```

`--weakest N` lists the sections the path pulls in on at most N hard citations, with the
citing sites. Those are the cheap prunes: reword or move one citation and the section, and
everything only it needed, leaves the path.

The demo profile above ships with this template and aims at the one section the template
has. It is an example of the *shape*, not of the content — replace it with this book's
readers before the second chapter exists, and delete it along with `src/ch00-demo/`.

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
- **A result marked `.optional` may be cited, but never proved from.** Writing
  `::: {#thm-foo .optional}` prints "Optional: nothing later depends on this" in both
  editions and takes the result off every reading path. A remark, a statement or an
  exercise may point at it; a proof, a proof idea, a claim or a written solution may not,
  and `./build.py check` fails if one does.
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
- `tools/` — the forward-dependency checker, the optional-result checker, the
  reading-path tool and the display-width harness.
- `.github/workflows/` — build, test and check on every push; publish on `main` once the
  `DEPLOY_KEY` secret and the `SITE_REPO` variable exist.
- `_build/`, `site/` and `docs/` are build output and are gitignored.
