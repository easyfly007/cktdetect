"""Structure extraction: current mirrors and differential pairs.

Both fall out of the role labeling (DESIGN.md section 2):
- a mirror is a bias net plus its diode reference and the same-polarity,
  same-source transistors gated by it;
- a differential pair is a fork: two same-polarity, signal-gated
  transistors sharing a non-rail source net with distinct gates.

Confidence is a rule-based score; every record carries its evidence.
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.circuit import Circuit
from ..ir.device import DeviceType
from .families import (control_net, drain_net, is_diode_connected,
                       is_transistor, polarity, source_net, strength)
from .rails import NetRole


def _is_rail(infos, net) -> bool:
    return infos[net].role in (NetRole.POWER, NetRole.GROUND)


def _ratio(out, ref):
    a, b = strength(out), strength(ref)
    return round(a / b, 6) if a and b else None


def _effective_drain(dev, by_source):
    """Follow single same-polarity series devices (cascodes) upward to
    the composite output node."""
    current = drain_net(dev)
    previous = dev
    for _ in range(3):
        ups = [u for u in by_source.get(current, [])
               if u is not previous and polarity(u) == polarity(dev)
               and drain_net(u) != current]
        if len(ups) != 1:
            break
        previous = ups[0]
        current = drain_net(previous)
    return current


def _composite_diodes(transistors, infos, connections) -> list:
    """(bottom, cascode) pairs whose diode connection runs through the
    cascode: gate(bottom) == drain(cascode), source(cascode) ==
    drain(bottom), and the intermediate net is exclusive to the two."""
    by_source = defaultdict(list)
    for dev in transistors:
        by_source[source_net(dev)].append(dev)

    result = []
    for bottom in transistors:
        if is_diode_connected(bottom) or polarity(bottom) is None:
            continue
        gate = control_net(bottom)
        if gate is None or _is_rail(infos, gate):
            continue
        mid = drain_net(bottom)
        if connections[mid] != 2:
            continue
        for casc in by_source.get(mid, []):
            if casc is bottom or polarity(casc) != polarity(bottom):
                continue
            if drain_net(casc) == gate:
                result.append((bottom, casc))
    return result


def find_current_mirrors(circuit: Circuit, infos: dict) -> list:
    transistors = [d for d in circuit.devices if is_transistor(d)]
    by_gate = defaultdict(list)
    by_source = defaultdict(list)
    connections = defaultdict(int)
    for dev in transistors:
        by_gate[control_net(dev)].append(dev)
        by_source[source_net(dev)].append(dev)
    for dev in circuit.devices:
        for net in dev.terminals.values():
            connections[net] += 1

    def make_record(ref, gate, outs, extra_evidence, base, cascode=None):
        evidence = [
            f"gate net '{gate}' shared by {len(outs)} output(s)",
            f"common source net '{source_net(ref)}'",
            *extra_evidence,
        ]
        confidence = base
        if all(d.model == ref.model for d in outs):
            confidence += 0.1
            evidence.append("same device model")
        ref_l = ref.params.get("l")
        if isinstance(ref_l, (int, float)) and \
                all(o.params.get("l") == ref_l for o in outs):
            confidence += 0.05
            evidence.append("matched channel length")
        record = {
            "type": "current_mirror",
            "variant": "cascode" if cascode else "simple",
            "polarity": polarity(ref),
            "gate_net": gate,
            "reference": ref.name,
            "ref_drain_net": gate,
            "outputs": [{"device": o.name,
                         "drain_net": _effective_drain(o, by_source),
                         "ratio": _ratio(o, ref)} for o in sorted(
                             outs, key=lambda d: d.name)],
            "confidence": round(confidence, 3),
            "evidence": evidence,
        }
        if cascode:
            record["cascode"] = cascode.name
        return record

    def gate_outputs(ref, gate):
        return [d for d in by_gate[gate]
                if d is not ref and not is_diode_connected(d)
                and polarity(d) == polarity(ref)
                and source_net(d) == source_net(ref)]

    mirrors = []
    claimed_gates = set()

    for ref in transistors:
        if not is_diode_connected(ref) or polarity(ref) is None:
            continue
        gate = control_net(ref)
        if _is_rail(infos, gate):
            continue
        outs = gate_outputs(ref, gate)
        if not outs:
            continue
        claimed_gates.add(gate)
        mirrors.append(make_record(
            ref, gate, outs,
            [f"diode-connected reference {ref.name}"], base=0.8))

    for bottom, casc in _composite_diodes(transistors, infos, connections):
        gate = control_net(bottom)
        if gate in claimed_gates:
            continue
        outs = gate_outputs(bottom, gate)
        if not outs:
            continue
        claimed_gates.add(gate)
        mirrors.append(make_record(
            bottom, gate, outs,
            [f"diode connection through cascode {casc.name} "
             f"(reference {bottom.name})"],
            base=0.75, cascode=casc))

    mirrors.sort(key=lambda m: m["reference"])
    return mirrors


def find_differential_pairs(circuit: Circuit, infos: dict) -> list:
    transistors = [d for d in circuit.devices if is_transistor(d)]

    groups = defaultdict(list)
    for dev in transistors:
        if is_diode_connected(dev) or polarity(dev) is None:
            continue
        if infos[control_net(dev)].role is not NetRole.SIGNAL:
            continue
        source = source_net(dev)
        if _is_rail(infos, source):
            continue
        groups[(source, polarity(dev))].append(dev)

    pairs = []
    for (tail_net, pol), devs in sorted(groups.items()):
        if len(devs) != 2:
            continue
        a, b = sorted(devs, key=lambda d: d.name)
        if control_net(a) == control_net(b):
            continue  # forbidden: gates shorted
        if drain_net(a) == drain_net(b):
            continue  # parallel devices, not a pair
        evidence = [
            f"shared source net '{tail_net}'",
            "same polarity, distinct signal gates, distinct drains",
        ]
        confidence = 0.6
        if all(isinstance(a.params.get(k), (int, float)) and
               a.params.get(k) == b.params.get(k) for k in ("w", "l")):
            confidence += 0.15
            evidence.append("matched geometry")
        tail_source = _find_tail(circuit, transistors, tail_net, (a, b))
        if tail_source:
            confidence += 0.15
            evidence.append(f"tail current source {tail_source}")
        pairs.append({
            "type": "differential_pair",
            "polarity": pol,
            "devices": [a.name, b.name],
            "inputs": [control_net(a), control_net(b)],
            "outputs": [drain_net(a), drain_net(b)],
            "tail_net": tail_net,
            "tail_source": tail_source,
            "confidence": round(confidence, 3),
            "evidence": evidence,
        })
    return pairs


def _find_tail(circuit, transistors, tail_net, pair):
    for dev in transistors:
        if dev not in pair and drain_net(dev) == tail_net:
            return dev.name
    for dev in circuit.devices:
        if dev.dtype is DeviceType.ISOURCE and tail_net in dev.nets:
            return dev.name
    return None


def apply_structure_roles(roles: dict, mirrors: list, pairs: list):
    """Refine device roles with structure membership (in place)."""
    for mirror in mirrors:
        ref = mirror["reference"]
        if ref in roles:
            roles[ref]["role"] = "mirror_reference"
            roles[ref]["evidence"].append(
                f"reference of current mirror on '{mirror['gate_net']}'")
        for out in mirror["outputs"]:
            name = out["device"]
            if name in roles:
                roles[name]["role"] = "mirror_output"
                roles[name]["evidence"].append(
                    f"output of current mirror on '{mirror['gate_net']}'")
        casc = mirror.get("cascode")
        if casc and casc in roles:
            roles[casc]["evidence"].append(
                f"closes the diode connection of the mirror on "
                f"'{mirror['gate_net']}'")
    for pair in pairs:
        tail = pair["tail_source"]
        if tail and tail in roles:
            roles[tail]["role"] = "tail_current_source"
            roles[tail]["evidence"].append(
                f"feeds tail net '{pair['tail_net']}' of pair "
                f"{','.join(pair['devices'])}")
