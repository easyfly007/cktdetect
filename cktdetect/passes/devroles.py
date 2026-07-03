"""Device role labeling (DESIGN.md P6).

A transistor's role follows from where its control terminal connects
(rail / bias / signal net) and its position in the branch stack. Roles
are unique per device, so there is no motif-overlap conflict to resolve.
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.circuit import Circuit
from .families import (control_net, drain_net, is_diode_connected,
                       is_transistor, polarity, source_net)
from .rails import NetRole


def assign_device_roles(circuit: Circuit, infos: dict) -> dict:
    """Return {device_name: {"role": str, "evidence": [str]}}."""

    def role_of(net):
        return infos[net].role

    transistors = [d for d in circuit.devices if is_transistor(d)]

    drain_map = defaultdict(list)
    for dev in transistors:
        drain_map[drain_net(dev)].append(dev)

    # signal-gated transistors grouped by their source net (fork candidates)
    source_groups = defaultdict(list)
    for dev in transistors:
        if is_diode_connected(dev):
            continue
        if role_of(control_net(dev)) is NetRole.SIGNAL:
            source_groups[source_net(dev)].append(dev)

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
            if pol == "n" and role_of(source) is NetRole.GROUND:
                role = "current_sink"
                evidence = [f"bias-gated ('{gate}'), source on ground"]
            elif pol == "p" and role_of(source) is NetRole.POWER:
                role = "current_source"
                evidence = [f"bias-gated ('{gate}'), source on power"]
            elif role_of(source) is NetRole.SIGNAL and any(
                    o is not dev and polarity(o) == pol
                    for o in drain_map[source]):
                below = [o.name for o in drain_map[source] if o is not dev]
                role = "cascode"
                evidence = [f"bias-gated ('{gate}'), stacked on "
                            f"{','.join(below)}"]
            else:
                role = "bias_gated"
                evidence = [f"gate on bias net '{gate}'"]
        elif role_of(gate) in (NetRole.POWER, NetRole.GROUND):
            role = "rail_tied"
            evidence = [f"gate tied to rail '{gate}'"]
        else:  # signal-gated
            peers = [o for o in source_groups[source]
                     if o is not dev and polarity(o) == pol
                     and control_net(o) != gate]
            if role_of(source) is NetRole.SIGNAL and peers:
                role = "diff_input"
                evidence = [f"shares source '{source}' with "
                            f"{','.join(o.name for o in peers)}"]
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
