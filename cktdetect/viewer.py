"""Self-contained HTML report with an SVG branch diagram (M5)."""

from __future__ import annotations

import html

_ROLE_COLORS = {
    "diff_input": "#4f83cc",
    "common_source": "#4f83cc",
    "amplifier": "#4f83cc",
    "source_follower": "#5bc0de",
    "cascode": "#3aa17e",
    "diode": "#c98e2b",
    "mirror_reference": "#c98e2b",
    "mirror_output": "#e0b25b",
    "current_source": "#9a9a9a",
    "current_sink": "#9a9a9a",
    "bias_gated": "#9a9a9a",
    "tail_current_source": "#7a4fcc",
    "rail_tied": "#cccccc",
}
_DEFAULT_COLOR = "#b8b8b8"

_CSS = """
body{font-family:system-ui,sans-serif;margin:1.5em;max-width:1100px}
h1{font-size:1.3em} h2{font-size:1.05em;margin-top:1.6em}
table{border-collapse:collapse;font-size:0.85em}
td,th{border:1px solid #ccc;padding:3px 8px;text-align:left}
.verdict{border:1px solid #ddd;border-radius:6px;padding:8px 12px;
 margin:6px 0;background:#fafafa}
.bar{height:8px;background:#4f83cc;border-radius:4px;margin-top:4px}
.conf{float:right;color:#666}
ul.ev{margin:4px 0 0 1.2em;color:#444;font-size:0.85em}
.legend span{display:inline-block;margin-right:12px;font-size:0.8em}
.legend i{display:inline-block;width:10px;height:10px;margin-right:4px;
 border-radius:2px}
"""


def _svg_branches(report: dict) -> str:
    branches = report.get("branches", [])
    roles = report.get("device_roles", {})
    if not branches:
        return ""
    col_w, box_h, pad = 150, 26, 10
    max_stack = max(len(b["devices"]) for b in branches)
    width = col_w * len(branches) + pad * 2
    height = max_stack * (box_h + 6) + 90
    parts = [f'<svg width="{width}" height="{height}" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'font-family="monospace" font-size="11">']
    parts.append(f'<rect x="0" y="10" width="{width}" height="8" '
                 f'fill="#d9534f"/><text x="4" y="34" fill="#d9534f">'
                 f'power rails</text>')
    parts.append(f'<rect x="0" y="{height - 18}" width="{width}" '
                 f'height="8" fill="#5a5a5a"/>'
                 f'<text x="4" y="{height - 24}" fill="#5a5a5a">'
                 f'ground rails</text>')
    for i, branch in enumerate(branches):
        x = pad + i * col_w
        y = 44
        for name in branch["devices"]:
            role = roles.get(name, {}).get("role", "")
            color = _ROLE_COLORS.get(role, _DEFAULT_COLOR)
            label = html.escape(f"{name} [{role}]" if role else name)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{col_w - 20}" '
                f'height="{box_h}" rx="4" fill="{color}" opacity="0.85"/>'
                f'<text x="{x + 5}" y="{y + 17}" fill="#fff">{label}</text>')
            y += box_h + 6
        if branch.get("forks"):
            parts.append(f'<text x="{x}" y="{y + 12}" fill="#7a4fcc">'
                         f'fork: {html.escape(",".join(branch["forks"]))}'
                         f'</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: dict) -> str:
    out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
           f"<title>cktdetect: {html.escape(report.get('title', ''))}"
           f"</title><style>{_CSS}</style></head><body>"]
    out.append(f"<h1>cktdetect report"
               f"{' — ' + html.escape(report['title']) if report.get('title') else ''}"
               f"</h1>")

    out.append("<h2>Classification</h2>")
    for verdict in report.get("classification", []):
        conf = verdict.get("confidence", 0)
        out.append(
            f"<div class='verdict'><b>{html.escape(verdict['type'])}</b>"
            f"<span class='conf'>{conf:.2f}</span>"
            f"<div class='bar' style='width:{int(conf * 100)}%'></div>"
            f"<ul class='ev'>"
            + "".join(f"<li>{html.escape(e)}</li>"
                      for e in verdict.get("evidence", []))
            + "</ul></div>")

    out.append("<h2>Branch diagram</h2>")
    out.append("<div class='legend'>"
               + "".join(f"<span><i style='background:{c}'></i>"
                         f"{html.escape(r)}</span>"
                         for r, c in _ROLE_COLORS.items()) + "</div>")
    out.append(_svg_branches(report))

    out.append("<h2>Structures</h2><table><tr><th>type</th><th>devices"
               "</th><th>confidence</th></tr>")
    for s in report.get("structures", []):
        devices = s.get("devices") or \
            [s.get("reference", "")] + [o["device"]
                                        for o in s.get("outputs", [])]
        out.append(f"<tr><td>{html.escape(s['type'])}</td>"
                   f"<td>{html.escape(','.join(devices))}</td>"
                   f"<td>{s.get('confidence', '')}</td></tr>")
    out.append("</table>")

    out.append("<h2>Net roles</h2><table><tr><th>net</th><th>role</th>"
               "<th>evidence</th></tr>")
    for net, info in sorted(report.get("net_roles", {}).items()):
        if info["role"] == "signal":
            continue
        out.append(f"<tr><td>{html.escape(net)}</td>"
                   f"<td>{html.escape(info['role'])}</td>"
                   f"<td>{html.escape('; '.join(info['evidence']))}</td></tr>")
    out.append("</table>")

    sub = report.get("subckt_analysis", {})
    if sub:
        out.append("<h2>Subcircuit classification</h2><table>"
                   "<tr><th>subckt</th><th>type</th><th>confidence</th></tr>")
        for name, verdicts in sorted(sub.items()):
            top = verdicts[0] if verdicts else {}
            out.append(f"<tr><td>{html.escape(name)}</td>"
                       f"<td>{html.escape(top.get('type', '?'))}</td>"
                       f"<td>{top.get('confidence', '')}</td></tr>")
        out.append("</table>")

    warnings = report.get("warnings", [])
    if warnings:
        out.append("<h2>Warnings</h2><ul>"
                   + "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
                   + "</ul>")
    out.append("</body></html>")
    return "".join(out)
