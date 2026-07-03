"""Electrical normalization (DESIGN.md P3).

v1 implements parallel MOS merging: identical MOS devices sharing the
same gate/bulk and the same channel net pair (source/drain order is
electrically symmetric) collapse into one device with summed m-factor.
"""

from __future__ import annotations

from ..ir.circuit import Circuit
from ..ir.device import Device, DeviceType


def _m_factor(dev: Device) -> float:
    m = dev.params.get("m")
    return float(m) if isinstance(m, (int, float)) else 1.0


def merge_parallel_mos(circuit: Circuit) -> Circuit:
    """Return a new circuit with parallel identical MOS devices merged."""
    merged = Circuit(name=circuit.name, ports=list(circuit.ports),
                     params=dict(circuit.params))
    groups = {}
    order = []
    for dev in circuit.devices:
        if dev.dtype in (DeviceType.NMOS, DeviceType.PMOS, DeviceType.MOS):
            key = (
                dev.dtype,
                dev.model,
                dev.terminals.get("g"),
                dev.terminals.get("b"),
                frozenset((dev.terminals.get("d"), dev.terminals.get("s"))),
                dev.params.get("w"),
                dev.params.get("l"),
            )
        else:
            key = ("__unique__", dev.name)
        if key in groups:
            groups[key].append(dev)
        else:
            groups[key] = [dev]
            order.append(key)

    for key in order:
        devs = groups[key]
        first = devs[0]
        if len(devs) == 1:
            merged.devices.append(first)
            continue
        combined = Device(
            name=first.name,
            dtype=first.dtype,
            terminals=dict(first.terminals),
            model=first.model,
            params=dict(first.params),
        )
        combined.params["m"] = sum(_m_factor(d) for d in devs)
        combined.params["merged_from"] = [d.name for d in devs]
        merged.devices.append(combined)
    return merged
