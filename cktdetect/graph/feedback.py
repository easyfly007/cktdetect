"""Feedback structure detection (DESIGN.md P8).

Cross-coupled pairs (each transistor's gate on the other's drain) are
positive-feedback 2-cycles: the regenerative core of latches,
comparators, and LC oscillators.
"""

from __future__ import annotations

from itertools import combinations

from ..passes.families import (control_net, drain_net, is_transistor,
                               polarity)


def find_cross_coupled_pairs(circuit) -> list:
    transistors = [d for d in circuit.devices if is_transistor(d)]
    found = []
    for a, b in combinations(transistors, 2):
        if control_net(a) == control_net(b):
            continue
        if control_net(a) == drain_net(b) and control_net(b) == drain_net(a):
            found.append({
                "devices": sorted([a.name, b.name]),
                "nets": sorted([drain_net(a), drain_net(b)]),
                "polarity": polarity(a) if polarity(a) == polarity(b)
                            else "mixed",
            })
    found.sort(key=lambda x: x["devices"])
    return found
