"""PDK profile: user-supplied mapping from PDK-specific names to device
types and rail roles.

JSON format::

    {
      "models":      {"sky130_fd_pr__nfet*": "nmos",
                      "sky130_fd_pr__pfet*": "pmos",
                      "my_vert_pnp": "pnp"},
      "power_nets":  ["vpwr*", "vdd_*"],
      "ground_nets": ["vgnd*"]
    }

Model patterns are matched exact-first, then by glob (fnmatch). All
names are compared lowercase, matching the parser's normalization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class PdkProfile:
    models: dict = field(default_factory=dict)
    power_nets: list = field(default_factory=list)
    ground_nets: list = field(default_factory=list)

    def model_type(self, model: str | None) -> str | None:
        if model is None:
            return None
        if model in self.models:
            return self.models[model]
        for pattern in sorted(self.models):
            if fnmatch(model, pattern):
                return self.models[pattern]
        return None

    def net_role(self, basename: str) -> str | None:
        for pattern in self.power_nets:
            if fnmatch(basename, pattern):
                return "power"
        for pattern in self.ground_nets:
            if fnmatch(basename, pattern):
                return "ground"
        return None


def load_profile(path) -> PdkProfile:
    data = json.loads(Path(path).read_text())
    return PdkProfile(
        models={str(k).lower(): str(v).lower()
                for k, v in data.get("models", {}).items()},
        power_nets=[str(p).lower() for p in data.get("power_nets", [])],
        ground_nets=[str(p).lower() for p in data.get("ground_nets", [])],
    )
