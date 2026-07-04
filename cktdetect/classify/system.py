"""System-level (composition) classification: circuits of circuits.

Hierarchical designs are classified bottom-up per subckt; this module
runs one level higher, on the block-instance graph -- subckt instances
labeled with their own classification, connected by the scope's nets.
A PLL is an oscillator, a phase/charge-pump block, and a loop filter
closed into a ring; a flash ADC is a resistor ladder whose taps feed an
array of comparator instances sharing an input.
"""

from __future__ import annotations

from collections import Counter

from ..ir.device import DeviceType

_OSC_TYPES = {"lc_vco", "ring_oscillator"}
_COMPARATOR_TYPES = {"comparator", "strongarm_comparator"}
_PASSIVE_PREFIXES = ("passive_filter", "resistive_")


def _blocks(circuit, subckt_analysis) -> list:
    blocks = []
    for dev in circuit.devices:
        if dev.dtype is not DeviceType.SUBCKT:
            continue
        verdicts = subckt_analysis.get(dev.subckt) or []
        blocks.append({
            "instance": dev.name,
            "subckt": dev.subckt,
            "type": verdicts[0]["type"] if verdicts else "unknown",
            "nets": set(dev.terminals.values()),
        })
    return blocks


def classify_system(circuit, subckt_analysis, rails) -> list:
    """Return system-level verdicts for a scope with subckt instances."""
    blocks = _blocks(circuit, subckt_analysis)
    if len(blocks) < 2:
        return []
    verdicts = []
    for verifier in (verify_pll, verify_flash_adc):
        verdict = verifier(circuit, blocks, rails)
        if verdict is not None:
            verdicts.append(verdict)
    verdicts.sort(key=lambda v: -v["confidence"])
    return verdicts


def _distinct_triple(set_a, set_b, set_c):
    for a in sorted(set_a):
        for b in sorted(set_b):
            if b == a:
                continue
            for c in sorted(set_c):
                if c not in (a, b):
                    return a, b, c
    return None


def verify_pll(circuit, blocks, rails):
    """Oscillator + control block + loop filter closed into a ring."""
    oscillators = [b for b in blocks if b["type"] in _OSC_TYPES]
    filters = [b for b in blocks
               if b["type"].startswith("passive_filter")]
    controls = [b for b in blocks
                if b["type"] not in _OSC_TYPES
                and not b["type"].startswith(_PASSIVE_PREFIXES)]
    for osc in oscillators:
        for flt in filters:
            for ctl in controls:
                osc_ctl = (ctl["nets"] & osc["nets"]) - rails
                ctl_flt = (ctl["nets"] & flt["nets"]) - rails
                flt_osc = (flt["nets"] & osc["nets"]) - rails
                triple = _distinct_triple(flt_osc, osc_ctl, ctl_flt)
                if triple is None:
                    continue
                tune, feedback, pump = triple
                evidence = [
                    f"oscillator {osc['instance']} ({osc['type']})",
                    f"phase/charge-pump block {ctl['instance']} "
                    f"({ctl['type']}) compares against the oscillator "
                    f"via '{feedback}'",
                    f"loop filter {flt['instance']} ({flt['type']}) "
                    f"integrates '{pump}' into the tuning net '{tune}'",
                    f"blocks close a control loop: "
                    f"{osc['instance']} -> {ctl['instance']} -> "
                    f"{flt['instance']} -> {osc['instance']}",
                ]
                confidence = 0.8
                reference = sorted(ctl["nets"] - osc["nets"]
                                   - flt["nets"] - rails)
                if reference:
                    confidence += 0.05
                    evidence.append(f"external reference input "
                                    f"'{reference[0]}'")
                return {"type": "pll", "confidence": round(confidence, 3),
                        "evidence": evidence}
    return None


def verify_flash_adc(circuit, blocks, rails):
    """Resistor-ladder taps feeding an array of comparator instances."""
    comparators = [b for b in blocks if b["type"] in _COMPARATOR_TYPES]
    if len(comparators) < 3:
        return None
    resistors = [d for d in circuit.devices
                 if d.dtype is DeviceType.RESISTOR]
    if len(resistors) < 3:
        return None

    r_connections = Counter()
    for res in resistors:
        for net in res.nets:
            r_connections[net] += 1
    taps = [n for n, count in r_connections.items()
            if count == 2 and n not in rails]

    tapped = {}
    for tap in taps:
        for block in comparators:
            if tap in block["nets"]:
                tapped[tap] = block["instance"]
                break
    if len(set(tapped.values())) < 3:
        return None

    shared = set.intersection(*[b["nets"] for b in comparators])
    shared -= rails | set(taps)
    if not shared:
        return None

    evidence = [
        f"{len(comparators)} comparator instances "
        f"({','.join(b['instance'] for b in comparators)})",
        f"resistor ladder taps {','.join(sorted(tapped))} feed "
        f"{len(set(tapped.values()))} distinct comparators",
        f"comparators share input net(s) {','.join(sorted(shared))}",
    ]
    confidence = 0.85
    if len(set(tapped.values())) >= len(comparators):
        confidence += 0.05
        evidence.append("every comparator has its own ladder tap")
    return {"type": "flash_adc", "confidence": round(confidence, 3),
            "evidence": evidence}
