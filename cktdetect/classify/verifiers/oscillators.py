"""Oscillator verifiers beyond the LC VCO: the ring oscillator (M6+).

Detection works on net-level inverting loops (gate->drain hops), which
covers plain CMOS inverter rings as well as current-starved and
single-ended stages (validated against the ALIGN benchmark suite).
"""

from __future__ import annotations


def verify_ring_oscillator(ctx):
    """Odd number of inverting stages closed into a loop."""
    for loop in ctx.inverting_loops:
        stages = len(loop["nets"])
        if stages < 3 or stages % 2 == 0:
            continue
        evidence = [
            f"{stages} inverting stages closed into a loop "
            f"({' -> '.join(loop['nets'])} -> {loop['nets'][0]})",
            f"stage devices: {','.join(loop['devices'])}",
            "odd stage count: no stable operating point (oscillates)",
        ]
        if ctx.inverters:
            evidence.append("complementary CMOS inverter stages")
        else:
            evidence.append("single-ended / current-starved stages")
        confidence = 0.85
        if not ctx.pairs and not ctx.mirrors:
            confidence += 0.05  # nothing but the ring: clean oscillator
        return {"type": "ring_oscillator",
                "confidence": round(confidence, 3), "evidence": evidence}
    return None
