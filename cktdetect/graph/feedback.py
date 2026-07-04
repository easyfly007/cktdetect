"""Feedback structure detection (DESIGN.md P8).

Cross-coupled pairs (each transistor's gate on the other's drain) are
positive-feedback 2-cycles: the regenerative core of latches,
comparators, and LC oscillators. Detection is hash-indexed by
(gate, drain) so it stays linear on large flattened designs.

``find_feedback_loops`` is the general analysis: a signed, directed
net graph (gate->drain inverts, follower gate->source and R/C passes
do not) whose cycles classify as negative feedback (regulators,
closed-loop amplifiers, Miller compensation) or positive feedback
(latches, oscillators).
"""

from __future__ import annotations

from collections import defaultdict

from ..passes.families import (control_net, drain_net, is_diode_connected,
                               is_transistor, polarity, source_net)
from ..passes.rails import NetRole


def find_cross_coupled_pairs(circuit) -> list:
    by_gate_drain = defaultdict(list)
    transistors = [d for d in circuit.devices if is_transistor(d)]
    for dev in transistors:
        by_gate_drain[(control_net(dev), drain_net(dev))].append(dev)

    found = []
    seen = set()
    for dev in transistors:
        gate, drain = control_net(dev), drain_net(dev)
        if gate == drain:
            continue
        for other in by_gate_drain.get((drain, gate), []):
            if other is dev or control_net(other) == gate:
                continue
            key = frozenset((dev.name, other.name))
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "devices": sorted([dev.name, other.name]),
                "nets": sorted([drain, gate]),
                "polarity": polarity(dev) if polarity(dev) == polarity(other)
                            else "mixed",
            })
    found.sort(key=lambda x: x["devices"])
    return found


_MAX_LOOP_LEN = 8
_MAX_LOOPS = 30


def find_feedback_loops(circuit, infos, roles) -> list:
    """Cycles of the signed signal graph with their loop polarity.

    Edges: any non-diode transistor inverts from gate to drain
    (mirror outputs included: the diode+mirror composite inverts);
    source followers pass gate to source non-inverting; resistors and
    capacitors pass both ways (capacitor hops mark the loop as AC,
    e.g. Miller compensation).
    """
    rails = {n for n, i in infos.items()
             if i.role in (NetRole.POWER, NetRole.GROUND)}

    edges = defaultdict(list)  # net -> [(next_net, sign, device, ac)]

    def add(a, b, sign, name, ac=False):
        if a not in rails and b not in rails and a != b:
            edges[a].append((b, sign, name, ac))

    for dev in circuit.devices:
        if is_transistor(dev):
            if is_diode_connected(dev):
                continue
            gate = control_net(dev)
            if roles.get(dev.name, {}).get("role") == "source_follower":
                add(gate, source_net(dev), +1, dev.name)
            else:
                add(gate, drain_net(dev), -1, dev.name)
        elif dev.dtype.value == "resistor":
            p, n = dev.terminals.get("p"), dev.terminals.get("n")
            add(p, n, +1, dev.name)
            add(n, p, +1, dev.name)
        elif dev.dtype.value == "capacitor":
            p, n = dev.terminals.get("p"), dev.terminals.get("n")
            add(p, n, +1, dev.name, ac=True)
            add(n, p, +1, dev.name, ac=True)

    loops, seen = [], set()
    budget = [200_000]

    def dfs(start, node, path_nets, path_devs, sign, ac):
        if len(path_nets) > _MAX_LOOP_LEN or budget[0] <= 0 or \
                len(loops) >= _MAX_LOOPS:
            return
        budget[0] -= 1
        for nxt, hop_sign, name, hop_ac in edges.get(node, ()):
            if name in path_devs:
                continue  # a device edge is used at most once per loop
            if nxt == start:
                key = frozenset(path_devs | {name})
                if key not in seen:
                    seen.add(key)
                    loops.append({
                        "nets": list(path_nets),
                        "devices": sorted(path_devs | {name}),
                        "polarity": ("positive" if sign * hop_sign > 0
                                     else "negative"),
                        "ac": ac or hop_ac,
                    })
            elif nxt not in path_nets and nxt > start:
                dfs(start, nxt, path_nets + [nxt], path_devs | {name},
                    sign * hop_sign, ac or hop_ac)

    for start in sorted(edges):
        dfs(start, start, [start], frozenset(), +1, False)
    loops.sort(key=lambda l: (len(l["nets"]), l["nets"]))
    return loops
