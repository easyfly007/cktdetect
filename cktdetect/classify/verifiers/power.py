"""Power-management verifiers: LDO and bandgap core (DESIGN.md M3)."""

from __future__ import annotations

from itertools import combinations

from ...ir.device import DeviceType
from ...passes.families import (control_net, drain_net, is_diode_connected,
                                polarity, source_net)
from ...passes.rails import NetRole
from ...passive.ladder import r_divider_taps

_BJT = (DeviceType.NPN, DeviceType.PNP, DeviceType.BJT)


def verify_ldo(ctx):
    """Error amplifier + pass device + resistive feedback to the input."""
    for pair in ctx.pairs:
        amp_nets = set(pair["outputs"])
        candidates = []
        for dev in ctx.transistors:
            if control_net(dev) not in amp_nets:
                continue
            role = ctx.role(dev.name)
            if role in ("common_source", "amplifier") and \
                    ctx.infos[source_net(dev)].role is NetRole.POWER:
                candidates.append((dev, drain_net(dev)))
            elif role == "source_follower":
                candidates.append((dev, source_net(dev)))
        for pass_dev, vout in candidates:
            taps = r_divider_taps(ctx.circuit, ctx.infos, vout)
            feedback = taps & set(pair["inputs"])
            if not feedback:
                continue
            tap = sorted(feedback)[0]
            evidence = [
                f"error amplifier: pair {','.join(pair['devices'])}",
                f"pass device {pass_dev.name} regulates '{vout}'",
                f"resistive divider from '{vout}' feeds tap '{tap}' "
                f"back to the amplifier input (negative feedback)",
            ]
            confidence = 0.85
            if any(d.dtype is DeviceType.CAPACITOR and vout in d.nets
                   for d in ctx.circuit.devices):
                confidence += 0.05
                evidence.append(f"output capacitor on '{vout}'")
            return {"type": "ldo", "confidence": round(confidence, 3),
                    "evidence": evidence}
    return None


def _area(dev) -> float:
    area = dev.params.get("area", 1.0)
    m = dev.params.get("m", 1.0)
    if isinstance(area, (int, float)) and isinstance(m, (int, float)):
        return float(area) * float(m)
    return 1.0


def verify_bandgap(ctx):
    """Delta-Vbe pair with emitter resistor plus a current mirror."""
    if not ctx.mirrors:
        return None
    bjts = [d for d in ctx.transistors if d.dtype in _BJT]
    resistors = [d for d in ctx.circuit.devices
                 if d.dtype is DeviceType.RESISTOR]

    def emitter_rs(dev):
        emitter = source_net(dev)
        return [r for r in resistors if emitter in r.nets]

    def is_rail(net):
        return ctx.infos[net].role in (NetRole.POWER, NetRole.GROUND)

    mirror_devices = set()
    for m in ctx.mirrors:
        mirror_devices.add(m["reference"])
        mirror_devices.update(o["device"] for o in m["outputs"])

    for a, b in combinations(bjts, 2):
        if polarity(a) is None or polarity(a) != polarity(b):
            continue
        ra, rb = emitter_rs(a), emitter_rs(b)
        if bool(ra) == bool(rb):
            continue  # exactly one branch is degenerated
        deg, plain = (a, b) if ra else (b, a)
        r_deg = (ra or rb)[0]
        if is_rail(source_net(deg)):
            continue
        evidence = [
            f"delta-Vbe core: {deg.name} with emitter resistor "
            f"{r_deg.name}, {plain.name} direct",
            f"current mirror {ctx.mirrors[0]['reference']} forces the "
            f"branch currents",
        ]
        confidence = 0.75
        ratio = _area(deg) / _area(plain)
        if ratio > 1:
            confidence += 0.1
            evidence.append(f"junction area ratio {ratio:g}:1")
        for branch in ctx.branches:
            if deg.name in branch.devices and \
                    set(branch.devices) & mirror_devices:
                confidence += 0.05
                evidence.append("mirror device sits in the delta-Vbe branch")
                break
        return {"type": "bandgap_core", "confidence": round(confidence, 3),
                "evidence": evidence}
    return None
