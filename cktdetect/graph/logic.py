"""Inverter and inverter-ring detection.

A CMOS inverter is a complementary pair: NMOS (source on ground) and
PMOS (source on power) sharing both gate and drain nets. Digital logic
itself is out of scope, but inverters are the primitive for the ring
oscillator (odd inverting loop) and for keeping digital chains out of
the analog verifiers.
"""

from __future__ import annotations

from ..passes.families import (control_net, drain_net, is_transistor,
                               polarity, source_net)
from ..passes.rails import NetRole


def find_inverters(circuit, infos) -> list:
    """Return [{"input", "output", "devices"}] for complementary pairs."""
    nmos, pmos = [], []
    for dev in circuit.devices:
        if not is_transistor(dev):
            continue
        if polarity(dev) == "n" and \
                infos[source_net(dev)].role is NetRole.GROUND:
            nmos.append(dev)
        elif polarity(dev) == "p" and \
                infos[source_net(dev)].role is NetRole.POWER:
            pmos.append(dev)

    inverters = []
    for n_dev in nmos:
        for p_dev in pmos:
            if control_net(n_dev) == control_net(p_dev) and \
                    drain_net(n_dev) == drain_net(p_dev) and \
                    control_net(n_dev) != drain_net(n_dev):
                inverters.append({
                    "input": control_net(n_dev),
                    "output": drain_net(n_dev),
                    "devices": sorted([n_dev.name, p_dev.name]),
                })
    inverters.sort(key=lambda inv: inv["devices"])
    return inverters


def find_inverting_loops(circuit, infos) -> list:
    """Odd/even cycles in the net-level gate->drain relation.

    Each signal-gated, non-diode transistor contributes an inverting hop
    from its gate net to its drain net. This generalizes the CMOS
    inverter ring to current-starved and single-ended stages: any odd
    cycle of length >= 3 is a ring oscillator core.
    """
    from collections import defaultdict

    from ..passes.families import is_diode_connected

    rails = {n for n, i in infos.items()
             if i.role in (NetRole.POWER, NetRole.GROUND)}
    edges = defaultdict(set)
    hop_devices = defaultdict(list)
    for dev in circuit.devices:
        if not is_transistor(dev) or is_diode_connected(dev):
            continue
        gate, drain = control_net(dev), drain_net(dev)
        if gate in rails or drain in rails or gate == drain:
            continue
        if infos[gate].role is not NetRole.SIGNAL:
            continue
        edges[gate].add(drain)
        hop_devices[(gate, drain)].append(dev.name)

    loops, seen = [], set()
    limit = 15
    budget = [200_000]  # step budget: keeps huge flat designs linear-ish

    def dfs(start, node, path):
        if len(path) > limit or budget[0] <= 0:
            return
        budget[0] -= 1
        for nxt in sorted(edges.get(node, ())):
            if nxt == start:
                key = frozenset(path)
                if key not in seen:
                    seen.add(key)
                    devices = sorted({name
                                      for a, b in zip(path, path[1:] + [start])
                                      for name in hop_devices[(a, b)]})
                    loops.append({"nets": list(path), "devices": devices})
            elif nxt not in path and nxt > start:
                dfs(start, nxt, path + [nxt])

    for start in sorted(edges):
        dfs(start, start, [start])
    loops.sort(key=lambda l: (len(l["nets"]), l["nets"]))
    return loops


def find_inverter_rings(inverters) -> list:
    """Cycles in the inverter input->output relation.

    Returns [{"length", "nets", "inverters"}]; odd length >= 3 is a
    ring oscillator, even length 2 is a latch core.
    """
    step = {}
    for inv in inverters:
        step.setdefault(inv["input"], inv)

    rings = []
    seen = set()
    for start in sorted(step):
        if start in seen:
            continue
        chain, net = [], start
        path_index = {}
        while net in step and net not in path_index:
            path_index[net] = len(chain)
            chain.append(step[net])
            net = step[net]["output"]
        if net in path_index:  # closed a cycle
            cycle = chain[path_index[net]:]
            rings.append({
                "length": len(cycle),
                "nets": [inv["input"] for inv in cycle],
                "inverters": [inv["devices"] for inv in cycle],
            })
            seen.update(inv["input"] for inv in cycle)
        seen.update(path_index)
    return rings
