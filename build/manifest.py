"""
Build System Manifest Module
============================
Scans every page for labels, references and search text (cached per page), and writes
the data files the website loads: tooltip shards, navigation and the search index.
"""

import hashlib
import json
import re
import shutil
import subprocess
from html import escape as html_escape, unescape
from concurrent.futures import ThreadPoolExecutor

from .book import Book, Page
from .utils import print_step, print_success, print_warning, print_error, run_with_crash_retry


# =============================================================================
# Label Scanning
# =============================================================================

def _scan_meta_file(book: Book):
    path = book.build_dir / "tmp" / "scan_meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"environment_settings": book.environment_settings}), encoding="utf-8")
    return path


def _scan_key(book: Book, page: Page) -> str:
    digest = hashlib.sha1()
    digest.update((book.filters_dir / "theorems.lua").read_bytes())
    digest.update((book.filters_dir / "components.lua").read_bytes())
    digest.update(json.dumps(book.environment_settings, sort_keys=True).encode())
    digest.update(f"{page.chapter_number}:{page.section}:{page.html_path}".encode())
    digest.update(page.source.read_bytes())
    return digest.hexdigest()


def _scan_page(book: Book, page: Page, meta_file) -> dict | None:
    cache_file = book.cache_dir / "scan" / f"{_scan_key(book, page)}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    cmd = [
        "pandoc", str(page.source),
        "--from", "markdown+tex_math_single_backslash",
        "--to", "json",
        "--lua-filter", str(book.filters_dir / "components.lua"),
        "--lua-filter", str(book.filters_dir / "theorems.lua"),
        "--metadata-file", str(meta_file),
        "--metadata", "scan_mode=true",
        "--metadata", f"book-root={book.root}",
        "--metadata", f"engine-root={book.filters_dir.parent}",
        "--metadata", f"source-path={page.source.relative_to(book.root)}",
        "--metadata", f"chapter-num={page.chapter_number}",
        "--metadata", f"section-num={page.section}",
    ]
    try:
        result = run_with_crash_retry(cmd)
    except subprocess.CalledProcessError as e:
        print_error(f"Error scanning {page.source.name}")
        for line in (e.stderr or "").strip().splitlines():
            print(f"    {line}")
        return None
    if result.stderr and result.stderr.strip():
        print_warning(f"Scan warning for {page.source.name}:")
        for line in result.stderr.strip().splitlines():
            print(f"    {line}")

    errors = [json.loads(line[len("COMPONENT_ERROR:"):])["message"]
              for line in result.stdout.splitlines() if line.startswith("COMPONENT_ERROR:")]
    for line in result.stdout.splitlines():
        if line.startswith("SCAN_RESULT:"):
            data = json.loads(line[len("SCAN_RESULT:"):])
            data = {"labels": data.get("labels") or {}, "refs": data.get("refs") or [], "text": data.get("text") or "",
                    "description": data.get("description") or "", "prose": data.get("prose") or "",
                    "uses": data.get("uses") or {}, "block_text": data.get("block_text") or {},
                    "errors": errors}
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
    print_error(f"No scan result for {page.source.name}")
    return None


def scan_labels(book: Book) -> dict:
    """
    Scan all pages. Writes crossref_labels.json (label registry used by the filters) and
    scan.json (per-page labels, references and text). Returns the scan data.
    """
    print_step("Scanning labels...")
    meta_file = _scan_meta_file(book)
    pages = book.pages
    with ThreadPoolExecutor(max_workers=min(8, len(pages) or 1)) as executor:
        results = list(executor.map(lambda p: _scan_page(book, p, meta_file), pages))

    global_labels = {}
    scan_files = {}
    for page, data in zip(pages, results):
        if data is None:
            continue
        uses = data.get("uses") or {}
        for label_id, info in data["labels"].items():
            info = dict(info, file=page.html_path, shard=page.shard, uses=uses.get(label_id, []),
                        text=(data.get("block_text") or {}).get(label_id, ""))
            global_labels.setdefault(label_id, info)
        scan_files[page.html_path] = {
            "source": str(page.source.relative_to(book.root)),
            "labels": sorted(data["labels"]),
            "refs": data["refs"],
            "text": data["text"],
            "description": data.get("description", ""),
            "prose": data.get("prose", ""),
            "errors": data.get("errors", []),
        }

    add_title_mentions(global_labels)
    book.build_dir.mkdir(parents=True, exist_ok=True)
    book.labels_file.write_text(json.dumps({"crossref_labels": global_labels}, indent=2), encoding="utf-8")
    scan = {"files": scan_files}
    book.scan_file.write_text(json.dumps(scan, indent=2), encoding="utf-8")
    print_success(f"Scanned {len(global_labels)} labels.")
    return scan


STATEMENT_TYPES = {"theorem", "lemma", "corollary", "proposition"}


def add_title_mentions(labels: dict):
    """
    "mentions": results whose title appears in another result's statement or proof
    ("... by the Basis Extension Theorem ...") without an @reference. Only named
    theorems, lemmas, corollaries and propositions count; definitions are mentioned
    everywhere by their terms and are not dependencies in that sense.
    """
    named = {
        label: re.compile(r"\b" + re.escape(info["title"]) + r"\b", re.IGNORECASE)
        for label, info in labels.items()
        if info.get("type") in STATEMENT_TYPES and len(info.get("title", "").split()) >= 2
    }
    for label, info in labels.items():
        text = info.pop("text", "")
        referenced = set(info.get("uses", []))
        info["mentions"] = sorted(
            other for other, pattern in named.items()
            if other != label and other not in referenced and pattern.search(text)
        )


def load_scan(book: Book) -> tuple[dict, dict]:
    """(scan data, label registry) from the last scan."""
    scan = json.loads(book.scan_file.read_text(encoding="utf-8"))
    labels = json.loads(book.labels_file.read_text(encoding="utf-8"))["crossref_labels"]
    return scan, labels


# =============================================================================
# Website Data Files
# =============================================================================

def generate_theorem_manifest(book: Book):
    """
    Write tooltip data as one small file per result: theorems/<chapter-slug>/<label>.json.

    One file per chapter would be simpler, but a hover then costs the whole chapter — the
    shards reached 2.8 MB to show a single ~12 KB entry. Per-result files also churn less:
    editing one section no longer rewrites a multi-megabyte blob on every deploy.
    """
    _, labels = load_scan(book)
    wanted: dict[str, set[str]] = {}
    out_dir = book.html_dir / "theorems"
    for label_id, info in labels.items():
        shard = info["shard"]
        wanted.setdefault(shard, set()).add(f"{label_id}.json")
        entry = {
            "type": info.get("type", "unknown"),
            "type_name": info.get("type_name", ""),
            "number": info.get("number", ""),
            "title": info.get("title", ""),
            "title_html": info.get("title_html", ""),
            "html": info.get("html_content", ""),
            "file": info.get("file", ""),
        }
        shard_dir = out_dir / shard
        shard_dir.mkdir(parents=True, exist_ok=True)
        _write_if_changed(shard_dir / f"{label_id}.json", _json(entry))

    # Drop files and directories left behind by renamed labels or removed chapters
    if out_dir.exists():
        for stale in out_dir.glob("*.json"):       # the old one-file-per-chapter layout
            stale.unlink()
        for shard_dir in out_dir.iterdir():
            if not shard_dir.is_dir():
                continue
            if shard_dir.name not in wanted:
                shutil.rmtree(shard_dir)
                continue
            for stale in shard_dir.glob("*.json"):
                if stale.name not in wanted[shard_dir.name]:
                    stale.unlink()
    print_success(f"Theorem manifest: {len(labels)} entries in {len(wanted)} chapters")


def navigation_data(book: Book) -> dict:
    """The sidebar's chapter/section tree, shared by navigation.json and the server-side render."""
    cached = getattr(book, "_navigation_data", None)
    if cached is not None:
        return cached
    pages = book.pages
    preface = next((p for p in pages if p.is_preface), None)
    navigation = {
        "title": book.title,
        "author": book.author,
        "home": {"title": preface.title, "path": preface.html_path} if preface else None,
        "extras": [
            {"title": "List of results", "path": "results.html", "icon": "bi-list-ol"},
            {"title": "Dependency graph", "path": "graph.html", "icon": "bi-diagram-3"},
        ],
        "chapters": [],
    }
    for chapter in book.chapters:
        chapter_pages = [p for p in pages if p.chapter is chapter]
        index = next((p for p in chapter_pages if p.section == 0), None)
        navigation["chapters"].append({
            "title": chapter.title,
            "number": chapter.number,
            "part": chapter.part,
            "collapsed": len(book.chapters) > 6,
            "path": index.html_path if index else None,
            "sections": [
                {"title": p.title, "number": p.number, "path": p.html_path, "filename": p.source.name}
                for p in chapter_pages if p.section > 0
            ],
        })
    book._navigation_data = navigation
    return navigation


def generate_navigation_manifest(book: Book):
    """Write navigation.json. The sidebar itself is rendered into each page (render_navigation)."""
    navigation = navigation_data(book)
    _write_if_changed(book.html_dir / "navigation.json", _json(navigation))
    print_success(f"Navigation manifest: {sum(len(c['sections']) for c in navigation['chapters'])} sections")


def render_navigation(book: Book, page: Page) -> str:
    """
    The sidebar, as HTML, for one page.

    The template has always had a `$navigation$` slot and nothing ever filled it, so every
    page shipped a one-link placeholder and waited on JS to fetch navigation.json and rebuild
    the tree — behind two render-blocking CDN scripts, on all 263 pages, with no cache between
    them. Rendering it here costs ~40 KB against an ~800 KB page and removes a round trip from
    first paint. The markup must stay in step with buildSidebarNav() in main.js, which still
    runs when this is absent (the dev server, and any page built without a book context).
    """
    nav = navigation_data(book)
    prefix = page.asset_prefix
    current = page.html_path
    out = ['<ul class="nav-list">']

    home = nav.get("home") or {"title": "Preface", "path": "index.html"}
    out.append(f'<li class="nav-item nav-home"><a href="{prefix}{home["path"]}">{home["title"]}</a></li>')
    for extra in nav.get("extras", []):
        active = " active" if current == extra["path"] else ""
        out.append(
            f'<li class="nav-item nav-extra{active}"><a href="{prefix}{extra["path"]}">'
            f'<i class="bi {extra["icon"]}" aria-hidden="true"></i> {extra["title"]}</a></li>')

    for index, chapter in enumerate(nav["chapters"]):
        paths = [s["path"] for s in chapter["sections"]]
        is_active = current in paths or current == chapter.get("path")
        expanded = is_active or not chapter["collapsed"]
        first = chapter["sections"][0]["path"] if chapter["sections"] else None
        url = chapter["path"] or first
        if chapter["part"]:
            out.append(f'<li class="nav-part">{chapter["part"]}</li>')
        out.append(f'<li class="nav-chapter{" active" if is_active else ""}">')
        out.append(f'<div class="nav-chapter-header" data-chapter="{index}">')
        out.append(f'<a href="{prefix + url if url else "#"}" class="nav-chapter-title-link">'
                   f'<span class="nav-chapter-title">{chapter["title"]}</span></a>')
        out.append(f'<span class="nav-toggle{" expanded" if expanded else ""}">'
                   '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
                   'stroke="currentColor" stroke-width="2">'
                   '<polyline points="9 18 15 12 9 6"></polyline></svg></span>')
        out.append("</div>")
        out.append(f'<ul class="nav-sections{"" if expanded else " collapsed"}">')
        for section in chapter["sections"]:
            active = " active" if section["path"] == current else ""
            out.append(
                f'<li class="nav-section-item{active}">'
                f'<a href="{prefix}{section["path"]}" title="{html_escape(section["title"], quote=True)}">'
                f'<span class="nav-section-number">{section["number"]}</span>'
                f'<span class="nav-section-title">{section["title"]}</span></a></li>')
        out.append("</ul></li>")

    out.append("</ul>")
    return "".join(out)


def _plain(html: str) -> str:
    """Text of an HTML fragment, whitespace collapsed (math stays as TeX source)."""
    text = re.sub(r"<[^>]+>", " ", html)
    return " ".join(unescape(text).split())


def generate_search_index(book: Book):
    """
    Write search.json: one entry per page, and one per labeled environment (theorems,
    definitions, ...) so a search for a result's name leads straight to it.
    """
    scan, labels = load_scan(book)
    pages = {p.html_path: p for p in book.pages}
    index = []
    for page in book.pages:
        entry = scan["files"].get(page.html_path)
        if entry:
            title = f"{page.number} {page.title}" if page.number else page.title
            index.append({"kind": "page", "title": title, "url": page.html_path,
                          "content": " ".join(entry["text"].split())})
    for label_id, info in labels.items():
        if info.get("type") == "equation" or info.get("file") not in pages:
            continue
        name = " ".join(filter(None, [info.get("type_name"), info.get("number")]))
        title = f"{name} ({info['title']})" if info.get("title") else name
        page = pages[info["file"]]
        index.append({"kind": "result", "title": title, "url": f"{info['file']}#{label_id}",
                      "page": f"{page.number} {page.title}".strip(),
                      "content": _plain(info.get("html_content", ""))})
    _write_if_changed(book.html_dir / "search.json", _json(index))
    print_success(f"Search index generated with {len(index)} entries")


def page_description(text: str, limit: int = 160) -> str:
    """Shorten a page's description text (see theorems.lua) to about `limit` characters."""
    # Cross-references would be parsed as citations in page metadata; drop them from the summary
    text = re.sub(r"\s*\((?:see\s+)?@[\w-]+\)", "", text)
    text = re.sub(r"@[\w-]+", "", text)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.?!])\s+", text)
    chosen = ""
    for sentence in sentences:
        candidate = f"{chosen} {sentence}".strip()
        if len(candidate) > limit:
            break
        chosen = candidate
    return chosen or text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def generate_site_files(book: Book):
    """robots.txt and sitemap.xml (when deploy-domain is set) and a 404 page."""
    domain = (book.config.get("deploy-domain") or "").strip()
    if domain:
        paths = [p.html_path for p in book.pages] + ["results.html", "graph.html"]
        urls = "\n".join(f"  <url><loc>https://{domain}/{path}</loc></url>" for path in paths)
        _write_if_changed(book.html_dir / "sitemap.xml",
                          '<?xml version="1.0" encoding="UTF-8"?>\n'
                          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                          f"{urls}\n</urlset>\n")
        _write_if_changed(book.html_dir / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml\n")
    # GitHub Pages serves 404.html for unknown paths at any depth, so links are absolute
    root = "/"
    title = html_escape(book.title)
    _write_if_changed(book.html_dir / "404.html", f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex">
    <script>
        (function () {{
            var theme = null;
            try {{ theme = localStorage.getItem('book-theme'); }} catch (e) {{}}
            document.documentElement.dataset.theme = theme === 'light' || theme === 'dark' ? theme
                : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        }})();
    </script>
    <title>Page not found – {title}</title>
    <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="{root}styles.css">
</head>
<body>
    <main class="not-found">
        <p class="not-found-book"><a href="{root}index.html">{title}</a></p>
        <h1>Page not found</h1>
        <p>This page does not exist, or it moved when the book was reorganized.</p>
        <p><a href="{root}index.html">Go to the start of the book</a>, or use the search in the sidebar there.</p>
    </main>
</body>
</html>
""")


def _json(data) -> str:
    """Compact JSON for the data files the browser fetches: nobody reads them by eye."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _write_if_changed(path, text: str):
    """Keep the file's timestamp when nothing changed (the dev server watches outputs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")
