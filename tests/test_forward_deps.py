"""Tests for tools/check_forward_deps.py, the gate against citing a later section."""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "check_forward_deps.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("check_forward_deps", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def label(file, number, kind="theorem", uses=()):
    return {"file": file, "number": number, "type": kind, "uses": list(uses)}


def run(labels):
    """Run the gate on a synthetic index; return (exit code, printed output)."""
    tool = load_tool()
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "crossref_labels.json"
        index.write_text(json.dumps({"crossref_labels": labels}))
        tool.INDEX = index
        out = io.StringIO()
        with redirect_stdout(out):
            code = tool.main()
    return code, out.getvalue()


class TestForwardDeps(unittest.TestCase):

    def test_backward_citation_passes(self):
        code, _ = run({
            "thm-early": label("ch01-a/02-x.html", "1.2.1"),
            "thm-late": label("ch03-b/01-y.html", "3.1.1", uses=["thm-early"]),
        })
        self.assertEqual(code, 0)

    def test_forward_citation_fails(self):
        code, out = run({
            "thm-early": label("ch01-a/02-x.html", "1.2.1", uses=["thm-late"]),
            "thm-late": label("ch03-b/01-y.html", "3.1.1"),
        })
        self.assertEqual(code, 1)
        self.assertIn("forward: thm-early", out)

    def test_dangling_citation_fails(self):
        code, out = run({
            "thm-a": label("ch01-a/01-x.html", "1.1.1", uses=["thm-missing"]),
        })
        self.assertEqual(code, 1)
        self.assertIn("dangling: thm-a", out)

    def test_gap_in_section_numbers_is_not_a_forward_citation(self):
        # Section 07 is not written yet, so the build numbers section 10's
        # results 16.9 while its file name still says 10. A result citing an
        # exercise in its own file must not be reported as forward. An earlier
        # version placed results by `number` and exercises by path, and failed.
        code, out = run({
            "cor-x": label("ch16-v/10-inertia.html", "16.9.2", uses=["exr-x-c1"]),
            "exr-x-c1": label("ch16-v/10-inertia.html", "", kind="exercise"),
        })
        self.assertEqual(code, 0, out)

    def test_forward_citation_across_a_gap_is_caught(self):
        # Section 06 citing section 09 across the missing 07 and 08: forward,
        # even though the positional numbers (16.6 and 16.7) sit side by side.
        code, out = run({
            "thm-six": label("ch16-v/06-a.html", "16.6.1", uses=["thm-nine"]),
            "thm-nine": label("ch16-v/09-b.html", "16.7.1"),
        })
        self.assertEqual(code, 1)
        self.assertIn("forward: thm-six", out)

    def test_same_section_is_unordered_not_an_error(self):
        # Labels sharing a section are not ordered by this tool, even when the
        # cited one has a larger third component.
        code, _ = run({
            "def-a": label("ch00-f/01-logic.html", "0.1.1", kind="definition"),
            "thm-a": label("ch00-f/01-logic.html", "0.1.1", uses=["def-b"]),
            "def-b": label("ch00-f/01-logic.html", "0.1.2", kind="definition"),
        })
        self.assertEqual(code, 0)

    def test_index_page_precedes_section_one(self):
        code, _ = run({
            "thm-intro": label("ch05-p/index.html", "5.0.1", uses=["thm-one"]),
            "thm-one": label("ch05-p/01-a.html", "5.1.1"),
        })
        self.assertEqual(code, 1)

    def test_lettered_chapter_directory_sorts_after_that_chapter(self):
        # `ch23a-notation` is an appendix to Chapter 23 and must keep its name:
        # `latex`/`theorems.lua` need it to read as chapter 23. Its index page
        # used to key as (23, 0) -- section zero -- so it sat *before* Chapter
        # 23's own sections, and a label put there would cite them "forward".
        tool = load_tool()
        self.assertGreater(
            tool.from_file("ch23a-notation/index.html"),
            tool.from_file("ch23-applied/12-last.html"),
        )
        code, out = run({
            "thm-notation": label("ch23a-notation/index.html", "23.0.1",
                                  uses=["thm-last"]),
            "thm-last": label("ch23-applied/12-last.html", "23.12.1"),
        })
        self.assertEqual(code, 0, out)

    def test_lettered_chapter_directory_still_cannot_cite_a_later_chapter(self):
        code, out = run({
            "thm-notation": label("ch23a-notation/index.html", "23.0.1",
                                  uses=["thm-later"]),
            "thm-later": label("ch24-x/01-a.html", "24.1.1"),
        })
        self.assertEqual(code, 1)
        self.assertIn("forward: thm-notation", out)


if __name__ == "__main__":
    unittest.main()
