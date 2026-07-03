"""Structure-level netlist comparison (M5).

Compares two analysis reports at the structure level -- classifications,
recognized structures, and device populations -- which is one
abstraction above a raw netlist diff.
"""

from __future__ import annotations

from collections import Counter


def structure_descriptors(report: dict) -> list:
    descs = []
    for s in report.get("structures", []):
        if s["type"] == "current_mirror":
            descs.append(f"current_mirror(pol={s['polarity']},"
                         f"outputs={len(s['outputs'])})")
        elif s["type"] == "differential_pair":
            tail = "tailed" if s.get("tail_source") else "untailed"
            descs.append(f"differential_pair(pol={s['polarity']},{tail})")
        else:
            descs.append(s["type"])
    for xc in report.get("cross_coupled", []):
        descs.append(f"cross_coupled(pol={xc['polarity']})")
    for tank in report.get("tanks", []):
        descs.append(f"lc_tank({tank['style']})")
    return descs


def diff_reports(report_a: dict, report_b: dict) -> dict:
    ca = Counter(structure_descriptors(report_a))
    cb = Counter(structure_descriptors(report_b))
    types_a = [v["type"] for v in report_a.get("classification", [])]
    types_b = [v["type"] for v in report_b.get("classification", [])]
    da = report_a.get("flat", {}).get("devices_by_type", {})
    db = report_b.get("flat", {}).get("devices_by_type", {})
    delta = {k: da.get(k, 0) - db.get(k, 0)
             for k in sorted(set(da) | set(db))
             if da.get(k, 0) != db.get(k, 0)}
    return {
        "classification": {"a": types_a, "b": types_b,
                           "same": types_a[:1] == types_b[:1]},
        "common_structures": sorted((ca & cb).elements()),
        "a_only_structures": sorted((ca - cb).elements()),
        "b_only_structures": sorted((cb - ca).elements()),
        "device_count_delta": delta,
    }
