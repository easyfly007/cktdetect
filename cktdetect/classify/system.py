"""System-level (composition) classification: circuits of circuits.

Hierarchical designs are classified bottom-up per subckt; this module
runs one level higher, on the block-instance graph -- subckt instances
labeled with their own classification, connected by the scope's nets.
A PLL is an oscillator, a phase/charge-pump block, and a loop filter
closed into a ring; a flash ADC is a resistor ladder whose taps feed an
array of comparator instances sharing an input.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..ir.device import DeviceType

_OSC_TYPES = {"lc_vco", "ring_oscillator"}
_COMPARATOR_TYPES = {"comparator", "strongarm_comparator"}
_PASSIVE_PREFIXES = ("passive_filter", "resistive_")
_INVERTING_STAGE_TYPES = {"class_ab_output_stage",
                          "common_source_amplifier"}


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
    for verifier in (verify_pll, verify_flash_adc,
                     verify_vco_stage_chain):
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


def verify_vco_stage_chain(circuit, blocks, rails):
    """Open chain of identical voltage-controlled inverting stages.

    A closed chain is a ring oscillator (caught at flat level); an OPEN
    chain whose ends leave through ports is a VCO delay chain closed
    externally. The all-instances-shared control net (frequency tuning)
    is what distinguishes it from a plain buffer/clock chain.
    """
    by_subckt = defaultdict(list)
    for block in blocks:
        by_subckt[block["subckt"]].append(block)
    ports = set(circuit.ports)

    for subckt, stages in sorted(by_subckt.items()):
        if len(stages) < 3:
            continue
        if stages[0]["type"] not in _INVERTING_STAGE_TYPES:
            continue
        control = set.intersection(*[b["nets"] for b in stages]) - rails
        if not control:
            continue  # no shared tuning input: a buffer chain, not a VCO

        net_count = Counter()
        for block in stages:
            for net in block["nets"] - rails - control:
                net_count[net] += 1
        links = {n for n, count in net_count.items() if count == 2}
        free = {n for n, count in net_count.items() if count == 1}

        adjacency = defaultdict(set)
        for net in links:
            members = [b["instance"] for b in stages if net in b["nets"]]
            adjacency[members[0]].add(members[1])
            adjacency[members[1]].add(members[0])
        degrees = {b["instance"]: len(adjacency[b["instance"]])
                   for b in stages}
        ends = [i for i, deg in degrees.items() if deg == 1]
        if len(ends) != 2 or any(deg != 2 for i, deg in degrees.items()
                                 if i not in ends):
            continue  # not a simple open path (cycles are rings)
        seen, frontier = {ends[0]}, ends[0]
        while True:
            step = [i for i in adjacency[frontier] if i not in seen]
            if not step:
                break
            frontier = step[0]
            seen.add(frontier)
        if len(seen) != len(stages):
            continue
        if len(free) < 2 or (ports and len(free & ports) < 2):
            continue  # ends must be open (externally closable)

        tune = sorted(control)[0]
        evidence = [
            f"{len(stages)} identical inverting stages "
            f"({subckt}, classified {stages[0]['type']}) chained "
            f"input-to-output",
            f"shared frequency-control net '{tune}' on every stage",
            f"chain ends {','.join(sorted(free)[:2])} leave the scope: "
            f"the loop closes externally",
        ]
        return {"type": "vco_stage_chain", "confidence": 0.8,
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
