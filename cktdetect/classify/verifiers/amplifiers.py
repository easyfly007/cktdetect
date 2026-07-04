"""Amplifier-family verifiers (DESIGN.md section 4, M2 set).

Each verifier checks the Required structure for one circuit type on the
analyzed context, accumulates Optional evidence, and returns a verdict
dict -- or None when a Required condition (or a Forbidden one) fails.
"""

from __future__ import annotations

from ...ir.device import DeviceType
from ...passes.families import (control_net, drain_net, polarity,
                                source_net)
from ...passive.ladder import r_divider_taps


def _mirror_load(ctx, pair):
    """Opposite-polarity mirror whose drains sit on the pair outputs."""
    pair_outs = set(pair["outputs"])
    for mirror in ctx.mirrors:
        if mirror["polarity"] == pair["polarity"]:
            continue
        ref = ctx.circuit.device(mirror["reference"])
        nets = {drain_net(ref)} | {o["drain_net"] for o in mirror["outputs"]}
        if nets & pair_outs:
            return mirror, nets <= pair_outs
    return None, False


def _second_stages(ctx, pair):
    """Signal-gated gain devices driven by the pair outputs."""
    outs = set(pair["outputs"])
    return [d for d in ctx.transistors
            if ctx.role(d.name) in ("common_source", "amplifier")
            and control_net(d) in outs]


def _miller_caps(ctx, cs_dev):
    gate, drain = control_net(cs_dev), drain_net(cs_dev)
    return [c for c in ctx.circuit.devices
            if c.dtype is DeviceType.CAPACITOR
            and {c.terminals.get("p"), c.terminals.get("n")} == {gate, drain}]


def verify_single_stage_ota(ctx):
    for pair in ctx.pairs:
        mirror, full = _mirror_load(ctx, pair)
        if mirror is None:
            continue
        if _second_stages(ctx, pair):
            continue  # forbidden: that is a two-stage topology
        evidence = [
            f"differential pair {','.join(pair['devices'])} "
            f"(tail net '{pair['tail_net']}')",
            f"current-mirror load (reference {mirror['reference']})",
        ]
        confidence = 0.7
        if pair["tail_source"]:
            confidence += 0.1
            evidence.append(f"tail current source {pair['tail_source']}")
        if full:
            confidence += 0.1
            evidence.append("mirror covers both pair outputs")
        return {"type": "single_stage_ota",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_two_stage_ota(ctx):
    for pair in ctx.pairs:
        mirror, full = _mirror_load(ctx, pair)
        if mirror is None:
            continue
        stages = _second_stages(ctx, pair)
        if not stages:
            continue
        cs = stages[0]
        # forbidden: resistive feedback from the output to the pair input
        # is a regulator/closed-loop topology (see verify_ldo), not an OTA
        taps = r_divider_taps(ctx.circuit, ctx.infos, drain_net(cs))
        if taps & set(pair["inputs"]):
            continue
        evidence = [
            f"input stage: pair {','.join(pair['devices'])} with "
            f"mirror load ({mirror['reference']})",
            f"second gain stage {cs.name} driven by '{control_net(cs)}'",
        ]
        confidence = 0.75
        if pair["tail_source"]:
            confidence += 0.05
            evidence.append(f"tail current source {pair['tail_source']}")
        millers = _miller_caps(ctx, cs)
        if millers:
            confidence += 0.1
            evidence.append(f"Miller compensation {millers[0].name} "
                            f"bridges the second stage")
        if full:
            confidence += 0.05
            evidence.append("mirror covers both pair outputs")
        return {"type": "two_stage_ota",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_folded_cascode_ota(ctx):
    for pair in ctx.pairs:
        outs = set(pair["outputs"])
        cascodes = [d for d in ctx.transistors
                    if ctx.role(d.name) == "cascode"
                    and source_net(d) in outs
                    and polarity(d) != pair["polarity"]]
        if len(cascodes) < 2:
            continue
        folders = [d for d in ctx.transistors
                   if ctx.role(d.name) in ("current_source", "current_sink",
                                           "mirror_output")
                   and drain_net(d) in outs]
        evidence = [
            f"differential pair {','.join(pair['devices'])}",
            f"opposite-polarity cascodes "
            f"{','.join(d.name for d in cascodes)} take over the pair "
            f"outputs (folding nodes {','.join(sorted(outs))})",
        ]
        confidence = 0.75
        if pair["tail_source"]:
            confidence += 0.05
            evidence.append(f"tail current source {pair['tail_source']}")
        if len(folders) >= 2:
            confidence += 0.1
            evidence.append(f"folding current sources "
                            f"{','.join(d.name for d in folders)}")
        return {"type": "folded_cascode_ota",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_telescopic_ota(ctx):
    """Same-polarity cascodes stacked directly on the pair outputs."""
    for pair in ctx.pairs:
        outs = set(pair["outputs"])
        cascodes = [d for d in ctx.transistors
                    if ctx.role(d.name) == "cascode"
                    and source_net(d) in outs
                    and polarity(d) == pair["polarity"]]
        if len(cascodes) < 2:
            continue
        evidence = [
            f"differential pair {','.join(pair['devices'])}",
            f"same-polarity cascodes {','.join(d.name for d in cascodes)} "
            f"stacked on the pair outputs {','.join(sorted(outs))}",
        ]
        confidence = 0.75
        if pair["tail_source"]:
            confidence += 0.05
            evidence.append(f"tail current source {pair['tail_source']}")
        casc_outs = {drain_net(d) for d in cascodes}
        for mirror in ctx.mirrors:
            if mirror["polarity"] == pair["polarity"]:
                continue
            ref = ctx.circuit.device(mirror["reference"])
            nets = {drain_net(ref)} | {o["drain_net"]
                                       for o in mirror["outputs"]}
            if nets & casc_outs:
                confidence += 0.1
                evidence.append(f"mirror load ({mirror['reference']}) on "
                                f"the cascode outputs")
                break
        return {"type": "telescopic_ota",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_fully_differential_ota(ctx):
    """Pair with matched current-source loads on both outputs, no mirror
    (a mirror load makes it single-ended), optionally with resistive
    common-mode feedback."""
    if ctx.cross_coupled:
        return None  # latch loads belong to comparators/oscillators
    for pair in ctx.pairs:
        outs = set(pair["outputs"])
        mirror_hit = False
        for mirror in ctx.mirrors:
            ref = ctx.circuit.device(mirror["reference"])
            nets = {drain_net(ref)} | {o["drain_net"]
                                       for o in mirror["outputs"]}
            if nets & outs:
                mirror_hit = True
                break
        if mirror_hit:
            continue
        if any(ctx.role(d.name) == "cascode" and source_net(d) in outs
               for d in ctx.transistors):
            continue  # telescopic/folded territory
        loads = {}
        for net in outs:
            for dev in ctx.transistors:
                if drain_net(dev) == net and polarity(dev) != \
                        pair["polarity"] and ctx.role(dev.name) in \
                        ("current_source", "current_sink", "mirror_output"):
                    loads[net] = dev
                    break
        if len(loads) != len(outs) or len(outs) != 2:
            continue
        load_a, load_b = sorted(loads.values(), key=lambda d: d.name)
        evidence = [
            f"differential pair {','.join(pair['devices'])} with both "
            f"outputs {','.join(sorted(outs))} kept differential",
            f"current-source loads {load_a.name},{load_b.name} "
            f"(no mirror: outputs are not single-ended)",
        ]
        confidence = 0.75
        if pair["tail_source"]:
            confidence += 0.05
            evidence.append(f"tail current source {pair['tail_source']}")
        if all(load_a.params.get(k) == load_b.params.get(k)
               and isinstance(load_a.params.get(k), (int, float))
               for k in ("w", "l")):
            confidence += 0.05
            evidence.append("matched load geometry")
        # resistive common-mode feedback: both outputs sensed by resistors
        # into one net that gates a transistor
        resistors = [d for d in ctx.circuit.devices
                     if d.dtype is DeviceType.RESISTOR]
        out_a, out_b = sorted(outs)
        for cm_net in sorted(ctx.circuit.nets()):
            if cm_net in outs:
                continue
            if not (any(set(r.nets) == {out_a, cm_net} for r in resistors)
                    and any(set(r.nets) == {out_b, cm_net}
                            for r in resistors)):
                continue
            sensor = next((d for d in ctx.transistors
                           if control_net(d) == cm_net), None)
            if sensor:
                confidence += 0.1
                evidence.append(
                    f"common-mode feedback: sense resistors average the "
                    f"outputs into '{cm_net}' gating {sensor.name}")
                break
        return {"type": "fully_differential_ota",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_strongarm_comparator(ctx):
    """Clocked tail + precharge devices + pair + regenerative latch."""
    if ctx.has_type(DeviceType.INDUCTOR):
        return None
    from collections import defaultdict

    from ...passes.rails import NetRole

    by_gate = defaultdict(list)
    for dev in ctx.transistors:
        by_gate[control_net(dev)].append(dev)

    for net, gated in sorted(by_gate.items()):
        tails = [d for d in gated if polarity(d) == "n"
                 and ctx.infos[source_net(d)].role is NetRole.GROUND]
        precharge = [d for d in gated if polarity(d) == "p"
                     and ctx.infos[source_net(d)].role is NetRole.POWER]
        if not tails or len(precharge) < 2:
            continue
        for tail_dev in tails:
            for pair in ctx.pairs:
                if pair["tail_net"] != drain_net(tail_dev):
                    continue
                outs = set(pair["outputs"])
                latch = None
                for xc in ctx.cross_coupled:
                    touched = set(xc["nets"]) | {
                        source_net(ctx.circuit.device(n))
                        for n in xc["devices"]}
                    if touched & outs:
                        latch = xc
                        break
                if latch is None:
                    continue
                evidence = [
                    f"clocked tail {tail_dev.name} and precharge devices "
                    f"{','.join(d.name for d in precharge)} share gate "
                    f"net '{net}' (clock)",
                    f"input pair {','.join(pair['devices'])}",
                    f"regenerative cross-coupled pair "
                    f"{','.join(latch['devices'])}",
                ]
                confidence = 0.85
                if len(ctx.cross_coupled) >= 2:
                    confidence += 0.05
                    evidence.append(
                        "complementary nmos+pmos cross-coupled pairs")
                return {"type": "strongarm_comparator",
                        "confidence": round(confidence, 3),
                        "evidence": evidence}
    return None


def verify_comparator(ctx):
    if ctx.has_type(DeviceType.INDUCTOR):
        return None  # cross-coupled + inductor is an oscillator, not a latch
    for pair in ctx.pairs:
        outs = set(pair["outputs"])
        for xc in ctx.cross_coupled:
            if not (set(xc["nets"]) & outs):
                continue
            evidence = [
                f"differential pair {','.join(pair['devices'])}",
                f"cross-coupled regenerative pair "
                f"{','.join(xc['devices'])} on the pair outputs",
            ]
            confidence = 0.75
            if pair["tail_source"]:
                confidence += 0.05
                evidence.append(f"tail current source {pair['tail_source']}")
            return {"type": "comparator",
                    "confidence": round(confidence, 3), "evidence": evidence}
    return None


def verify_buffer(ctx):
    followers = ctx.devices_by_role("source_follower")
    if not followers or ctx.pairs:
        return None
    if ctx.devices_by_role("common_source", "amplifier"):
        return None  # gain stages present: not a plain buffer
    evidence = [f"source follower {d.name} (input '{control_net(d)}', "
                f"output '{source_net(d)}')" for d in followers]
    return {"type": "buffer", "confidence": 0.7, "evidence": evidence}


def verify_current_mirror_bias(ctx):
    if not ctx.mirrors or ctx.pairs:
        return None
    if ctx.devices_by_role("common_source", "amplifier", "diff_input",
                           "source_follower"):
        return None  # gain devices present: mirrors are a sub-structure
    evidence = [
        f"current mirror on '{m['gate_net']}' "
        f"({m['reference']} -> {','.join(o['device'] for o in m['outputs'])})"
        for m in ctx.mirrors
    ]
    confidence = 0.7 + 0.05 * min(len(ctx.mirrors), 2)
    cascodes = ctx.devices_by_role("cascode")
    if cascodes:
        evidence.append(f"cascoded by {','.join(d.name for d in cascodes)}")
    return {"type": "current_mirror_bias",
            "confidence": round(confidence, 3), "evidence": evidence}
