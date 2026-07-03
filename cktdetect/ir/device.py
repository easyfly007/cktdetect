"""Canonical device IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DeviceType(str, Enum):
    NMOS = "nmos"
    PMOS = "pmos"
    MOS = "mos"  # MOS with unknown polarity
    NPN = "npn"
    PNP = "pnp"
    BJT = "bjt"  # BJT with unknown polarity
    DIODE = "diode"
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"
    MUTUAL = "mutual"
    VSOURCE = "vsource"
    ISOURCE = "isource"
    VCVS = "vcvs"
    VCCS = "vccs"
    SUBCKT = "subckt"


MOS_TYPES = {DeviceType.NMOS, DeviceType.PMOS, DeviceType.MOS}
BJT_TYPES = {DeviceType.NPN, DeviceType.PNP, DeviceType.BJT}


@dataclass
class Device:
    """A parsed circuit element.

    ``terminals`` maps terminal roles to net names, preserving card order:
    MOS: d/g/s/b; BJT: c/b/e[/s]; two-terminal devices: p/n;
    subckt instances: positional keys "1".."n".
    """

    name: str
    dtype: DeviceType
    terminals: dict = field(default_factory=dict)
    model: str | None = None
    params: dict = field(default_factory=dict)
    subckt: str | None = None

    @property
    def nets(self) -> list:
        return list(self.terminals.values())
