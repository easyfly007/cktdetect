from pathlib import Path

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.branches import dc_domains, decompose_branches
from cktdetect.passes.netroles import classify_net_roles

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def branches_for(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    infos = classify_net_roles(flat)
    branches, non_dc = decompose_branches(flat, infos)
    return flat, infos, branches, non_dc


def test_five_t_core_is_one_branch_with_tail_fork():
    _, _, branches, non_dc = branches_for("five_t_ota.sp")
    by_dev = {d: b for b in branches for d in b.devices}

    core = by_dev["xota.m1"]
    assert set(core.devices) == {
        "xota.m1", "xota.m2", "xota.m3", "xota.m4", "xota.m5"}
    assert core.forks == ["xota.tail"]
    assert set(core.rails) == {"0", "vdd"}

    bias = by_dev["ib"]
    assert set(bias.devices) == {"ib", "xota.m6"}
    assert bias.forks == []

    assert non_dc == ["cl"]  # capacitor blocks DC


def test_rail_to_rail_source_is_its_own_branch():
    _, _, branches, _ = branches_for("five_t_ota.sp")
    by_dev = {d: b for b in branches for d in b.devices}
    vdd = by_dev["vdd"]
    assert vdd.devices == ["vdd"]
    assert vdd.internal_nets == []


def test_cascode_mirror_branches():
    _, _, branches, _ = branches_for("cascode_mirror.sp")
    by_dev = {d: b for b in branches for d in b.devices}
    assert set(by_dev["m1"].devices) == {"ib", "m1", "m2"}
    assert set(by_dev["m3"].devices) == {"m3", "m4", "rload"}


def test_dc_domains_cut_by_capacitor():
    text = """* ac coupled stages
V1 a 0 1
R1 a b 1k
C1 b c 1u
R2 c 0 1k
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    infos = classify_net_roles(flat)
    assert dc_domains(flat, infos) == [["a", "b"], ["c"]]
