"""Hypothesis-driven classification engine (DESIGN.md P9).

Every registered verifier checks one circuit type. Verdicts above the
acceptance threshold are returned ranked by confidence; when nothing
matches, the result is a single UNKNOWN verdict -- never a guess.
"""

from __future__ import annotations

from .context import Context
from .verifiers import amplifiers, passive, power

THRESHOLD = 0.6

VERIFIERS = [
    power.verify_ldo,
    power.verify_bandgap,
    amplifiers.verify_two_stage_ota,
    amplifiers.verify_folded_cascode_ota,
    amplifiers.verify_single_stage_ota,
    amplifiers.verify_comparator,
    amplifiers.verify_buffer,
    amplifiers.verify_current_mirror_bias,
    passive.verify_passive_network,
]


def classify(ctx: Context) -> list:
    verdicts = []
    for verifier in VERIFIERS:
        verdict = verifier(ctx)
        if verdict is not None:
            verdicts.append(verdict)
    verdicts.sort(key=lambda v: -v["confidence"])
    accepted = [v for v in verdicts if v["confidence"] >= THRESHOLD]
    if not accepted:
        return [{"type": "unknown", "confidence": 0.0,
                 "evidence": [], "note": "no circuit-type verifier matched"}]
    return accepted
