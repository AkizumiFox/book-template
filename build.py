#!/usr/bin/env python3
"""Shebang-executable entry point for the build system.

Run as: ./build.py html | pdf | book | all | serve | check | doctor | deploy | clean [file] [--book DIR]
   or:  python build.py html ...
   or:  python -m build html ...
"""
from build.cli import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)
