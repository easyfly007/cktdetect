"""Device family helpers shared by the role and structure passes.

MOS and BJT are treated uniformly: the control terminal (gate/base)
does not conduct DC; the channel terminals (drain-source /
collector-emitter) do.
"""

from __future__ import annotations

from ..ir.device import Device, DeviceType

_MOS = {DeviceType.NMOS, DeviceType.PMOS, DeviceType.MOS}
_BJT = {DeviceType.NPN, DeviceType.PNP, DeviceType.BJT}

_CTRL_TERM = {**{t: "g" for t in _MOS}, **{t: "b" for t in _BJT}}
_DRAIN_TERM = {**{t: "d" for t in _MOS}, **{t: "c" for t in _BJT}}
_SOURCE_TERM = {**{t: "s" for t in _MOS}, **{t: "e" for t in _BJT}}

_POLARITY = {
    DeviceType.NMOS: "n",
    DeviceType.NPN: "n",
    DeviceType.PMOS: "p",
    DeviceType.PNP: "p",
}

# terminals that conduct DC current
_CONDUCTING = {
    **{t: ("d", "s") for t in _MOS},
    **{t: ("c", "e") for t in _BJT},
    DeviceType.DIODE: ("p", "n"),
    DeviceType.RESISTOR: ("p", "n"),
    DeviceType.INDUCTOR: ("p", "n"),
    DeviceType.VSOURCE: ("p", "n"),
    DeviceType.ISOURCE: ("p", "n"),
    DeviceType.VCVS: ("p", "n"),
    DeviceType.VCCS: ("p", "n"),
    DeviceType.CAPACITOR: (),
    DeviceType.MUTUAL: (),
    DeviceType.SUBCKT: (),
}


def is_transistor(dev: Device) -> bool:
    return dev.dtype in _CTRL_TERM


def control_term(dev: Device) -> str | None:
    return _CTRL_TERM.get(dev.dtype)


def control_net(dev: Device) -> str | None:
    term = _CTRL_TERM.get(dev.dtype)
    return dev.terminals.get(term) if term else None


def drain_net(dev: Device) -> str | None:
    term = _DRAIN_TERM.get(dev.dtype)
    return dev.terminals.get(term) if term else None


def source_net(dev: Device) -> str | None:
    term = _SOURCE_TERM.get(dev.dtype)
    return dev.terminals.get(term) if term else None


def polarity(dev: Device) -> str | None:
    """'n' or 'p'; None for non-transistors and unknown polarity."""
    return _POLARITY.get(dev.dtype)


def is_diode_connected(dev: Device) -> bool:
    return (is_transistor(dev)
            and control_net(dev) is not None
            and control_net(dev) == drain_net(dev))


def conducting_nets(dev: Device) -> list:
    return [dev.terminals[t] for t in _CONDUCTING.get(dev.dtype, ())
            if t in dev.terminals]


def strength(dev: Device) -> float | None:
    """Relative current strength W*m/L; None when geometry is unknown."""
    w, l = dev.params.get("w"), dev.params.get("l")
    m = dev.params.get("m", 1.0)
    if all(isinstance(v, (int, float)) for v in (w, l, m)) and l:
        return w * m / l
    return None
