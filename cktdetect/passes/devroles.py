"""Device role labeling (DESIGN.md P6).

A transistor's role follows from where its control terminal connects
(rail / bias / signal net) and its position in the branch stack. Roles
are unique per device, so there is no motif-overlap conflict to resolve.

All group lookups are pre-indexed so the pass stays linear on large
flattened designs (validated on a 20k-device DC-DC converter).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..ir.circuit import Circuit
from .families import (control_net, drain_net, is_diode_connected,
                       is_transistor, polarity, source_net)
from .rails import NetRole


def assign_device_roles(circuit: Circuit, infos: dict) -> dict:
    """Return {device_name: {"role": str, "evidence": [str]}}."""

    def role_of(net):
        return infos[net].role

    transistors = [d for d in circuit.devices if is_transistor(d)]

    # devices draining into a net, by polarity (for cascode detection)
    drain_pol_count = Counter()
    drain_first = {}
    for dev in transistors:
        key = (drain_net(dev), polarity(dev))
        drain_pol_count[key] += 1
        drain_first.setdefault(key, dev.name)

    # signal-gated, non-diode transistors grouped by source net
    # (fork candidates); counted per gate so peer checks are O(1)
    group_count = Counter()
    group_gate_count = Counter()
    group_samples = defaultdict(list)
    for dev in transistors:
        if is_diode_connected(dev):
            continue
        gate = control_net(dev)
        if role_of(gate) is not NetRole.SIGNAL:
            continue
        key = (source_net(dev), polarity(dev))
        group_count[key] += 1
        group_gate_count[(key, gate)] += 1
        if len(group_samples[key]) < 4:
            group_samples[key].append(dev.name)

    roles = {}
    for dev in transistors:
        gate, drain, source = (control_net(dev), drain_net(dev),
                               source_net(dev))
        pol = polarity(dev)
        role, evidence = "unknown", []

        if gate == drain:
            role = "diode"
            evidence = ["control terminal tied to drain"]
        elif role_of(gate) is NetRole.BIAS:
            stacked_below = (drain_pol_count[(source, pol)]
                             - (1 if drain == source else 0))
            if pol == "n" and role_of(source) is NetRole.GROUND:
                role = "current_sink"
                evidence = [f"bias-gated ('{gate}'), source on ground"]
            elif pol == "p" and role_of(source) is NetRole.POWER:
                role = "current_source"
                evidence = [f"bias-gated ('{gate}'), source on power"]
            elif role_of(source) is NetRole.SIGNAL and stacked_below > 0:
                below = drain_first.get((source, pol), "?")
                role = "cascode"
                evidence = [f"bias-gated ('{gate}'), stacked on {below}"]
            else:
                role = "bias_gated"
                evidence = [f"gate on bias net '{gate}'"]
        elif role_of(gate) in (NetRole.POWER, NetRole.GROUND):
            role = "rail_tied"
            evidence = [f"gate tied to rail '{gate}'"]
        else:  # signal-gated
            key = (source, pol)
            peers = (group_count[key] - group_gate_count[(key, gate)]
                     if not is_diode_connected(dev) else 0)
            if role_of(source) is NetRole.SIGNAL and peers > 0:
                sample = [n for n in group_samples[key]
                          if n != dev.name][:2]
                role = "diff_input"
                evidence = [f"shares source '{source}' with "
                            f"{','.join(sample)}"
                            + (f" (+{peers - len(sample)} more)"
                               if peers > len(sample) else "")]
            elif role_of(source) in (NetRole.POWER, NetRole.GROUND):
                role = "common_source"
                evidence = [f"signal gate '{gate}', source on rail"]
            elif (pol == "n" and role_of(drain) is NetRole.POWER) or \
                    (pol == "p" and role_of(drain) is NetRole.GROUND):
                role = "source_follower"
                evidence = [f"signal gate '{gate}', drain on rail, "
                            f"output at source '{source}'"]
            else:
                role = "amplifier"
                evidence = [f"signal gate '{gate}'"]
        roles[dev.name] = {"role": role, "evidence": evidence}
    return roles
