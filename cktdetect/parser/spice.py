"""Generic SPICE netlist parser (v1 frontend).

Covers the core syntax shared by standard SPICE, ngspice, and HSPICE:
device cards M Q D R C L K V I E G X and the control cards
.subckt/.ends/.model/.param/.global/.end. Dialect-specific extensions
(Spectre, HSPICE-only constructs) are out of scope for v1.

Design choices (see DESIGN.md P1):
- Only topology and key parameters are extracted; unknown constructs are
  skipped with a warning instead of failing the parse.
- Names are case-insensitive and normalized to lowercase.
- The first physical line is treated as the title when it does not parse
  as a statement (standard SPICE behavior for title lines).
- MOS/BJT polarity is resolved after parsing, so .model cards may appear
  anywhere in the file.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..ir.circuit import Circuit, Netlist
from ..ir.device import BJT_TYPES, Device, DeviceType, MOS_TYPES
from .values import resolve_value


class ParseError(Exception):
    pass


_NMOS_NAME_RE = re.compile(r"nmos|nch|nfet|^n")
_PMOS_NAME_RE = re.compile(r"pmos|pch|pfet|^p")
_NPN_NAME_RE = re.compile(r"npn")
_PNP_NAME_RE = re.compile(r"pnp")

_IGNORED_CARDS = {
    ".option", ".options", ".temp", ".op", ".tran", ".ac", ".dc", ".noise",
    ".pz", ".print", ".plot", ".probe", ".save", ".meas", ".measure",
    ".ic", ".nodeset", ".width", ".data", ".enddata", ".protect",
    ".unprotect", ".alter", ".backanno", ".four", ".sens",
}


class SpiceParser:
    _MAX_INCLUDE_DEPTH = 16

    def __init__(self, profile=None):
        self.netlist = Netlist()
        self.profile = profile  # optional PdkProfile
        self._scope = [self.netlist.top]
        self._origin = "<string>"
        self._raw_line = ""
        self._base_dir = Path(".")
        self._include_stack = []

    # ------------------------------------------------------------------
    # public API

    def parse_file(self, path) -> Netlist:
        path = Path(path)
        self._base_dir = path.parent
        return self.parse_string(path.read_text(errors="replace"), source=str(path))

    def parse_string(self, text: str, source: str = "<string>") -> Netlist:
        self._origin = source
        self._process(text, source, top_level=True)
        if len(self._scope) > 1:
            self._warn(f"missing .ends for subckt '{self._scope[-1].name}'")
        self._finalize()
        return self.netlist

    def _process(self, text: str, source: str, top_level: bool = False):
        previous = self._origin
        self._origin = source
        for index, (lineno, line) in enumerate(self._logical_lines(text)):
            self._raw_line = line
            stripped = re.sub(r"\s*=\s*", "=", line.lower())
            try:
                if not self._statement(stripped):
                    break  # .end
            except ParseError as exc:
                if top_level and index == 0 and lineno == 1 and \
                        not self.netlist.title:
                    self.netlist.title = line
                else:
                    self._warn(f"line {lineno}: {exc} -- skipped")
        self._origin = previous

    # ------------------------------------------------------------------
    # include expansion

    def _resolve_include_path(self, raw: str, label: str):
        path = Path(raw)
        if not path.is_absolute():
            path = self._base_dir / path
        if not path.exists():
            self._warn(f"{label} file not found: {raw}")
            return None
        resolved = str(path.resolve())
        if resolved in self._include_stack:
            self._warn(f"{label} cycle detected: {raw}")
            return None
        if len(self._include_stack) >= self._MAX_INCLUDE_DEPTH:
            self._warn(f"{label} nesting deeper than "
                       f"{self._MAX_INCLUDE_DEPTH}: {raw}")
            return None
        return path

    def _process_included(self, path: Path, text: str):
        self._include_stack.append(str(path.resolve()))
        previous_base = self._base_dir
        self._base_dir = path.parent
        self._process(text, str(path))
        self._base_dir = previous_base
        self._include_stack.pop()

    def _include(self, cmd: str, tokens: list):
        if len(tokens) < 2:
            self._warn(f"{cmd} without a file argument")
            return
        raw_tokens = self._raw_line.split()
        raw = (raw_tokens[1] if len(raw_tokens) > 1
               else tokens[1]).strip("'\"")
        path = self._resolve_include_path(raw, cmd)
        if path is None:
            return
        text = path.read_text(errors="replace")
        if cmd == ".lib":
            if len(tokens) < 3:
                self._warn(".lib without a section name -- skipped")
                return
            text = self._lib_section(text, tokens[2])
            if text is None:
                self._warn(f".lib section '{tokens[2]}' not found in {raw}")
                return
        self._process_included(path, text)

    @staticmethod
    def _lib_section(text: str, section: str):
        lines, active = [], False
        for raw in text.splitlines():
            low = raw.strip().lower()
            if low.startswith(".lib"):
                active = low.split()[1:2] == [section]
                continue
            if low.startswith(".endl"):
                active = False
                continue
            if active:
                lines.append(raw)
        return "\n".join(lines) if lines else None

    # ------------------------------------------------------------------
    # line assembly

    @staticmethod
    def _logical_lines(text: str):
        lines = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = re.split(r"\s[;$]", raw, maxsplit=1)[0].strip()
            if not line or line.startswith("*") or line.startswith("//"):
                continue
            if lines and lines[-1][1].endswith("\\"):
                # previous line continues (trailing backslash)
                lines[-1][1] = lines[-1][1][:-1].rstrip() + " " + line
                continue
            if line.startswith("+"):
                if lines:
                    lines[-1][1] += " " + line[1:].strip()
                continue
            lines.append([lineno, line])
        return [(ln, txt) for ln, txt in lines]

    # ------------------------------------------------------------------
    # statements

    def _statement(self, line: str) -> bool:
        if line.startswith("."):
            return self._card(line)
        self._device(line)
        return True

    def _card(self, line: str) -> bool:
        tokens = line.split()
        cmd = tokens[0]
        if cmd == ".end":
            return False
        if cmd == ".subckt":
            if len(tokens) < 2:
                raise ParseError(".subckt requires a name")
            name = tokens[1]
            ports = [t for t in tokens[2:] if "=" not in t]
            circ = Circuit(name=name, ports=ports,
                           params=self._kv_params(tokens[2:]))
            self.netlist.subckts[name] = circ
            self._scope.append(circ)
        elif cmd == ".ends":
            if len(self._scope) > 1:
                self._scope.pop()
            else:
                self._warn(".ends without matching .subckt")
        elif cmd == ".model":
            if len(tokens) < 3:
                raise ParseError("malformed .model card")
            self.netlist.models[tokens[1]] = tokens[2].split("(")[0]
        elif cmd == ".param":
            in_subckt = len(self._scope) > 1
            target = (self._scope[-1].params if in_subckt
                      else self.netlist.params)
            for key, val in self._kv_params(tokens[1:]).items():
                if not isinstance(val, (int, float)) and not in_subckt:
                    self._warn(f"parameter '{key}' has unresolved value '{val}'")
                target[key] = val
        elif cmd == ".global":
            self.netlist.globals.update(tokens[1:])
        elif cmd in (".include", ".inc", ".lib"):
            self._include(".lib" if cmd == ".lib" else cmd, tokens)
        elif cmd not in _IGNORED_CARDS:
            self._warn(f"unknown control card '{cmd}' ignored")
        return True

    # ------------------------------------------------------------------
    # devices

    _HANDLED = "mqdrclkvixeg"

    def _device(self, line: str):
        tokens = line.split()
        name = tokens[0]
        letter = name[0]
        if letter not in self._HANDLED:
            raise ParseError(f"unsupported device card '{name}'")
        params = self._kv_params(tokens[1:])
        pos = [name] + [t for t in tokens[1:] if "=" not in t]
        dev = getattr(self, f"_dev_{letter}")(name, pos, params)
        if dev is not None:
            self._scope[-1].devices.append(dev)

    def _dev_m(self, name, pos, params):
        if len(pos) < 6:
            raise ParseError(f"MOS card '{name}' needs 4 nodes and a model")
        return Device(name=name, dtype=DeviceType.MOS,
                      terminals=dict(zip(("d", "g", "s", "b"), pos[1:5])),
                      model=pos[5], params=params)

    def _dev_q(self, name, pos, params):
        if len(pos) < 5:
            raise ParseError(f"BJT card '{name}' needs 3 or 4 nodes and a model")
        nodes = pos[1:-1]
        if len(nodes) == 3:
            terms = dict(zip(("c", "b", "e"), nodes))
        elif len(nodes) == 4:
            terms = dict(zip(("c", "b", "e", "s"), nodes))
        else:
            raise ParseError(f"BJT card '{name}' has {len(nodes)} nodes")
        return Device(name=name, dtype=DeviceType.BJT, terminals=terms,
                      model=pos[-1], params=params)

    def _dev_d(self, name, pos, params):
        if len(pos) < 4:
            raise ParseError(f"diode card '{name}' needs 2 nodes and a model")
        return Device(name=name, dtype=DeviceType.DIODE,
                      terminals={"p": pos[1], "n": pos[2]},
                      model=pos[3], params=params)

    def _passive(self, name, pos, params, dtype, value_key):
        if len(pos) < 3:
            raise ParseError(f"'{name}' needs two nodes")
        model = None
        value = None
        for tok in pos[3:]:
            resolved = resolve_value(tok, self.netlist.params)
            if resolved is not None and value is None:
                value = resolved
            elif model is None:
                model = tok
        if value is None and isinstance(params.get(value_key), (int, float)):
            value = params[value_key]
        if value is None and model is None:
            raise ParseError(f"'{name}' has no value or model")
        if value is not None:
            params["value"] = value
        else:
            # the unresolved token may be a parameter reference rather
            # than a model name; flattening resolves it against the
            # hierarchical parameter environment
            params.setdefault("value", model)
        return Device(name=name, dtype=dtype,
                      terminals={"p": pos[1], "n": pos[2]},
                      model=model, params=params)

    def _dev_r(self, name, pos, params):
        return self._passive(name, pos, params, DeviceType.RESISTOR, "r")

    def _dev_c(self, name, pos, params):
        return self._passive(name, pos, params, DeviceType.CAPACITOR, "c")

    def _dev_l(self, name, pos, params):
        return self._passive(name, pos, params, DeviceType.INDUCTOR, "l")

    def _dev_k(self, name, pos, params):
        if len(pos) < 4:
            raise ParseError(f"mutual inductor '{name}' needs L1 L2 k")
        params["inductors"] = [pos[1], pos[2]]
        coupling = resolve_value(pos[3], self.netlist.params)
        params["coupling"] = coupling if coupling is not None else pos[3]
        return Device(name=name, dtype=DeviceType.MUTUAL, params=params)

    def _source(self, name, pos, params, dtype):
        if len(pos) < 3:
            raise ParseError(f"source '{name}' needs two nodes")
        rest = pos[3:]
        dc = params.get("dc")
        if dc is None and rest:
            if rest[0] == "dc" and len(rest) > 1:
                dc = resolve_value(rest[1], self.netlist.params)
            else:
                dc = resolve_value(rest[0], self.netlist.params)
        if isinstance(dc, (int, float)):
            params["dc"] = dc
        if rest:
            params.setdefault("spec", " ".join(rest))
        return Device(name=name, dtype=dtype,
                      terminals={"p": pos[1], "n": pos[2]}, params=params)

    def _dev_v(self, name, pos, params):
        return self._source(name, pos, params, DeviceType.VSOURCE)

    def _dev_i(self, name, pos, params):
        return self._source(name, pos, params, DeviceType.ISOURCE)

    def _dev_x(self, name, pos, params):
        pos = [t for t in pos if t != "/"]  # CDL: X<nets> / <subckt>
        if len(pos) < 3:
            raise ParseError(
                f"subckt instance '{name}' needs nodes and a subckt name")
        nets = pos[1:-1]
        return Device(name=name, dtype=DeviceType.SUBCKT,
                      terminals={str(i + 1): n for i, n in enumerate(nets)},
                      params=params, subckt=pos[-1])

    def _controlled(self, name, pos, params, dtype):
        if len(pos) < 6:
            raise ParseError(f"controlled source '{name}' needs 4 nodes and a gain")
        gain = resolve_value(pos[5], self.netlist.params)
        params["gain"] = gain if gain is not None else pos[5]
        return Device(name=name, dtype=dtype,
                      terminals=dict(zip(("p", "n", "cp", "cn"), pos[1:5])),
                      params=params)

    def _dev_e(self, name, pos, params):
        return self._controlled(name, pos, params, DeviceType.VCVS)

    def _dev_g(self, name, pos, params):
        return self._controlled(name, pos, params, DeviceType.VCCS)

    # ------------------------------------------------------------------
    # helpers

    def _kv_params(self, tokens) -> dict:
        out = {}
        for tok in tokens:
            if "=" not in tok:
                continue
            key, _, val = tok.partition("=")
            resolved = resolve_value(val, self.netlist.params)
            out[key] = resolved if resolved is not None else val
        return out

    def _warn(self, message: str):
        self.netlist.warnings.append(f"{self._origin}: {message}")

    def _finalize(self):
        """Resolve MOS/BJT polarity once all .model cards are known."""
        circuits = [self.netlist.top, *self.netlist.subckts.values()]
        for circ in circuits:
            for dev in circ.devices:
                if dev.dtype in MOS_TYPES:
                    dev.dtype = self._mos_polarity(dev)
                elif dev.dtype in BJT_TYPES:
                    dev.dtype = self._bjt_polarity(dev)

    def _mos_polarity(self, dev) -> DeviceType:
        if self.profile is not None:
            mapped = self.profile.model_type(dev.model)
            if mapped == "nmos":
                return DeviceType.NMOS
            if mapped == "pmos":
                return DeviceType.PMOS
        mtype = self.netlist.models.get(dev.model)
        if mtype == "nmos":
            return DeviceType.NMOS
        if mtype == "pmos":
            return DeviceType.PMOS
        if _NMOS_NAME_RE.search(dev.model):
            return DeviceType.NMOS
        if _PMOS_NAME_RE.search(dev.model):
            return DeviceType.PMOS
        self._warn(
            f"cannot infer MOS polarity of '{dev.name}' from model '{dev.model}'")
        return DeviceType.MOS

    def _bjt_polarity(self, dev) -> DeviceType:
        if self.profile is not None:
            mapped = self.profile.model_type(dev.model)
            if mapped == "npn":
                return DeviceType.NPN
            if mapped == "pnp":
                return DeviceType.PNP
        mtype = self.netlist.models.get(dev.model)
        if mtype == "npn":
            return DeviceType.NPN
        if mtype == "pnp":
            return DeviceType.PNP
        if _NPN_NAME_RE.search(dev.model):
            return DeviceType.NPN
        if _PNP_NAME_RE.search(dev.model):
            return DeviceType.PNP
        self._warn(
            f"cannot infer BJT polarity of '{dev.name}' from model '{dev.model}'")
        return DeviceType.BJT
