"""Circuit and netlist containers."""

from __future__ import annotations

from dataclasses import dataclass, field

from .device import Device


@dataclass
class Circuit:
    """A flat list of devices: either a subckt definition or a top level."""

    name: str
    ports: list = field(default_factory=list)
    devices: list = field(default_factory=list)
    params: dict = field(default_factory=dict)

    def nets(self) -> set:
        result = set()
        for dev in self.devices:
            result.update(dev.terminals.values())
        return result

    def device(self, name: str) -> Device:
        for dev in self.devices:
            if dev.name == name:
                return dev
        raise KeyError(f"no device '{name}' in circuit '{self.name}'")


@dataclass
class Netlist:
    """Parse result: hierarchy tree plus global tables."""

    title: str = ""
    top: Circuit = field(default_factory=lambda: Circuit("__top__"))
    subckts: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)  # model name -> spice model type
    globals: set = field(default_factory=set)
    params: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
