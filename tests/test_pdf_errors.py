"""Tests for build.pdf._latex_error_lines, which decides whether a PDF built cleanly.

pdflatex runs in nonstopmode and writes a PDF even after an error, so the build
judges success by the error lines, not by the file existing. Twelve algorithm
blocks and 26 other sections once shipped damaged because only existence was
checked.
"""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build.pdf import _latex_error_lines  # noqa: E402


def run(stdout):
    return _latex_error_lines(types.SimpleNamespace(stdout=stdout))


class TestLatexErrorLines(unittest.TestCase):

    def test_math_error_is_caught(self):
        out = "! Missing $ inserted.\n<inserted text> \n                $\nl.1488 \\begin{aligned}\n"
        self.assertEqual(run(out), ["! Missing $ inserted."])

    def test_undefined_environment_is_caught(self):
        out = ("! LaTeX Error: Environment algorithm undefined.\n\nSee the LaTeX manual.\n"
               " ...\n\nl.19511 \\begin{algorithm}\n")
        self.assertEqual(len(run(out)), 1)

    def test_fatal_stop_is_caught(self):
        out = "! Emergency stop.\n<*> book.tex\n"
        self.assertEqual(len(run(out)), 1)

    def test_overfull_box_dump_is_not_an_error(self):
        # A wrapped continuation line of an Overfull \hbox dump can begin with "!".
        out = ("Overfull \\hbox (32.7pt too wide) in paragraph at lines 1601--1604\n"
               "[]\\OT1/cmr/m/n/10.95 Deduce\n"
               "! []\\OT1/cmr/m/n/10.95 (\\OT1/cmr/bx/n/10.95 w[]\n []\n\n")
        self.assertEqual(run(out), [])

    def test_clean_run_has_no_errors(self):
        self.assertEqual(run("Output written on x.pdf (3 pages).\n"), [])


if __name__ == "__main__":
    unittest.main()
