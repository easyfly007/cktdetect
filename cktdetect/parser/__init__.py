from __future__ import annotations

import re
from pathlib import Path

from .spectre import SpectreParser
from .spice import SpiceParser

__all__ = ["SpiceParser", "SpectreParser", "parse_netlist"]

_SPECTRE_LANG_RE = re.compile(r"^\s*simulator\s+lang\s*=\s*spectre",
                              re.IGNORECASE | re.MULTILINE)
# dot-less scope keywords only exist in Spectre-style netlists (the
# lang line is often commented out in tool exports, e.g. MAGICAL)
_SPECTRE_SCOPE_RE = re.compile(r"^\s*(subckt|topckt|ends)\s",
                               re.IGNORECASE | re.MULTILINE)


def parse_netlist(path, dialect: str = "auto", profile=None):
    """Parse a netlist file, auto-detecting the dialect by default.

    Spectre is chosen for ``.scs`` files or when the text declares
    ``simulator lang=spectre``; ``.cdl`` files and everything else parse
    as generic SPICE (the SPICE frontend handles CDL's common syntax).
    ``profile`` is an optional PdkProfile for model-name mapping.
    """
    path = Path(path)
    text = path.read_text(errors="replace")
    if dialect == "auto":
        if path.suffix.lower() == ".scs" or _SPECTRE_LANG_RE.search(text) \
                or _SPECTRE_SCOPE_RE.search(text):
            dialect = "spectre"
        else:
            dialect = "spice"  # includes CDL
    parser = (SpectreParser(profile=profile) if dialect == "spectre"
              else SpiceParser(profile=profile))
    parser._base_dir = path.parent
    return parser.parse_string(text, source=str(path))
