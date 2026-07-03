from __future__ import annotations

import re
from pathlib import Path

from .spectre import SpectreParser
from .spice import SpiceParser

__all__ = ["SpiceParser", "SpectreParser", "parse_netlist"]

_SPECTRE_LANG_RE = re.compile(r"^\s*simulator\s+lang\s*=\s*spectre",
                              re.IGNORECASE | re.MULTILINE)


def parse_netlist(path, dialect: str = "auto"):
    """Parse a netlist file, auto-detecting the dialect by default.

    Spectre is chosen for ``.scs`` files or when the text declares
    ``simulator lang=spectre``; everything else parses as generic SPICE.
    """
    path = Path(path)
    text = path.read_text(errors="replace")
    if dialect == "auto":
        if path.suffix.lower() == ".scs" or _SPECTRE_LANG_RE.search(text):
            dialect = "spectre"
        else:
            dialect = "spice"
    parser = SpectreParser() if dialect == "spectre" else SpiceParser()
    return parser.parse_string(text, source=str(path))
