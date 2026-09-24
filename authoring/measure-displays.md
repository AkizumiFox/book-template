# Finding maths that overflows the text column

The harness lives in the repo at `tools/_measure.html`. Copy it into the built site and drive
it headless: it renders every formula of every section into a 39rem column (the book's text
width) and lists the ones that stick out, as
`percent<TAB>page<TAB>first characters of the formula`, widest first.

```bash
cd <the book>
./build.py html
cp tools/_measure.html _build/html/_measure.html
(python3 -m http.server 8772 --directory _build/html >/dev/null 2>&1 &)
S=<your scratchpad>
rm -rf "$S/measure"            # a fresh Chrome profile every run -- see the traps below
timeout 300 google-chrome --headless=new --disable-gpu --no-sandbox --user-data-dir=$S/measure \
  --virtual-time-budget=120000 --dump-dom "http://localhost:8772/_measure.html" 2>/dev/null \
  | python3 -c "
import sys, re, html
m = re.search(r'<pre id=\"out\">(.*?)</pre>', sys.stdin.read(), re.S)
print(html.unescape(m.group(1)).strip() if m else '(no output)')"
```

Add `?mode=inline` to the URL to measure the **inline** maths instead of the displays. It is
the same page list, the same font warm-up and the same column, so the two sets of numbers are
comparable by construction; a clean run says `none (N inline formulas measured on M pages)`
rather than `none (N displays ...)`. Measure both after any bulk edit: inline maths overflows
the column as readily as a display and is easier to miss.

**Making an over-wide inline formula a display fixes nothing by itself.** A display is set in
the same column, so a 124% inline chain becomes a 124% display. What fixes the width is
breaking the chain across lines inside an `aligned`, or moving its left-hand side into the
prose. Never shrink the font to buy width.

**Measure `mjx-math`, not `mjx-container`.** The container is a block with `max-width: 100%`
and `overflow-x: auto`, so it always reports exactly the column width and a naive measurement
says every formula fits. The typeset mathematics inside it is what sticks out and what the
reader has to scroll. A harness that reports "none" for the whole book is measuring the wrong
box; sanity-check it against a formula you can see overflowing.

A formula over 100% overflows at all; at 110% and above it is clearly scrolling and should be
broken with `aligned`, `split` or `cases` (a `\tag` goes after `\end{aligned}`, never inside).

To measure a phone-width column instead, change `#stage { width: 39rem }` to 20rem.

## Four traps

- **Chrome caches the pages.** Re-running with the same `--user-data-dir` after editing can re-report the *old* widths, so an "after" number is a lie. Delete the profile directory before every run. This one has cost real time more than once.
- **A row at exactly 100% is not an overflow.** An equation carrying a `\tag` gets `width="full"` from MathJax, which stretches `mjx-math` to precisely the column. Those rows are measurement artifacts.
- **A site that was never prerendered measures as clean.** MathJax runs at build time; if the pages you serve have not been through it there is no `mjx-container` to find, and an older harness reported "none". The harness now refuses that: a clean run prints `none (N displays measured on M pages)`, and finding nothing at all is an error. If you see the error, run a full `./build.py html` first.
- **The incremental build races.** `_build/cache/html-fingerprints.json` can record stale HTML as freshly built when two builds run at once, and later builds then skip that page. Before trusting a measurement, delete that file and `_build/html` and rebuild; a serial `./build.py html` afterwards is the only state worth measuring.
