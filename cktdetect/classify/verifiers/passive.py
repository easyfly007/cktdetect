"""Passive-network verifiers: filters and dividers (DESIGN.md M3)."""

from __future__ import annotations

from ...passive.ladder import analyze_passive_network


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
