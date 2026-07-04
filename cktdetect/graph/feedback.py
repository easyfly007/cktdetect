"""Feedback structure detection (DESIGN.md P8).

Cross-coupled pairs (each transistor's gate on the other's drain) are
positive-feedback 2-cycles: the regenerative core of latches,
comparators, and LC oscillators. Detection is hash-indexed by
(gate, drain) so it stays linear on large flattened designs.
"""

from __future__ import annotations

from collections import defaultdict

from ..passes.families import (control_net, drain_net, is_transistor,
                               polarity)


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
