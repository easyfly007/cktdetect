import json
import time
from pathlib import Path

from cktdetect.cli import build_report, main
from cktdetect.diffcmp import diff_reports
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.normalize import merge_parallel_mos
from cktdetect.templates import TemplateLibrary, circuit_signature
from cktdetect.viewer import render_html

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"

# same topology as five_t_ota.sp: flat, renamed, one device S/D-swapped
RENAMED_5T = """* renamed flat variant of the 5t ota testbench
VDDX pwr 0 1.8
IBX pwr biasx 10u
MA za ina cm 0 nch W=4u L=0.5u
MB zout inb cm 0 nch W=4u L=0.5u
MC pwr za za pwr pch W=8u L=1u
MD zout za pwr pwr pch W=8u L=1u
ME cm biasx 0 0 nch W=2u L=2u
MF biasx biasx 0 0 nch W=2u L=2u
CX zout 0 1p
VA ina 0 0.9
VB inb 0 0.9
.end
"""


def flat_bench(name):
    netlist = SpiceParser().parse_file(BENCH / name)
    return merge_parallel_mos(flatten(netlist))


def test_signature_invariant_to_names_and_sd_swap():
    a = flat_bench("five_t_ota.sp")
    b = merge_parallel_mos(flatten(SpiceParser().parse_string(RENAMED_5T)))
    assert circuit_signature(a) == circuit_signature(b)
    c = flat_bench("two_stage_ota.sp")
    assert circuit_signature(a) != circuit_signature(c)


def test_template_library(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "classic_5t_ota.sp").write_text(RENAMED_5T)
    lib = TemplateLibrary(tdir)
    assert lib.match(flat_bench("five_t_ota.sp")) == ["classic_5t_ota"]
    assert lib.match(flat_bench("two_stage_ota.sp")) == []


def test_template_verdict_in_report(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "classic_5t_ota.sp").write_text(RENAMED_5T)
    report = build_report(BENCH / "five_t_ota.sp", template_dir=tdir)
    assert report["classification"][0]["type"] == "template:classic_5t_ota"
    assert report["classification"][1]["type"] == "single_stage_ota"


def test_html_report():
    report = build_report(BENCH / "five_t_ota.sp")
    html = render_html(report)
    assert "single_stage_ota" in html
    assert "<svg" in html
    assert "tail_current_source" in html


def test_structure_diff():
    a = build_report(BENCH / "five_t_ota.sp")
    b = build_report(BENCH / "two_stage_ota.sp")
    diff = diff_reports(a, b)
    assert diff["classification"]["a"] == ["single_stage_ota"]
    assert diff["classification"]["b"] == ["two_stage_ota"]
    assert not diff["classification"]["same"]
    assert "differential_pair(pol=n,tailed)" in diff["common_structures"]


def test_subckt_analysis_and_composition():
    report = build_report(BENCH / "five_t_ota.sp")
    assert report["subckt_analysis"]["ota5"][0]["type"] == "single_stage_ota"
    assert report["composition"] == {"ota5": 1}


def test_cli_diff_and_html(tmp_path):
    out = tmp_path / "diff.json"
    page = tmp_path / "report.html"
    rc = main([str(BENCH / "five_t_ota.sp"),
               "--diff", str(BENCH / "ldo.sp"),
               "--html", str(page), "-o", str(out)])
    assert rc == 0
    diff = json.loads(out.read_text())["diff"]
    assert diff["classification"]["b"][0] == "ldo"
    assert "<svg" in page.read_text()


def test_large_hierarchical_netlist_is_fast(tmp_path):
    lines = ["* large hierarchical design",
             ".subckt ota5 vip vin vout ibias vdd vss",
             "M1 n1 vip tail vss nch W=4u L=0.5u",
             "M2 vout vin tail vss nch W=4u L=0.5u",
             "M3 n1 n1 vdd vdd pch W=8u L=1u",
             "M4 vout n1 vdd vdd pch W=8u L=1u",
             "M5 tail ibias vss vss nch W=2u L=2u",
             "M6 ibias ibias vss vss nch W=2u L=2u",
             ".ends",
             "Vdd vdd 0 1.8"]
    for i in range(80):
        lines.append(f"X{i} in{i}p in{i}n out{i} nb{i} vdd 0 ota5")
        lines.append(f"Ib{i} vdd nb{i} 10u")
        lines.append(f"CL{i} out{i} 0 1p")
    lines.append(".end")
    big = tmp_path / "big.sp"
    big.write_text("\n".join(lines) + "\n")

    start = time.monotonic()
    report = build_report(big)
    elapsed = time.monotonic() - start

    assert report["flat"]["device_count"] == 80 * 8 + 1
    assert report["composition"] == {"ota5": 80}
    assert report["subckt_analysis"]["ota5"][0]["type"] == "single_stage_ota"
    assert elapsed < 5.0, f"analysis took {elapsed:.1f}s"
