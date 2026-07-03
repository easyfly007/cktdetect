"""Branch-level signal-flow graph (DESIGN.md P7).

Nodes are branches; a directed edge exists when a device's drain in one
branch drives a device's gate (on a signal net). Capacitors between a
drain net and a gate net add AC-coupling edges. The graph is tiny even
for large circuits, which is where architecture-level analysis runs.
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.device import DeviceType
from ..passes.families import (control_net, drain_net, is_transistor,
                               source_net)
from ..passes.rails import NetRole

_INVERTING_ROLES = {"common_source", "amplifier", "diff_input"}


def build_stage_edges(circuit, infos, branches, roles) -> list:
    branch_of = {}
    for index, branch in enumerate(branches):
        for name in branch.devices:
            branch_of[name] = index

    transistors = [d for d in circuit.devices if is_transistor(d)]
    drains = defaultdict(list)
    gates = defaultdict(list)
    for dev in transistors:
        drains[drain_net(dev)].append(dev)
        gate = control_net(dev)
        if infos[gate].role is NetRole.SIGNAL:
            gates[gate].append(dev)
        # follower outputs drive from their source net
        if roles.get(dev.name, {}).get("role") == "source_follower":
            drains[source_net(dev)].append(dev)

    edges = []
    for net, receivers in gates.items():
        for recv in receivers:
            for drv in drains[net]:
                if drv is recv:
                    continue
                edges.append({
                    "from": branch_of.get(drv.name),
                    "to": branch_of.get(recv.name),
                    "net": net,
                    "driver": drv.name,
                    "receiver": recv.name,
                    "kind": "dc",
                    "inverting": roles.get(recv.name, {}).get("role")
                                 in _INVERTING_ROLES,
                })

    # AC coupling: capacitor bridging a drain net into a gate net
    for cap in circuit.devices:
        if cap.dtype is not DeviceType.CAPACITOR:
            continue
        p, n = cap.terminals.get("p"), cap.terminals.get("n")
        for a, b in ((p, n), (n, p)):
            for drv in drains.get(a, []):
                for recv in gates.get(b, []):
                    if drv is recv:
                        continue
                    edges.append({
                        "from": branch_of.get(drv.name),
                        "to": branch_of.get(recv.name),
                        "net": b,
                        "driver": drv.name,
                        "receiver": recv.name,
                        "kind": "ac",
                        "via": cap.name,
                        "inverting": roles.get(recv.name, {}).get("role")
                                     in _INVERTING_ROLES,
                    })
    return edges
