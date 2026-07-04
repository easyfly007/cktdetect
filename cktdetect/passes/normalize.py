"""Electrical normalization (DESIGN.md P3).

- Parallel MOS merging: identical MOS devices sharing the same
  gate/bulk and the same channel net pair (source/drain order is
  electrically symmetric) collapse into one device with summed m-factor.
- Series MOS merging: same-gate stacked segments (a long device split
  in two, common in real PDK netlists) collapse into one device with
  summed channel length, provided the intermediate net belongs
  exclusively to the two channel terminals.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ..ir.circuit import Circuit
from ..ir.device import Device, DeviceType

_MOS = (DeviceType.NMOS, DeviceType.PMOS, DeviceType.MOS)


def _m_factor(dev: Device) -> float:
    m = dev.params.get("m")
    return float(m) if isinstance(m, (int, float)) else 1.0


def merge_series_mos(circuit: Circuit) -> Circuit:
    """Return a new circuit with same-gate series MOS segments merged."""
    devices = list(circuit.devices)
    ports = set(circuit.ports)

    changed = True
    while changed:
        changed = False
        connections = Counter()
        for dev in devices:
            for net in dev.terminals.values():
                connections[net] += 1
        by_channel = defaultdict(list)
        for dev in devices:
            if dev.dtype in _MOS:
                for term in ("d", "s"):
                    by_channel[dev.terminals[term]].append((dev, term))

        for net, items in by_channel.items():
            if len(items) != 2 or connections[net] != 2:
                continue  # the mid net must belong to exactly these two
            if net in ports or net == "0":
                continue
            (dev_a, _), (dev_b, _) = items
            if dev_a is dev_b:
                continue
            if dev_a.dtype is not dev_b.dtype or dev_a.model != dev_b.model:
                continue
            if dev_a.terminals.get("g") != dev_b.terminals.get("g"):
                continue  # different gates: cascode, not a split device
            if dev_a.terminals.get("b") != dev_b.terminals.get("b"):
                continue
            if dev_a.params.get("w") != dev_b.params.get("w") or \
                    dev_a.params.get("m", 1.0) != dev_b.params.get("m", 1.0):
                continue
            drain = (dev_a.terminals["d"] if dev_a.terminals["d"] != net
                     else dev_b.terminals["d"])
            source = (dev_a.terminals["s"] if dev_a.terminals["s"] != net
                      else dev_b.terminals["s"])
            if drain == source:
                continue
            params = dict(dev_a.params)
            l_a, l_b = dev_a.params.get("l"), dev_b.params.get("l")
            if isinstance(l_a, (int, float)) and isinstance(l_b, (int, float)):
                params["l"] = l_a + l_b
            params["merged_series"] = (
                dev_a.params.get("merged_series", [dev_a.name])
                + dev_b.params.get("merged_series", [dev_b.name]))
            merged = Device(
                name=dev_a.name, dtype=dev_a.dtype,
                terminals={"d": drain, "g": dev_a.terminals["g"],
                           "s": source, "b": dev_a.terminals.get("b")},
                model=dev_a.model, params=params)
            devices = [merged if d is dev_a else d
                       for d in devices if d is not dev_b]
            changed = True
            break  # connection census is stale; rescan

    result = Circuit(name=circuit.name, ports=list(circuit.ports),
                     params=dict(circuit.params))
    result.devices = devices
    return result


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
