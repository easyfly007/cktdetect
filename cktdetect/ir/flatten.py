"""Hierarchy flattening: expand subckt instances into a flat circuit.

Parameter handling: device parameters that the parser could not resolve
(strings referencing subckt arguments or scoped ``.param`` values) are
resolved here against the hierarchical environment -- global parameters,
the subckt's defaults and scoped parameters, and the instance's
overrides, in that order. An ``m=`` factor on an instance multiplies
into the m-factors of all devices below it.
"""

from __future__ import annotations

from .circuit import Circuit, Netlist
from .device import Device, DeviceType

SEP = "."


def _numeric_layer(env: dict, params: dict) -> dict:
    """Extend ``env`` with the numeric values of ``params``, resolving
    string entries sequentially so later entries may reference earlier
    ones."""
    from ..parser.values import resolve_value  # deferred: avoids import cycle

    out = dict(env)
    for key, val in params.items():
        if isinstance(val, (int, float)):
            out[key] = float(val)
        elif isinstance(val, str):
            resolved = resolve_value(val, out)
            if resolved is not None:
                out[key] = resolved
    return out


def _resolve_device_params(params: dict, env: dict, mult: float) -> dict:
    from ..parser.values import resolve_value  # deferred: avoids import cycle

    out = {}
    for key, val in params.items():
        if isinstance(val, str):
            resolved = resolve_value(val, env)
            out[key] = resolved if resolved is not None else val
        else:
            out[key] = val
    if mult != 1:
        m = out.get("m", 1.0)
        m = float(m) if isinstance(m, (int, float)) else 1.0
        out["m"] = m * mult
    return out


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

    def expand(circ: Circuit, prefix: str, netmap: dict, stack: frozenset,
               env: dict, mult: float):
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
                inst_params = _resolve_device_params(dev.params, env, 1)
                child_mult = mult
                m_val = inst_params.get("m")
                if isinstance(m_val, (int, float)):
                    child_mult = mult * float(m_val)
                # defaults and scoped params, with instance overrides
                # substituted in place so dependent expressions see them
                merged = dict(sub.params)
                merged.update(inst_params)
                child_env = _numeric_layer(
                    _numeric_layer({}, netlist.params), merged)
                expand(sub, prefix + dev.name + SEP, inner_map,
                       stack | {dev.subckt}, child_env, child_mult)
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
                        params=_resolve_device_params(dev.params, env, mult),
                    )
                )

    root_env = _numeric_layer(_numeric_layer({}, netlist.params), root.params)
    expand(root, "", {}, frozenset(), root_env, 1)
    return flat
