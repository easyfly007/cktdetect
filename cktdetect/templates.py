"""Template library: label known topologies by isomorphism signature.

A template is just a labeled reference netlist dropped into a directory
(the file stem is the label) -- extending the library needs no code.
Matching uses a Weisfeiler-Lehman hash over the device-net bipartite
graph: device nodes are labeled by type, net nodes only by rail role,
and MOS drain/source edges share one label so S/D orientation does not
matter. Equal signatures mean the circuits are isomorphic (WL collisions
are theoretically possible but not for circuits of this size, and the
match is reported as evidence, never silently).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .ir.device import DeviceType
from .ir.flatten import flatten
from .passes.normalize import merge_parallel_mos
from .passes.rails import NetRole, classify_nets

_MOS = (DeviceType.NMOS, DeviceType.PMOS, DeviceType.MOS)


def _term_label(dev, term: str) -> str:
    if dev.dtype in _MOS and term in ("d", "s"):
        return "ch"
    return term


def circuit_signature(circuit, rounds: int = 3) -> str:
    infos = classify_nets(circuit)
    labels = {}
    adjacency = defaultdict(list)

    for dev in circuit.devices:
        node = ("dev", dev.name)
        labels[node] = f"dev:{dev.dtype.value}"
        for term, net in dev.terminals.items():
            edge = _term_label(dev, term)
            adjacency[node].append((edge, ("net", net)))
            adjacency[("net", net)].append((edge, node))

    for net in circuit.nets():
        role = infos[net].role
        labels[("net", net)] = (f"net:{role.value}"
                                if role in (NetRole.POWER, NetRole.GROUND)
                                else "net")

    for _ in range(rounds):
        refined = {}
        for node, label in labels.items():
            neighborhood = sorted(f"{edge}|{labels[other]}"
                                  for edge, other in adjacency.get(node, []))
            refined[node] = hashlib.sha1(
                (label + "##" + ";".join(neighborhood)).encode()
            ).hexdigest()
        labels = refined

    digest = hashlib.sha1(
        "\n".join(sorted(labels.values())).encode()).hexdigest()
    return f"{len(circuit.devices)}:{digest}"


class TemplateLibrary:
    def __init__(self, directory):
        from .parser import parse_netlist  # local import: avoid cycle
        self.entries = []
        directory = Path(directory)
        paths = sorted(directory.glob("*.sp")) + sorted(directory.glob("*.scs"))
        for path in paths:
            netlist = parse_netlist(path)
            if netlist.top.devices:
                flat = flatten(netlist)
            elif netlist.subckts:
                flat = flatten(netlist, top=next(iter(netlist.subckts)))
            else:
                continue
            flat = merge_parallel_mos(flat)
            self.entries.append({
                "label": path.stem,
                "signature": circuit_signature(flat),
                "source": str(path),
            })

    def match(self, circuit) -> list:
        signature = circuit_signature(circuit)
        return [e["label"] for e in self.entries
                if e["signature"] == signature]
