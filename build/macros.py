"""
Build System Macros Module
==========================
Converts the book's LaTeX macro file into a MathJax macro table, so the website and
the PDF use the same definitions.

Supported definitions (one per line or several per line):
    \\def\\name{body}
    \\newcommand{\\name}[n]{body}      (also \\renewcommand, \\providecommand, starred forms)
    \\DeclareMathOperator{\\name}{text} (starred form gives \\operatorname*)
"""

import json
import re
from pathlib import Path

# LaTeX constructs MathJax does not provide, rewritten for the web
WEB_REWRITES = [
    (re.compile(r"\\mathbbmss\b"), r"\\mathbb"),
]

# Definitions LaTeX gets from packages (mathtools, bm) that MathJax needs spelled out.
# Applied before the macro file, so the book's own definitions win.
WEB_DEFAULTS: dict[str, str | list] = {
    "coloneqq": "\\mathrel{:=}",
    "eqqcolon": "\\mathrel{=:}",
}
# Applied after the macro file: \providecommand{\bm} is a no-op in LaTeX once the bm
# package is loaded, so the web should follow the package, not the fallback.
WEB_OVERRIDES: dict[str, str | list] = {
    "bm": ["\\boldsymbol{#1}", 1],
}

_NAME = r"\\([A-Za-z]+|[0-9])"


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def _read_group(text: str, pos: int) -> tuple[str, int] | None:
    """Read a balanced {...} group starting at or after pos (skipping spaces)."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        return None
    depth = 0
    for i in range(pos, len(text)):
        char = text[i]
        if char == "\\":
            continue
        if char == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif char == "}" and text[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[pos + 1:i], i + 1
    return None


def _strip_ensuremath(body: str) -> str:
    """\\ensuremath{X} -> X (MathJax is always in math mode)."""
    while True:
        index = body.find("\\ensuremath")
        if index < 0:
            return body
        group = _read_group(body, index + len("\\ensuremath"))
        if not group:
            return body
        inner, end = group
        body = body[:index] + inner + body[end:]


def parse_macros(text: str) -> dict[str, str | list]:
    """Parse macro definitions into MathJax form: name -> body or [body, nargs]."""
    text = _strip_comments(text)
    macros: dict[str, str | list] = {}
    pattern = re.compile(
        r"\\def\s*" + _NAME
        + r"|\\(?:new|renew|provide)command\*?\s*(?:\{\s*" + _NAME + r"\s*\}|" + _NAME + r")"
        + r"|\\DeclareMathOperator(\*?)\s*\{\s*" + _NAME + r"\s*\}"
    )
    pos = 0
    while True:
        match = pattern.search(text, pos)
        if not match:
            break
        pos = match.end()
        def_name, cmd_name_braced, cmd_name_bare, operator_star, operator_name = match.groups()

        if def_name:
            group = _read_group(text, pos)
            if not group:
                continue
            body, pos = group
            name, nargs = def_name, 0
        elif operator_name:
            group = _read_group(text, pos)
            if not group:
                continue
            body, pos = group
            name, nargs = operator_name, 0
            body = f"\\operatorname{'*' if operator_star else ''}{{{body}}}"
        else:
            name = cmd_name_braced or cmd_name_bare
            nargs = 0
            arg_match = re.match(r"\s*\[(\d)\]", text[pos:])
            if arg_match:
                nargs = int(arg_match.group(1))
                pos += arg_match.end()
            group = _read_group(text, pos)
            if not group:
                continue
            body, pos = group
            is_provide = "providecommand" in match.group(0)
            if is_provide and name in macros:
                continue

        body = _strip_ensuremath(body.strip())
        for regex, replacement in WEB_REWRITES:
            body = regex.sub(replacement, body)
        macros[name] = [body, nargs] if nargs else body
    return macros


def mathjax_macros(macros_file: Path) -> dict:
    """MathJax macro table for the book (engine defaults, the macro file, then overrides)."""
    macros = dict(WEB_DEFAULTS)
    if macros_file.exists():
        macros.update(parse_macros(macros_file.read_text(encoding="utf-8")))
    macros.update(WEB_OVERRIDES)
    return dict(sorted(macros.items()))


def mathjax_macros_js(macros_file: Path) -> str:
    """Script defining window.BOOK_MACROS, loaded before the MathJax configuration."""
    body = json.dumps(mathjax_macros(macros_file), ensure_ascii=False, indent=1)
    return f"// Generated from {macros_file.name} by build/macros.py\nwindow.BOOK_MACROS = {body};\n"
