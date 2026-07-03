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
