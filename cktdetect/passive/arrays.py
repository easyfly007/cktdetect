"""Weighted resistor array detection: the R-2R DAC ladder (M6+).

An R-2R ladder is a backbone chain of series resistors of value R whose
every node also carries a branch resistor of value 2R (the bit inputs
and the ground terminator).
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.device import DeviceType
from ..passes.families import is_transistor
from ..passes.rails import NetRole

_REL_TOL = 0.05


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _REL_TOL * max(abs(a), abs(b))


def find_r2r_ladder(circuit, infos):
    """Return ladder info or None. Only for transistor-free circuits."""
    if any(is_transistor(d) for d in circuit.devices):
        return None
    resistors = [d for d in circuit.devices
                 if d.dtype is DeviceType.RESISTOR
                 and isinstance(d.params.get("value"), (int, float))]
    if len(resistors) < 5:  # 3 series + 2 branches is the minimum worth naming
        return None

    values = sorted(r.params["value"] for r in resistors)
    unit = values[0]
    series = [r for r in resistors if _close(r.params["value"], unit)]
    branches = [r for r in resistors if _close(r.params["value"], 2 * unit)]
    if len(series) < 2 or len(branches) < 3:
        return None

    # walk the backbone chain of series resistors
    adjacency = defaultdict(list)
    for r in series:
        p, n = r.terminals["p"], r.terminals["n"]
        adjacency[p].append((r, n))
        adjacency[n].append((r, p))
    ends = sorted(n for n, edges in adjacency.items() if len(edges) == 1)
    if not ends:
        return None
    chain, used = [ends[0]], set()
    while True:
        steps = [(r, other) for r, other in adjacency[chain[-1]]
                 if r.name not in used]
        if len(steps) != 1:
            break
        r, other = steps[0]
        used.add(r.name)
        chain.append(other)
    if len(used) != len(series) or len(chain) < 3:
        return None  # not a single simple backbone

    # every backbone node must carry a 2R branch
    branch_nets = defaultdict(list)
    for r in branches:
        for net in r.nets:
            branch_nets[net].append(r)
    if not all(branch_nets[net] for net in chain):
        return None

    grounds = {n for n, i in infos.items() if i.role is NetRole.GROUND}
    terminator = next(
        (r.name for net in chain for r in branch_nets[net]
         if any(n in grounds for n in r.nets)), None)
    return {
        "bits": len(chain),
        "backbone": chain,
        "unit_value": unit,
        "series": sorted(r.name for r in series),
        "branches": sorted(r.name for r in branches),
        "terminator": terminator,
    }
