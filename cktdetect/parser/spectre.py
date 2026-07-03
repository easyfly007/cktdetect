"""Spectre netlist frontend (M5).

Parses the common Spectre core into the same Netlist IR as the SPICE
frontend: ``subckt/ends``, ``model``, ``parameters``, ``global``,
``include`` (warned, not expanded), and instance lines

    name (node node ...) master param=value ...

The parenthesis-free instance form is also accepted (last positional
token is the master). Primitive masters (resistor, capacitor, inductor,
vsource, isource, diode) map directly; ``model`` statements resolve
MOS/BJT polarity via their ``type=`` parameter; unknown masters become
subckt instances, and 4-terminal masters with MOS-like names fall back
to name-based polarity inference.
"""

from __future__ import annotations

import re

from ..ir.circuit import Circuit
from ..ir.device import Device, DeviceType
from .spice import (ParseError, SpiceParser, _NMOS_NAME_RE, _PMOS_NAME_RE)

_IGNORED = {
    "simulator", "save", "ic", "options", "option", "info", "set",
    "sens", "dc", "ac", "tran", "noise", "sweep", "montecarlo", "alter",
    "statistics", "sp", "pss", "pnoise",
}

_INSTANCE_RE = re.compile(r"^(\S+)\s*\(([^)]*)\)\s*(\S+)\s*(.*)$")


class SpectreParser(SpiceParser):
    def parse_string(self, text: str, source: str = "<string>"):
        self._origin = source
        for lineno, line in self._spectre_lines(text):
            stripped = re.sub(r"\s*=\s*", "=", line.lower())
            try:
                self._spectre_statement(stripped)
            except ParseError as exc:
                self._warn(f"line {lineno}: {exc} -- skipped")
        if len(self._scope) > 1:
            self._warn(f"missing ends for subckt '{self._scope[-1].name}'")
        self._finalize()
        return self.netlist

    # ------------------------------------------------------------------

    @staticmethod
    def _spectre_lines(text: str):
        lines = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.split("//", 1)[0].rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            if lines and lines[-1][1].endswith("\\"):
                lines[-1][1] = lines[-1][1][:-1].rstrip() + " " + stripped
                continue
            if stripped.startswith("+") and lines:
                lines[-1][1] += " " + stripped[1:].strip()
                continue
            lines.append([lineno, stripped])
        return [(ln, txt) for ln, txt in lines]

    # ------------------------------------------------------------------

    def _spectre_statement(self, line: str):
        tokens = line.split()
        head = tokens[0]
        if head in _IGNORED:
            return
        if head == "global":
            self.netlist.globals.update(tokens[1:])
            return
        if head == "parameters":
            for key, val in self._kv_params(tokens[1:]).items():
                self.netlist.params[key] = val
            return
        if head == "subckt":
            if len(tokens) < 2:
                raise ParseError("subckt requires a name")
            ports = [t.strip("()") for t in tokens[2:] if "=" not in t]
            circ = Circuit(name=tokens[1], ports=[p for p in ports if p],
                           params=self._kv_params(tokens[2:]))
            self.netlist.subckts[tokens[1]] = circ
            self._scope.append(circ)
            return
        if head == "ends":
            if len(self._scope) > 1:
                self._scope.pop()
            else:
                self._warn("ends without matching subckt")
            return
        if head == "model":
            if len(tokens) < 3:
                raise ParseError("malformed model statement")
            self._register_model(tokens[1], tokens[2],
                                 self._kv_params(tokens[3:]))
            return
        if head in ("include", "ahdl_include"):
            self._warn(f"{head} is not expanded in v1: "
                       f"{' '.join(tokens[1:])}")
            return
        self._instance(line)

    def _register_model(self, name, master, params):
        mtype = str(params.get("type", ""))
        if mtype == "n":
            self.netlist.models[name] = "nmos"
        elif mtype == "p":
            self.netlist.models[name] = "pmos"
        elif mtype in ("npn", "pnp"):
            self.netlist.models[name] = mtype
        elif master in ("resistor", "capacitor", "inductor", "diode"):
            self.netlist.models[name] = \
                "d" if master == "diode" else master[0]
        else:
            self.netlist.models[name] = master

    # ------------------------------------------------------------------

    def _instance(self, line: str):
        match = _INSTANCE_RE.match(line)
        if match:
            name = match.group(1)
            nodes = match.group(2).split()
            master = match.group(3)
            params = self._kv_params(match.group(4).split())
        else:
            tokens = line.split()
            params = self._kv_params(tokens[1:])
            pos = [t for t in tokens if "=" not in t]
            if len(pos) < 3:
                raise ParseError(f"cannot parse instance '{tokens[0]}'")
            name, nodes, master = pos[0], pos[1:-1], pos[-1]
        self._scope[-1].devices.append(
            self._build_instance(name, nodes, master, params))

    def _build_instance(self, name, nodes, master, params) -> Device:
        def passive(dtype, key):
            if len(nodes) < 2:
                raise ParseError(f"'{name}' needs two nodes")
            if isinstance(params.get(key), (int, float)):
                params["value"] = params[key]
            return Device(name=name, dtype=dtype,
                          terminals={"p": nodes[0], "n": nodes[1]},
                          params=params)

        if master == "resistor":
            return passive(DeviceType.RESISTOR, "r")
        if master == "capacitor":
            return passive(DeviceType.CAPACITOR, "c")
        if master == "inductor":
            return passive(DeviceType.INDUCTOR, "l")
        if master in ("vsource", "isource"):
            if len(nodes) < 2:
                raise ParseError(f"source '{name}' needs two nodes")
            dtype = (DeviceType.VSOURCE if master == "vsource"
                     else DeviceType.ISOURCE)
            return Device(name=name, dtype=dtype,
                          terminals={"p": nodes[0], "n": nodes[1]},
                          params=params)

        mtype = self.netlist.models.get(master)
        mos_like = mtype in ("nmos", "pmos") or (
            mtype is None and len(nodes) == 4 and
            (_NMOS_NAME_RE.search(master) or _PMOS_NAME_RE.search(master)))
        if mos_like:
            if len(nodes) != 4:
                raise ParseError(f"MOS instance '{name}' needs 4 nodes")
            return Device(name=name, dtype=DeviceType.MOS,
                          terminals=dict(zip(("d", "g", "s", "b"), nodes)),
                          model=master, params=params)
        if mtype in ("npn", "pnp"):
            keys = ("c", "b", "e", "s")[:len(nodes)]
            return Device(name=name, dtype=DeviceType.BJT,
                          terminals=dict(zip(keys, nodes)),
                          model=master, params=params)
        if mtype == "d":
            return Device(name=name, dtype=DeviceType.DIODE,
                          terminals={"p": nodes[0], "n": nodes[1]},
                          model=master, params=params)
        if mtype in ("r", "c", "l"):
            dtype = {"r": DeviceType.RESISTOR, "c": DeviceType.CAPACITOR,
                     "l": DeviceType.INDUCTOR}[mtype]
            return passive(dtype, mtype)
        return Device(name=name, dtype=DeviceType.SUBCKT,
                      terminals={str(i + 1): n for i, n in enumerate(nodes)},
                      params=params, subckt=master)
