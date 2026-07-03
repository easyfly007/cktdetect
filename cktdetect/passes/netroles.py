"""Net role labeling: rail / bias / signal (DESIGN.md P4).

Builds on rail classification and promotes SIGNAL nets to BIAS when:

A. the net is driven by a diode-connected transistor (this is also how
   current-mirror families surface: the diode is the reference, every
   same-polarity transistor gated by the net is a candidate output); or
B. the net fans out only to control terminals, is driven only by DC
   sources, and every gated device sits with its source on a rail
   (a DC source driving the gate of a non-rail-sourced device is a
   signal input, e.g. a testbench voltage on a diff-pair gate).
"""

from __future__ import annotations

from collections import defaultdict

from ..ir.circuit import Circuit
from ..ir.device import DeviceType
from .families import (control_net, control_term, is_diode_connected,
                       is_transistor, source_net)
from .rails import NetRole, classify_nets

_AC_SPEC_KEYWORDS = ("ac", "sin", "pulse", "pwl", "exp")


def _is_dc_driver(dev) -> bool:
    if dev.dtype not in (DeviceType.VSOURCE, DeviceType.ISOURCE):
        return False
    if not isinstance(dev.params.get("dc"), (int, float)):
        return False
    spec = str(dev.params.get("spec", ""))
    return not any(key in spec for key in _AC_SPEC_KEYWORDS)


def classify_net_roles(circuit: Circuit) -> dict:
    """Return {net: NetInfo} with POWER/GROUND/BIAS/SIGNAL roles."""
    infos = classify_nets(circuit)

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
        if all(source_net(d) is not None and is_rail(source_net(d))
               for d in gated):
            infos[net].role = NetRole.BIAS
            names = ",".join(d.name for d in drivers)
            infos[net].evidence.append(
                f"dc source {names} drives gate-only net of "
                f"rail-sourced devices")

    return infos
