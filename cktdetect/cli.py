"""Command-line entry point: parse, flatten, analyze, report."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from .ir.flatten import flatten
from .parser.spice import SpiceParser
from .passes.branches import decompose_branches
from .passes.devroles import assign_device_roles
from .passes.netroles import classify_net_roles
from .passes.normalize import merge_parallel_mos
from .passes.structures import (apply_structure_roles, find_current_mirrors,
                                find_differential_pairs)


def analyze(flat):
    """Run the M1 analysis pipeline on a flat circuit."""
    infos = classify_net_roles(flat)
    branches, non_dc = decompose_branches(flat, infos)
    mirrors = find_current_mirrors(flat, infos)
    pairs = find_differential_pairs(flat, infos)
    roles = assign_device_roles(flat, infos)
    apply_structure_roles(roles, mirrors, pairs)
    return {
        "net_roles": {
            net: {"role": info.role.value, "evidence": info.evidence}
            for net, info in infos.items()
        },
        "branches": [
            {"devices": b.devices, "rails": b.rails,
             "internal_nets": b.internal_nets, "forks": b.forks}
            for b in branches
        ],
        "non_dc_devices": non_dc,
        "device_roles": roles,
        "structures": mirrors + pairs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="cktdetect",
        description="Rule-based circuit structure detection from SPICE netlists",
    )
    ap.add_argument("netlist", help="SPICE netlist file")
    ap.add_argument("--top",
                    help="analyze this subckt instead of the top-level devices")
    ap.add_argument("-o", "--output",
                    help="write the JSON report to this file (default: stdout)")
    args = ap.parse_args(argv)

    netlist = SpiceParser().parse_file(args.netlist)
    flat = merge_parallel_mos(flatten(netlist, top=args.top))

    report = {
        "title": netlist.title,
        "subckts": {
            name: {"ports": sub.ports, "device_count": len(sub.devices)}
            for name, sub in netlist.subckts.items()
        },
        "flat": {
            "device_count": len(flat.devices),
            "net_count": len(flat.nets()),
            "devices_by_type": dict(
                Counter(d.dtype.value for d in flat.devices)),
        },
        **analyze(flat),
        "warnings": netlist.warnings,
    }
    text = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0
