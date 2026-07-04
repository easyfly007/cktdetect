"""Passive-network verifiers: filters and dividers (DESIGN.md M3)."""

from __future__ import annotations

from ...passive.arrays import find_r2r_ladder
from ...passive.ladder import analyze_passive_network


def verify_r2r_ladder(ctx):
    ladder = find_r2r_ladder(ctx.circuit, ctx.infos)
    if ladder is None:
        return None
    evidence = [
        f"{ladder['bits']}-node backbone of series R "
        f"({','.join(ladder['series'])}, R={ladder['unit_value']:g})",
        f"2R branch on every backbone node "
        f"({','.join(ladder['branches'])})",
    ]
    confidence = 0.85
    if ladder["terminator"]:
        confidence += 0.05
        evidence.append(f"2R ground terminator {ladder['terminator']}")
    return {"type": "r2r_ladder", "confidence": round(confidence, 3),
            "evidence": evidence}


def verify_passive_network(ctx):
    result = analyze_passive_network(ctx.circuit, ctx.infos)
    if result is None:
        return None
    if result["order"] == 0:
        if not result["series"] or not result["shunts"]:
            return None
        evidence = [
            f"resistor chain {'-'.join(result['series'])} from "
            f"'{result['input_net']}' with shunt "
            f"{','.join(result['shunts'])} to ground",
            f"tap net(s): {','.join(result['chain'][1:])}",
        ]
        return {"type": "resistive_divider", "confidence": 0.75,
                "evidence": evidence}
    if result["kind"] is None:
        return None
    evidence = [
        f"passive ladder from '{result['input_net']}' to "
        f"'{result['output_net']}'",
        f"series: {','.join(result['series']) or '-'}; "
        f"shunts: {','.join(result['shunts']) or '-'}",
        f"order {result['order']} ({result['kind']})",
    ]
    return {"type": f"passive_filter_{result['kind']}",
            "confidence": 0.8, "evidence": evidence}
