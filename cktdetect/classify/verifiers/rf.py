"""RF verifiers: LC VCO, LNA, Gilbert mixer (DESIGN.md M4)."""

from __future__ import annotations

from ...ir.device import DeviceType
from ...passes.families import control_net, drain_net, source_net
from ...passes.rails import NetRole


def verify_lc_vco(ctx):
    """Cross-coupled pair (positive-feedback 2-cycle) resonated by a tank."""
    for xc in ctx.cross_coupled:
        nets = set(xc["nets"])
        for tank in ctx.tanks:
            if tank["style"] == "inductor_only":
                # no explicit C: only a perfect match with the
                # cross-coupled nets is conclusive (switched-cap or
                # varactor bank provides the capacitance elsewhere)
                if set(tank["nets"]) != nets:
                    continue
            elif not (set(tank["nets"]) & nets):
                continue
            cap_note = (",".join(tank["capacitors"])
                        if tank["capacitors"] else "external/switched bank")
            evidence = [
                f"cross-coupled pair {','.join(xc['devices'])} "
                f"(negative-gm cell)",
                f"{tank['style']} LC tank "
                f"(L: {','.join(tank['inductors'])}, "
                f"C: {cap_note}) on the oscillation "
                f"nets {','.join(tank['nets'])}",
            ]
            confidence = 0.85 if tank["capacitors"] else 0.8
            devices = [ctx.circuit.device(n) for n in xc["devices"]]
            tails = {source_net(d) for d in devices}
            if len(tails) == 1:
                tail_net = next(iter(tails))
                tail = next((d.name for d in ctx.transistors
                             if drain_net(d) == tail_net), None)
                if tail:
                    confidence += 0.05
                    evidence.append(f"tail current source {tail}")
            return {"type": "lc_vco", "confidence": round(confidence, 3),
                    "evidence": evidence}
    return None


def verify_lna(ctx):
    """Amplifying device with inductive source degeneration."""
    grounds = {n for n, i in ctx.infos.items() if i.role is NetRole.GROUND}
    inductors = [d for d in ctx.circuit.devices
                 if d.dtype is DeviceType.INDUCTOR]

    def other(dev, net):
        nets = dev.nets
        return nets[1] if nets[0] == net else nets[0]

    for dev in ctx.transistors:
        if ctx.role(dev.name) not in ("amplifier", "common_source"):
            continue
        src = source_net(dev)
        degs = [l for l in inductors
                if src in l.nets and other(l, src) in grounds]
        if not degs:
            continue
        evidence = [
            f"input device {dev.name} with inductive source degeneration "
            f"{degs[0].name}",
        ]
        confidence = 0.75
        gate_ls = [l for l in inductors if control_net(dev) in l.nets]
        if gate_ls:
            confidence += 0.1
            evidence.append(f"series gate inductor {gate_ls[0].name} "
                            f"(input matching)")
        cascodes = [d for d in ctx.transistors
                    if ctx.role(d.name) == "cascode"
                    and source_net(d) == drain_net(dev)]
        out_net = drain_net(cascodes[0]) if cascodes else drain_net(dev)
        if cascodes:
            confidence += 0.05
            evidence.append(f"cascode device {cascodes[0].name}")
        loads = [l for l in inductors if out_net in l.nets] + \
            [t for t in ctx.tanks if out_net in t["nets"]]
        if loads:
            confidence += 0.05
            evidence.append(f"inductive/tank load on '{out_net}'")
        return {"type": "lna", "confidence": round(confidence, 3),
                "evidence": evidence}
    return None


def verify_gilbert_mixer(ctx):
    """Transconductance pair whose outputs carry two switching pairs
    with cross-connected drains (three-level Gilbert stack)."""
    for gm in ctx.pairs:
        outs = set(gm["outputs"])
        switches = [p for p in ctx.pairs
                    if p is not gm and p["tail_net"] in outs
                    and p["polarity"] == gm["polarity"]]
        if len(switches) < 2:
            continue
        for i in range(len(switches)):
            for j in range(i + 1, len(switches)):
                b, c = switches[i], switches[j]
                if b["tail_net"] == c["tail_net"]:
                    continue
                out_b, out_c = set(b["outputs"]), set(c["outputs"])
                if out_b != out_c or len(out_b) != 2:
                    continue  # drains must be cross-connected
                quad = sorted(b["devices"] + c["devices"])
                evidence = [
                    f"transconductance pair {','.join(gm['devices'])} "
                    f"(tail '{gm['tail_net']}')",
                    f"switching quad {','.join(quad)} stacked on the "
                    f"pair outputs {','.join(sorted(outs))}",
                    f"quad drains cross-connected to "
                    f"{','.join(sorted(out_b))}",
                ]
                confidence = 0.85
                if gm["tail_source"]:
                    confidence += 0.05
                    evidence.append(
                        f"tail current source {gm['tail_source']}")
                return {"type": "gilbert_mixer",
                        "confidence": round(confidence, 3),
                        "evidence": evidence}
    return None
