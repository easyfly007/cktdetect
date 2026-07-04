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
