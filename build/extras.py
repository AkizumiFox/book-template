"""
Build System Extra Pages
========================
Pages generated from the label registry rather than written by the author:

- results.html: every definition, theorem, example, ... grouped by chapter and section,
  with filters and hover previews.
- graph.html: the dependency graph of results (templates/html/graph.js), from
  @references and from theorem titles mentioned in statements and proofs.

They use the book's HTML template, so they have the same sidebar, toolbar and theme.
"""

import json
import re
from html import escape
from pathlib import Path

from .book import Book, Page
from .manifest import load_scan, STATEMENT_TYPES
from .pandoc import build_pandoc_command, page_metadata, run_pandoc
from .utils import print_success, print_error, print_warning

RESULTS_PAGE = "results.html"
GRAPH_PAGE = "graph.html"

# Filter groups on the results page: (group, label, environment types)
RESULT_GROUPS = [
    ("statements", "Theorems and lemmas", STATEMENT_TYPES | {"conjecture"}),
    ("definitions", "Definitions", {"definition"}),
    ("examples", "Examples", {"example"}),
    ("exercises", "Exercises", {"exercise"}),
]


BLACKBOARD = {"R": "ℝ", "Q": "ℚ", "C": "ℂ", "Z": "ℤ", "N": "ℕ", "F": "𝔽"}
SYMBOLS = {"sqrt": "√", "cdot": "·", "times": "×", "to": "→", "leq": "≤", "geq": "≥", "neq": "≠",
           "in": "∈", "subseteq": "⊆", "oplus": "⊕", "cap": "∩", "cup": "∪", "infty": "∞"}


def plain_title(title: str) -> str:
    """A title for places that cannot typeset math (graph labels): TeX to readable text."""
    title = re.sub(r"\\n([A-Z])\b", lambda m: BLACKBOARD.get(m.group(1), m.group(1)), title)
    title = re.sub(r"\\[()\[\]]", "", title)
    title = re.sub(r"\\([A-Za-z]+)", lambda m: SYMBOLS.get(m.group(1), m.group(1)), title)
    title = title.replace("{", "").replace("}", "")
    return " ".join(title.split())


def _group_of(env_type: str) -> str:
    return next((group for group, _, types in RESULT_GROUPS if env_type in types), "other")


def _env_colors(book: Book) -> dict[str, str]:
    colors = {}
    for env in book.environment_settings.get("big_envs", []):
        key = env["name"].lower().replace(" ", "-")
        if env.get("color"):
            colors[key] = env["color"]
    return colors


def _results_by_page(book: Book, labels: dict) -> dict[str, list[tuple[str, dict]]]:
    """Labeled environments (not equations) per page, in reading order."""
    scan, _ = load_scan(book)
    grouped = {}
    for page in book.pages:
        entry = scan["files"].get(page.html_path)
        if not entry:
            continue
        # scan.json lists labels sorted by id; order them as they appear in the page text
        items = [(label, labels[label]) for label in entry["labels"]
                 if label in labels and labels[label].get("type") != "equation"]
        text = page.source.read_text(encoding="utf-8")
        items.sort(key=lambda item: text.find("#" + item[0]))
        if items:
            grouped[page.html_path] = items
    return grouped


def _results_body(book: Book, labels: dict) -> str:
    grouped = _results_by_page(book, labels)
    counts = {group: 0 for group, _, _ in RESULT_GROUPS}
    for items in grouped.values():
        for _, info in items:
            group = _group_of(info.get("type", ""))
            if group in counts:
                counts[group] += 1

    parts = ['<div class="results-filters" role="group" aria-label="Filter results">']
    for group, label, _ in RESULT_GROUPS:
        if counts[group]:
            parts.append(
                f'<label class="results-filter"><input type="checkbox" value="{group}" checked> '
                f'{escape(label)} <span class="results-count">{counts[group]}</span></label>')
    parts.append('<input type="search" class="results-search" placeholder="Filter by name or number" '
                 'aria-label="Filter results by name or number">')
    parts.append('</div>')

    for chapter in book.chapters:
        chapter_pages = [p for p in book.pages if p.chapter is chapter and p.html_path in grouped]
        if not chapter_pages:
            continue
        parts.append(f'<section class="results-chapter">')
        parts.append(f'<h2 id="chapter-{escape(chapter.slug)}">{escape(chapter.title)}</h2>')
        for page in chapter_pages:
            heading = f"{page.number} {page.title}" if page.number else page.title
            parts.append(f'<div class="results-section">')
            parts.append(f'<h3><a href="{escape(page.html_path)}">{escape(heading)}</a></h3>')
            parts.append('<ul class="results-list">')
            for label, info in grouped[page.html_path]:
                name = " ".join(filter(None, [info.get("type_name"), info.get("number")]))
                title = info.get("title_html") or ""
                search_text = f"{name} {info.get('title', '')}".lower()
                parts.append(
                    f'<li class="result" data-group="{_group_of(info.get("type", ""))}" '
                    f'data-search="{escape(search_text)}" style="--env-color: {_env_colors(book).get(info.get("type"), "var(--muted)")}">'
                    f'<a class="xref result-name" href="{escape(info["file"])}#{escape(label)}" '
                    f'data-ref="{escape(label)}" data-shard="{escape(info.get("shard", ""))}">{escape(name)}</a>'
                    + (f' <span class="result-title">{title}</span>' if title else "")
                    + '</li>')
            parts.append('</ul></div>')
        parts.append('</section>')
    parts.append('<p class="results-empty" hidden>No results match the filter.</p>')
    return "\n".join(parts)


def _graph_data(book: Book, labels: dict) -> dict:
    """Chapter-level dependencies: how often a chapter's pages cite results of another chapter."""
    scan, _ = load_scan(book)
    chapter_of = {p.html_path: p.chapter for p in book.pages if p.chapter}
    index_of = {c.slug: next((p.html_path for p in book.pages if p.chapter is c and p.section == 0), "")
                for c in book.chapters}
    counts: dict[tuple[str, str], int] = {}
    results: dict[str, int] = {c.slug: 0 for c in book.chapters}
    for label, info in labels.items():
        chapter = chapter_of.get(info.get("file"))
        if chapter is not None and info.get("type") != "equation":
            results[chapter.slug] = results.get(chapter.slug, 0) + 1
    for path, entry in scan["files"].items():
        citing = chapter_of.get(path)
        if citing is None:
            continue
        for ref in entry.get("refs", []):
            target = labels.get(ref)
            cited = chapter_of.get(target.get("file")) if target else None
            if cited is None or cited.slug == citing.slug or target.get("type") == "equation":
                continue  # citations inside one chapter are not drawn
            key = (cited.slug, citing.slug)
            counts[key] = counts.get(key, 0) + 1
    nodes = [{
        "id": chapter.slug,
        "name": f"Chapter {chapter.number}",
        "title": chapter.title,
        "url": index_of.get(chapter.slug, ""),
        "results": results.get(chapter.slug, 0),
        "chapterNumber": chapter.number,
        "part": chapter.part,
    } for chapter in book.chapters]
    implied = _implied_edges(counts)
    edges = [{"source": source, "target": target, "weight": weight,
              "implied": (source, target) in implied}
             for (source, target), weight in sorted(counts.items())]
    return {"nodes": nodes, "edges": edges}


def _implied_edges(counts: dict[tuple[str, str], int]) -> set[tuple[str, str]]:
    """The edges a transitive reduction drops: those a longer path already implies.

    An edge u -> v is implied when u has another direct successor w that reaches v, so
    drawing u -> v tells the reader nothing that u -> w -> ... -> v does not. On a directed
    acyclic graph the reduction is unique, so there is nothing to choose. A cycle would make
    it ambiguous; chapters may not cite each other in a circle, and if they ever do we draw
    every edge rather than pick a spanning shape at random.
    """
    successors: dict[str, set[str]] = {}
    for source, target in counts:
        successors.setdefault(source, set()).add(target)
        successors.setdefault(target, set())
    reach: dict[str, set[str]] = {}
    visiting: set[str] = set()
    cyclic = False

    def reachable(node: str) -> set[str]:
        nonlocal cyclic
        if node in reach:
            return reach[node]
        if node in visiting:
            cyclic = True
            return set()
        visiting.add(node)
        seen: set[str] = set()
        for nxt in successors[node]:
            seen.add(nxt)
            seen |= reachable(nxt)
        visiting.discard(node)
        reach[node] = seen
        return seen

    for node in successors:
        reachable(node)
    if cyclic:
        print_warning("chapters cite each other in a circle; drawing every dependency")
        return set()
    return {(source, target) for source, target in counts
            if any(other != target and target in reach[other] for other in successors[source])}


GRAPH_BODY = """<p class="graph-intro">
Each box is a chapter. An arrow from one chapter to another means results in the second
cite results in the first; the thicker the arrow, the more citations. A dependency that a
longer chain already implies is not drawn, so what you see is the skeleton: almost every
chapter also draws on chapters further back. Hover over a chapter to see those dropped
dependencies, as dashed arrows and as counts beside the graph; click to open it. For the
results themselves, see the <a href="results.html">list of results</a>.
</p>
<div class="graph-frame">
  <div id="dependency-graph" class="dependency-graph" data-graph="graph.json" role="img"
       aria-label="Dependency graph of the book's chapters"></div>
  <aside class="graph-preview" hidden></aside>
</div>
<noscript><p>The graph needs JavaScript. The <a href="results.html">list of results</a> works without it.</p></noscript>
"""


def _render_page(book: Book, html_path: str, title: str, body_html: str, extra: dict) -> bool:
    source = book.build_dir / "tmp" / "generated" / Path(html_path).with_suffix(".md")
    source.parent.mkdir(parents=True, exist_ok=True)
    # A raw HTML block, so Pandoc passes the markup through unchanged
    # (the title gets its own id, which would otherwise collide with ids in the body)
    source.write_text(f"# {title} {{#page-title}}\n\n```{{=html}}\n{body_html}\n```\n", encoding="utf-8")
    page = Page(source=source, chapter=None, section=0, title=title, html_path=html_path)
    metadata = page_metadata(book, page, "html", extra)
    metadata["breadcrumb-chapter-title"] = book.title
    output = book.html_dir / html_path
    return run_pandoc(build_pandoc_command(book, page, output, "html", metadata))


def generate_extra_pages(book: Book, extra: dict) -> bool:
    """Write results.html, graph.html and graph.json. `extra` is shared page metadata."""
    _, labels = load_scan(book)
    ok = _render_page(book, RESULTS_PAGE, "List of results", _results_body(book, labels), extra)
    (book.html_dir / "graph.json").write_text(json.dumps(_graph_data(book, labels), indent=1), encoding="utf-8")
    ok = _render_page(book, GRAPH_PAGE, "Dependency graph", GRAPH_BODY,
                      dict(extra, **{"page-scripts": ["graph.js"], "wide-page": True})) and ok
    if ok:
        print_success("Generated pages: list of results, dependency graph")
    else:
        print_error("Could not generate the list of results or the dependency graph")
    return ok
