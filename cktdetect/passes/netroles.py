"""Net role labeling: rail / bias / signal (DESIGN.md P4).

Builds on rail classification and promotes SIGNAL nets to BIAS when:

A. the net is driven by a diode-connected transistor (this is also how
   current-mirror families surface: the diode is the reference, every
   same-polarity transistor gated by the net is a candidate output); or
B. the net fans out only to control terminals, is driven only by DC
   sources, and every gated device looks bias-gated: its source is on a
   rail (current source/sink), or it is a mid-stack series device
   (cascode). Devices whose drain is on a rail (follower inputs) or that
   share their source with another signal-gated transistor (diff-pair
   members) mark the net as a signal input instead.
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.circuit import Circuit
from ..ir.device import DeviceType
from .families import (control_net, control_term, drain_net,
                       is_diode_connected, is_transistor, source_net)
from .rails import NetRole, classify_nets

_AC_SPEC_KEYWORDS = ("ac", "sin", "pulse", "pwl", "exp")


def _is_dc_driver(dev) -> bool:
    if dev.dtype not in (DeviceType.VSOURCE, DeviceType.ISOURCE):
        return False
    if not isinstance(dev.params.get("dc"), (int, float)):
        return False
    spec = str(dev.params.get("spec", ""))
    return not any(key in spec for key in _AC_SPEC_KEYWORDS)


def classify_net_roles(circuit: Circuit, profile=None) -> dict:
    """Return {net: NetInfo} with POWER/GROUND/BIAS/SIGNAL roles."""
    infos = classify_nets(circuit, profile)

    def is_rail(net) -> bool:
        return infos[net].role in (NetRole.POWER, NetRole.GROUND)

    # rule A: diode-connected transistors define bias nets
    for dev in circuit.devices:
        if not is_diode_connected(dev):
            continue
        net = control_net(dev)
        if is_rail(net):
            continue
        if infos[net].role is NetRole.SIGNAL:
            infos[net].role = NetRole.BIAS
        infos[net].evidence.append(f"driven by diode-connected {dev.name}")

    # rule B: dc source driving a gate-only net of rail-sourced devices
    connections = defaultdict(list)
    for dev in circuit.devices:
        for term, net in dev.terminals.items():
            connections[net].append((dev, term))

    for net, items in connections.items():
        if infos[net].role is not NetRole.SIGNAL:
            continue
        gated, drivers, blocked = [], [], False
        for dev, term in items:
            if is_transistor(dev) and term == control_term(dev):
                gated.append(dev)
            elif _is_dc_driver(dev):
                drivers.append(dev)
            else:
                blocked = True
                break
        if blocked or not gated or not drivers:
            continue

        def has_diff_peer(dev):
            src = source_net(dev)
            for other in circuit.devices:
                if other is dev or not is_transistor(other):
                    continue
                if source_net(other) != src or is_diode_connected(other):
                    continue
                ctrl = control_net(other)
                if ctrl != net and infos[ctrl].role is NetRole.SIGNAL:
                    return True
            return False

        def bias_like(dev):
            if is_rail(source_net(dev)):
                return True  # current source/sink
            if is_rail(drain_net(dev)):
                return False  # source follower input
            if has_diff_peer(dev):
                return False  # differential-pair input
            return True  # mid-stack series device (cascode)

        if all(bias_like(d) for d in gated):
            infos[net].role = NetRole.BIAS
            names = ",".join(d.name for d in drivers)
            infos[net].evidence.append(
                f"dc source {names} drives gate-only net of "
                f"bias-gated devices")

    return infos
