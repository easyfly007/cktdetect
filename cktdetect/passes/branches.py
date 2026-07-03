"""DC branch decomposition (DESIGN.md P5).

Removing the rail nets and following only DC-conducting terminals
(channel, R/L, sources; capacitors block) splits the circuit into
"legs": stacks of devices between the rails. A net carrying three or
more conducting terminals inside a branch is a fork (e.g. the tail node
of a differential pair).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..ir.circuit import Circuit
from .families import conducting_nets
from .rails import NetRole


@dataclass
class Branch:
    devices: list = field(default_factory=list)
    rails: list = field(default_factory=list)
    internal_nets: list = field(default_factory=list)
    forks: list = field(default_factory=list)


def _rails(infos) -> set:
    return {net for net, info in infos.items()
            if info.role in (NetRole.POWER, NetRole.GROUND)}


def decompose_branches(circuit: Circuit, infos: dict):
    """Return (branches, non_dc_device_names)."""
    rails = _rails(infos)

    dev_nets = {}
    cond_count = Counter()
    non_dc = []
    for dev in circuit.devices:
        nets = conducting_nets(dev)
        if not nets:
            non_dc.append(dev.name)
            continue
        dev_nets[dev.name] = nets
        for net in nets:
            cond_count[net] += 1

    # union-find over devices joined through non-rail conducting nets
    parent = {name: name for name in dev_nets}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    seen_net = {}
    for name, nets in dev_nets.items():
        for net in nets:
            if net in rails:
                continue
            if net in seen_net:
                union(name, seen_net[net])
            else:
                seen_net[net] = name

    order = {dev.name: i for i, dev in enumerate(circuit.devices)}
    groups = {}
    for name in dev_nets:
        groups.setdefault(find(name), []).append(name)

    branches = []
    for members in groups.values():
        members.sort(key=order.get)
        rail_nets, internal = set(), set()
        for name in members:
            for net in dev_nets[name]:
                (rail_nets if net in rails else internal).add(net)
        branches.append(Branch(
            devices=members,
            rails=sorted(rail_nets),
            internal_nets=sorted(internal),
            forks=sorted(n for n in internal if cond_count[n] >= 3),
        ))
    branches.sort(key=lambda b: order[b.devices[0]])
    return branches, non_dc


def dc_domains(circuit: Circuit, infos: dict) -> list:
    """Group non-rail nets into DC-connected domains (cut by capacitors)."""
    rails = _rails(infos)
    nets = sorted(n for n in circuit.nets() if n not in rails)
    parent = {net: net for net in nets}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for dev in circuit.devices:
        conn = [n for n in conducting_nets(dev) if n not in rails]
        for a, b in zip(conn, conn[1:]):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

    groups = {}
    for net in nets:
        groups.setdefault(find(net), []).append(net)
    return sorted(sorted(g) for g in groups.values())
