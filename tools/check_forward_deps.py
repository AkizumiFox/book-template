#!/usr/bin/env python3
"""Fail if any result cites a result proved in a later section of the book.

Reads `_build/crossref_labels.json`, which the HTML build writes. Every label
carries the `file` it lives in and a `uses` list of the labels cited inside its
block and its proof.

Every label is placed by its file path -- chapter directory, then the section
number in the file name -- and by nothing else. **Do not mix in the `number`
field.** That field is positional: while a chapter has a gap (its section 07
not yet written, say), the build numbers section 10's results 16.9, while the
file name still says 10. An earlier version of this tool placed numbered
results by `number` and exercises by path; the two disagreed across the gap,
which reported false forward citations and could have hidden a real one.

The tool compares sections only. Labels in the same section are reported as
unordered, not as errors: the third component of `number` counts within a type
(`def-connectives` and `thm-contrapositive-equivalent` are both 0.1.1), so it
cannot order two labels, and ordering inside a section is the job of the
section's referee, who can see the text.

Run after `./build.py html`. Exits 1 if anything cites a later section.
"""
import json
import re
import sys
from pathlib import Path

INDEX = Path("_build/crossref_labels.json")


CHAPTER = re.compile(r"^ch(\d+)[^/]*/(\d+|index)")


def from_file(path):
    """Exercises and examples carry no number, but their path names the section.

    'ch15-norms/04-spectral-radius.html' -> (15, 4); an index page -> (n, 0).
    """
    m = CHAPTER.match(path or "")
    if not m:
        return None
    section = 0 if m.group(2) == "index" else int(m.group(2))
    return int(m.group(1)), section


RESULT_TYPES = {"theorem", "proposition", "corollary", "lemma"}


def list_results_citing_exercises(labels):
    """Print every result that cites an exercise. Advisory, not a gate.

    A theorem must not *rest* on an exercise -- that rule has been broken and
    repaired seven times in this book. But a result may legitimately cite one
    for attribution ("this is exercise C1, proved here in general"), and only
    reading the passage tells the two apart. So this lists candidates for a
    human to triage; it never fails the run.
    """
    rows = []
    for name, rec in sorted(labels.items()):
        if rec.get("type") not in RESULT_TYPES:
            continue
        for cited in rec.get("uses", []):
            if cited.startswith("exr-"):
                rows.append((rec.get("file", "").replace(".html", ""), name, cited))
    for path, name, cited in rows:
        print(f"{path}: {name} -> {cited}")
    print(f"\n{len(rows)} results cite an exercise. Each needs reading: a citation for "
          f"attribution is fine, a proof that depends on the exercise is not.")
    return 0


def main():
    if "--exercises" in sys.argv:
        if not INDEX.exists():
            print(f"{INDEX} not found; run ./build.py html first", file=sys.stderr)
            return 1
        return list_results_citing_exercises(
            json.loads(INDEX.read_text())["crossref_labels"]
        )

    if not INDEX.exists():
        print(f"{INDEX} not found; run ./build.py html first", file=sys.stderr)
        return 1

    labels = json.loads(INDEX.read_text())["crossref_labels"]

    order = {}
    unplaced = []
    for name, rec in labels.items():
        key = from_file(rec.get("file"))
        if key is None:
            unplaced.append(name)
        else:
            order[name] = key

    forward = []
    dangling = []
    same_section = 0
    for name, rec in sorted(labels.items()):
        here = order.get(name)
        if here is None:
            continue
        for cited in rec.get("uses", []):
            if cited not in labels:
                dangling.append((name, cited))
            elif cited in order:
                there = order[cited]
                if there > here:
                    forward.append((name, rec["number"], cited, labels[cited]["number"]))
                elif there == here:
                    same_section += 1

    for name, num, cited, cited_num in forward:
        print(f"forward: {name} ({num}) cites {cited} ({cited_num})")
    for name, cited in dangling:
        print(f"dangling: {name} cites {cited}, which is not a label")

    checked = len(order)
    if forward or dangling:
        print(f"\n{len(forward)} forward, {len(dangling)} dangling, over {checked} labels")
        return 1

    skipped = f", {len(unplaced)} could not be placed" if unplaced else ""
    print(
        f"No citation crosses into a later section: {checked} labels checked{skipped}; "
        f"{same_section} citations within a section were not ordered."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
