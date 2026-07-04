"""Switch- and charge-based verifiers: sample-and-hold and the Dickson
charge pump (M6+)."""

from __future__ import annotations

from ...ir.device import DeviceType
from ...passes.families import (control_net, drain_net, is_diode_connected,
                                is_transistor, polarity, source_net)
from ...passes.rails import NetRole


def _is_rail(ctx, net) -> bool:
    return ctx.infos[net].role in (NetRole.POWER, NetRole.GROUND)


def verify_sample_and_hold(ctx):
    """Pass switch into a high-impedance hold capacitor node."""
    caps = [d for d in ctx.circuit.devices
            if d.dtype is DeviceType.CAPACITOR]
    grounds = {n for n, i in ctx.infos.items() if i.role is NetRole.GROUND}

    # channel/resistive connection count per net (gates excluded)
    channel_count = {}
    for dev in ctx.circuit.devices:
        if is_transistor(dev):
            nets = (drain_net(dev), source_net(dev))
        elif dev.dtype in (DeviceType.RESISTOR, DeviceType.INDUCTOR):
            nets = tuple(dev.nets)
        else:
            continue
        for net in nets:
            channel_count[net] = channel_count.get(net, 0) + 1

    for switch in ctx.transistors:
        if is_diode_connected(switch):
            continue
        gate = control_net(switch)
        if ctx.infos[gate].role is not NetRole.BIAS:
            continue  # clock/control gate shows up as a dc-driven bias net
        d, s = drain_net(switch), source_net(switch)
        if _is_rail(ctx, d) or _is_rail(ctx, s):
            continue
        for hold, other in ((d, s), (s, d)):
            hold_caps = [c for c in caps if hold in c.nets
                         and any(n in grounds for n in c.nets)]
            if not hold_caps:
                continue
            if channel_count.get(hold, 0) != 1:
                continue  # hold node must see only the switch channel
            evidence = [
                f"pass switch {switch.name} (gate '{gate}' is a "
                f"dc-controlled clock) between '{other}' and '{hold}'",
                f"hold capacitor {hold_caps[0].name} on the "
                f"high-impedance node '{hold}'",
            ]
            confidence = 0.75
            buffer = next(
                (dev for dev in ctx.transistors
                 if control_net(dev) == hold
                 and ctx.role(dev.name) == "source_follower"), None)
            if buffer:
                confidence += 0.1
                evidence.append(f"output buffer {buffer.name} senses the "
                                f"hold node")
            return {"type": "sample_and_hold",
                    "confidence": round(confidence, 3),
                    "evidence": evidence}
    return None


def verify_switched_capacitor(ctx):
    """Multi-phase switch network over capacitors.

    Required: at least two clock nets, each gating >= 3 pass switches
    (non-diode transistors with no channel terminal on power), and
    capacitors on the switched nets. An embedded amplifier still shows
    up as a lower-ranked verdict -- the circuit as a whole is SC.
    """
    from collections import defaultdict

    caps = [c for c in ctx.circuit.devices
            if c.dtype is DeviceType.CAPACITOR]
    if len(caps) < 2:
        return None

    power = {n for n, i in ctx.infos.items() if i.role is NetRole.POWER}
    switches_by_gate = defaultdict(list)
    for dev in ctx.transistors:
        if is_diode_connected(dev):
            continue
        d, s = drain_net(dev), source_net(dev)
        gate = control_net(dev)
        if d in power or s in power or gate in (d, s):
            continue
        switches_by_gate[gate].append(dev)

    clocks = sorted(g for g, devs in switches_by_gate.items()
                    if len(devs) >= 3)
    if len(clocks) < 2:
        return None

    switched_nets = set()
    n_switches = 0
    for clock in clocks:
        for dev in switches_by_gate[clock]:
            switched_nets.update((drain_net(dev), source_net(dev)))
            n_switches += 1
    sc_caps = [c for c in caps if set(c.nets) & switched_nets]
    if len(sc_caps) < 2:
        return None

    evidence = [
        f"{len(clocks)} switch phases ({','.join(clocks)}) driving "
        f"{n_switches} pass switches",
        f"{len(sc_caps)} capacitors on the switched nets "
        f"({','.join(c.name for c in sc_caps[:6])})",
    ]
    return {"type": "switched_capacitor_circuit", "confidence": 0.85,
            "evidence": evidence}


def verify_dickson_charge_pump(ctx):
    """Chain of diode-connected devices with pump capacitors driven by
    clock nets on the internal nodes."""
    diodes = [d for d in ctx.transistors
              if is_diode_connected(d) and polarity(d) is not None]
    caps = [c for c in ctx.circuit.devices
            if c.dtype is DeviceType.CAPACITOR]

    # chain the diodes: next stage's drain(+gate) sits on this source
    by_drain = {drain_net(d): d for d in diodes}
    chains = []
    heads = [d for d in diodes if drain_net(d) not in
             {source_net(x) for x in diodes}]
    for head in heads:
        chain, dev = [head], head
        while source_net(dev) in by_drain:
            dev = by_drain[source_net(dev)]
            chain.append(dev)
        chains.append(chain)

    for chain in sorted(chains, key=len, reverse=True):
        if len(chain) < 3:
            continue
        internal = [source_net(d) for d in chain[:-1]]
        pumped, clocks = [], set()
        for net in internal:
            for cap in caps:
                if net not in cap.nets:
                    continue
                other = cap.nets[0] if cap.nets[1] == net else cap.nets[1]
                if not _is_rail(ctx, other):
                    pumped.append(net)
                    clocks.add(other)
                    break
        if len(pumped) < 2:
            continue
        evidence = [
            f"{len(chain)} diode-connected devices in series "
            f"({' -> '.join(d.name for d in chain)})",
            f"pump capacitors on internal nodes "
            f"{','.join(pumped)}",
        ]
        confidence = 0.8
        if len(clocks) >= 2:
            confidence += 0.05
            evidence.append(f"alternating clock nets "
                            f"{','.join(sorted(clocks))}")
        return {"type": "dickson_charge_pump",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None
