"""Hierarchy flattening: expand subckt instances into a flat circuit."""

from __future__ import annotations

from .circuit import Circuit, Netlist
from .device import Device, DeviceType

SEP = "."


def flatten(netlist: Netlist, top: str | None = None) -> Circuit:
    """Return a flat circuit with hierarchical instance paths in names.

    ``top`` selects a subckt to flatten; default is the top-level devices.
    Global nets (node 0 and ``.global``) keep their names; other nets and
    device names inside instances get a ``<instance>.`` prefix.
    """
    if top is not None:
        if top not in netlist.subckts:
            raise KeyError(f"subckt '{top}' not defined")
        root = netlist.subckts[top]
    else:
        root = netlist.top

    flat = Circuit(name=root.name, ports=list(root.ports))

    def resolve(net: str, prefix: str, netmap: dict) -> str:
        if net == "0" or net in netlist.globals:
            return net
        if net in netmap:
            return netmap[net]
        return prefix + net

    def expand(circ: Circuit, prefix: str, netmap: dict, stack: frozenset):
        for dev in circ.devices:
            if dev.dtype is DeviceType.SUBCKT:
                sub = netlist.subckts.get(dev.subckt)
                if sub is None:
                    raise ValueError(
                        f"undefined subckt '{dev.subckt}' instantiated by "
                        f"'{prefix + dev.name}'"
                    )
                if dev.subckt in stack:
                    raise ValueError(
                        f"recursive instantiation of subckt '{dev.subckt}'"
                    )
                conns = list(dev.terminals.values())
                if len(conns) != len(sub.ports):
                    raise ValueError(
                        f"instance '{prefix + dev.name}' connects {len(conns)} "
                        f"nets but subckt '{sub.name}' has {len(sub.ports)} ports"
                    )
                inner_map = {
                    port: resolve(net, prefix, netmap)
                    for port, net in zip(sub.ports, conns)
                }
                expand(sub, prefix + dev.name + SEP, inner_map,
                       stack | {dev.subckt})
            else:
                flat.devices.append(
                    Device(
                        name=prefix + dev.name,
                        dtype=dev.dtype,
                        terminals={
                            t: resolve(n, prefix, netmap)
                            for t, n in dev.terminals.items()
                        },
                        model=dev.model,
                        params=dict(dev.params),
                    )
                )

    expand(root, "", {}, frozenset())
    return flat
