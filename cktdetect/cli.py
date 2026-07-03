"""Command-line entry point: parse, flatten, analyze, report."""

from __future__ import annotations

import argparse
import json
from collections import Counter

from .classify.context import build_context
from .classify.engine import classify
from .diffcmp import diff_reports
from .ir.device import DeviceType
from .ir.flatten import flatten
from .parser import parse_netlist
from .passes.normalize import merge_parallel_mos
from .templates import TemplateLibrary
from .viewer import render_html


def analyze(flat):
    """Run the analysis pipeline on a flat circuit."""
    ctx = build_context(flat)
    return {
        "classification": classify(ctx),
        "net_roles": {
            net: {"role": info.role.value, "evidence": info.evidence}
            for net, info in ctx.infos.items()
        },
        "branches": [
            {"devices": b.devices, "rails": b.rails,
             "internal_nets": b.internal_nets, "forks": b.forks}
            for b in ctx.branches
        ],
        "non_dc_devices": ctx.non_dc,
        "device_roles": ctx.roles,
        "structures": ctx.mirrors + ctx.pairs,
        "cross_coupled": ctx.cross_coupled,
        "tanks": ctx.tanks,
        "stage_edges": ctx.stage_edges,
    }


def _composition(netlist) -> dict:
    counts = Counter()

    def walk(circ, mult, depth):
        if depth > 50:
            return
        for dev in circ.devices:
            if dev.dtype is DeviceType.SUBCKT and \
                    dev.subckt in netlist.subckts:
                counts[dev.subckt] += mult
                walk(netlist.subckts[dev.subckt], mult, depth + 1)

    walk(netlist.top, 1, 0)
    return dict(counts)


def _subckt_analysis(netlist) -> dict:
    result = {}
    for name in netlist.subckts:
        try:
            flat = merge_parallel_mos(flatten(netlist, top=name))
            result[name] = classify(build_context(flat))
        except ValueError as exc:
            result[name] = [{"type": "error", "confidence": 0.0,
                             "evidence": [], "note": str(exc)}]
    return result


def build_report(path, top=None, dialect="auto", template_dir=None) -> dict:
    netlist = parse_netlist(path, dialect=dialect)
    flat = merge_parallel_mos(flatten(netlist, top=top))
    report = {
        "netlist": str(path),
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
        "subckt_analysis": _subckt_analysis(netlist),
        "composition": _composition(netlist),
        "warnings": netlist.warnings,
    }
    if template_dir:
        matches = TemplateLibrary(template_dir).match(flat)
        for label in reversed(matches):
            report["classification"].insert(0, {
                "type": f"template:{label}", "confidence": 0.97,
                "evidence": ["graph-isomorphic to template netlist"],
            })
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="cktdetect",
        description="Rule-based circuit type detection from SPICE netlists",
    )
    ap.add_argument("netlist", help="netlist file (SPICE or Spectre)")
    ap.add_argument("--top",
                    help="analyze this subckt instead of the top-level devices")
    ap.add_argument("--dialect", choices=("auto", "spice", "spectre"),
                    default="auto", help="netlist dialect (default: auto)")
    ap.add_argument("--templates", metavar="DIR",
                    help="directory of labeled template netlists")
    ap.add_argument("--html", metavar="FILE",
                    help="also write an HTML report")
    ap.add_argument("--diff", metavar="OTHER",
                    help="compare against a second netlist at structure level")
    ap.add_argument("-o", "--output",
                    help="write the JSON report to this file (default: stdout)")
    args = ap.parse_args(argv)

    report = build_report(args.netlist, top=args.top, dialect=args.dialect,
                          template_dir=args.templates)
    if args.diff:
        other = build_report(args.diff, dialect=args.dialect,
                             template_dir=args.templates)
        payload = {"a": args.netlist, "b": args.diff,
                   "diff": diff_reports(report, other)}
    else:
        payload = report

    if args.html:
        with open(args.html, "w") as fh:
            fh.write(render_html(report))

    text = json.dumps(payload, indent=2)
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0
