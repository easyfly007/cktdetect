"""RF structure detection: LC tanks (DESIGN.md M4).

Styles:
- parallel:      L and C share both nets
- differential:  two inductors from a common net, C across the far ends
- single_ended:  L from a rail to a net, C from that net to a rail
"""

from __future__ import annotations

from itertools import combinations

from ..ir.device import DeviceType
from ..passes.rails import NetRole


def _other(dev, net):
    nets = dev.nets
    return nets[1] if nets[0] == net else nets[0]


def find_lc_tanks(circuit, infos) -> list:
    rails = {n for n, i in infos.items()
             if i.role in (NetRole.POWER, NetRole.GROUND)}
    inductors = [d for d in circuit.devices
                 if d.dtype is DeviceType.INDUCTOR]
    capacitors = [d for d in circuit.devices
                  if d.dtype is DeviceType.CAPACITOR]
    tanks = []

    for ind in inductors:
        lnets = set(ind.nets)
        for cap in capacitors:
            if set(cap.nets) == lnets:
                tanks.append({
                    "style": "parallel", "nets": sorted(lnets - rails),
                    "inductors": [ind.name], "capacitors": [cap.name],
                })

    for l1, l2 in combinations(inductors, 2):
        shared = set(l1.nets) & set(l2.nets)
        if len(shared) != 1:
            continue
        a, b = _other(l1, next(iter(shared))), _other(l2, next(iter(shared)))
        for cap in capacitors:
            if set(cap.nets) == {a, b}:
                tanks.append({
                    "style": "differential", "nets": sorted((a, b)),
                    "common_net": next(iter(shared)),
                    "inductors": [l1.name, l2.name],
                    "capacitors": [cap.name],
                })

    for ind in inductors:
        rail_side = [n for n in ind.nets if n in rails]
        if len(rail_side) != 1:
            continue
        x = _other(ind, rail_side[0])
        for cap in capacitors:
            if x in cap.nets and _other(cap, x) in rails:
                tanks.append({
                    "style": "single_ended", "nets": [x],
                    "inductors": [ind.name], "capacitors": [cap.name],
                })
    return tanks
