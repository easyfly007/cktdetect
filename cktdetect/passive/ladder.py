"""Passive network analysis (DESIGN.md section 4, passive path).

Circuits without transistors have no DC legs; instead we walk the
series/shunt ladder from the driven input net and classify it:
series L / shunt C push lowpass, series C / shunt L push highpass,
both together indicate a bandpass-like network.

``r_divider_taps`` is shared with the LDO verifier: it returns the
intermediate nets of resistor-only paths from a net down to ground.
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.device import DeviceType
from ..passes.families import is_transistor
from ..passes.rails import NetRole

_PASSIVE = (DeviceType.RESISTOR, DeviceType.CAPACITOR, DeviceType.INDUCTOR)
_REACTIVE = (DeviceType.CAPACITOR, DeviceType.INDUCTOR)
_SOURCES = (DeviceType.VSOURCE, DeviceType.ISOURCE)


def r_divider_taps(circuit, infos, start: str) -> set:
    """Intermediate nets of resistor chains from ``start`` to ground."""
    grounds = {n for n, i in infos.items() if i.role is NetRole.GROUND}
    adj = defaultdict(list)
    for dev in circuit.devices:
        if dev.dtype is not DeviceType.RESISTOR:
            continue
        p, n = dev.terminals.get("p"), dev.terminals.get("n")
        adj[p].append((dev.name, n))
        adj[n].append((dev.name, p))

    taps = set()

    def walk(net, path, used):
        for rname, other in adj[net]:
            if rname in used:
                continue
            if other in grounds:
                taps.update(path)
            elif other != start and other not in path:
                walk(other, path | {other}, used | {rname})

    walk(start, frozenset(), frozenset())
    return taps


def analyze_passive_network(circuit, infos):
    """Classify a transistor-free ladder network; None when not applicable."""
    if any(is_transistor(d) for d in circuit.devices):
        return None
    passives = [d for d in circuit.devices if d.dtype in _PASSIVE]
    if not passives:
        return None

    rails = {n for n, i in infos.items()
             if i.role in (NetRole.POWER, NetRole.GROUND)}

    # input: the non-rail net a source drives (prefer AC sources)
    candidates = []
    for dev in circuit.devices:
        if dev.dtype not in _SOURCES:
            continue
        nets = [n for n in dev.terminals.values() if n not in rails]
        if nets:
            has_ac = "ac" in str(dev.params.get("spec", ""))
            candidates.append((0 if has_ac else 1, nets[0]))
    if not candidates:
        return None
    input_net = sorted(candidates)[0][1]

    series_adj = defaultdict(list)   # net -> [(dev, other_net)]
    shunt_map = defaultdict(list)    # net -> [dev to rail]
    for dev in passives:
        p, n = dev.terminals.get("p"), dev.terminals.get("n")
        if p in rails and n in rails:
            continue
        if p in rails or n in rails:
            shunt_map[n if p in rails else p].append(dev)
        else:
            series_adj[p].append((dev, n))
            series_adj[n].append((dev, p))

    # walk the ladder from the input
    chain, series = [input_net], []
    current, prev = input_net, None
    visited = {input_net}
    while True:
        steps = [(dev, other) for dev, other in series_adj[current]
                 if other != prev and other not in visited]
        if len(steps) != 1:
            break  # end of ladder, or not a simple ladder
        dev, other = steps[0]
        series.append(dev)
        chain.append(other)
        visited.add(other)
        prev, current = current, other

    shunts = [d for net in chain for d in shunt_map[net]]
    elements = series + shunts
    reactive = [d for d in elements if d.dtype in _REACTIVE]

    low = any(d.dtype is DeviceType.INDUCTOR for d in series) or \
        any(d.dtype is DeviceType.CAPACITOR for d in shunts)
    high = any(d.dtype is DeviceType.CAPACITOR for d in series) or \
        any(d.dtype is DeviceType.INDUCTOR for d in shunts)
    kind = ("bandpass" if low and high else
            "lowpass" if low else
            "highpass" if high else None)

    return {
        "input_net": input_net,
        "output_net": chain[-1],
        "chain": chain,
        "series": [d.name for d in series],
        "shunts": [d.name for d in shunts],
        "order": len(reactive),
        "kind": kind,
    }
