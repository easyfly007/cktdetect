"""Oscillator verifiers beyond the LC VCO: the ring oscillator (M6+)."""

from __future__ import annotations


def verify_ring_oscillator(ctx):
    """Odd number of inverting stages closed into a loop."""
    for ring in ctx.inverter_rings:
        if ring["length"] < 3 or ring["length"] % 2 == 0:
            continue
        stages = [",".join(devs) for devs in ring["inverters"]]
        evidence = [
            f"{ring['length']} inverting stages closed into a loop "
            f"({' -> '.join(ring['nets'])} -> {ring['nets'][0]})",
            f"stage devices: {'; '.join(stages)}",
            "odd stage count: no stable operating point (oscillates)",
        ]
        confidence = 0.85
        if len(ctx.pairs) == 0 and not ctx.mirrors:
            confidence += 0.05  # nothing but the ring: clean oscillator
        return {"type": "ring_oscillator",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None
