"""Command-line entry point: parse, flatten, normalize, classify rails."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from .ir.flatten import flatten
from .parser.spice import SpiceParser
from .passes.normalize import merge_parallel_mos
from .passes.rails import classify_nets


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
    roles = classify_nets(flat)

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
        "net_roles": {
            net: {"role": info.role.value, "evidence": info.evidence}
            for net, info in roles.items()
        },
        "warnings": netlist.warnings,
    }
    text = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0
