from pathlib import Path

import pytest

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.devroles import assign_device_roles
from cktdetect.passes.netroles import classify_net_roles
from cktdetect.passes.structures import (apply_structure_roles,
                                         find_current_mirrors,
                                         find_differential_pairs)

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def setup(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    infos = classify_net_roles(flat)
    return flat, infos


def test_simple_mirror():
    flat, infos = setup("current_mirror.sp")
    mirrors = find_current_mirrors(flat, infos)
    assert len(mirrors) == 1
    m = mirrors[0]
    assert m["reference"] == "m1"
    assert m["outputs"] == [
        {"device": "m2", "drain_net": "nout", "ratio": pytest.approx(4.0)}]
    assert m["confidence"] >= 0.9
    assert find_differential_pairs(flat, infos) == []


def test_five_t_structures():
    flat, infos = setup("five_t_ota.sp")
    mirrors = find_current_mirrors(flat, infos)
    assert {(m["reference"], m["outputs"][0]["device"]) for m in mirrors} == {
        ("xota.m3", "xota.m4"),   # pmos load mirror
        ("xota.m6", "xota.m5"),   # nmos bias mirror
    }

    pairs = find_differential_pairs(flat, infos)
    assert len(pairs) == 1
    p = pairs[0]
    assert p["devices"] == ["xota.m1", "xota.m2"]
    assert p["tail_net"] == "xota.tail"
    assert p["tail_source"] == "xota.m5"
    assert set(p["inputs"]) == {"inp", "inn"}
    assert p["confidence"] >= 0.85


def test_structure_roles_overlay():
    flat, infos = setup("five_t_ota.sp")
    mirrors = find_current_mirrors(flat, infos)
    pairs = find_differential_pairs(flat, infos)
    roles = assign_device_roles(flat, infos)
    apply_structure_roles(roles, mirrors, pairs)
    assert roles["xota.m3"]["role"] == "mirror_reference"
    assert roles["xota.m4"]["role"] == "mirror_output"
    # tail wins over mirror-output for m5, both evidences retained
    assert roles["xota.m5"]["role"] == "tail_current_source"
    assert any("mirror" in e for e in roles["xota.m5"]["evidence"])


def test_two_stage_structures():
    flat, infos = setup("two_stage_ota.sp")
    mirrors = find_current_mirrors(flat, infos)
    assert [(m["reference"], m["outputs"][0]["device"]) for m in mirrors] == [
        ("m3", "m4")]
    pairs = find_differential_pairs(flat, infos)
    assert len(pairs) == 1
    assert pairs[0]["devices"] == ["m1", "m2"]
    assert pairs[0]["tail_source"] == "m5"


def test_cascode_mirror_reports_only_true_mirror():
    flat, infos = setup("cascode_mirror.sp")
    mirrors = find_current_mirrors(flat, infos)
    # m1's gate loads sit on a different source net -> not reported
    assert [(m["reference"], m["outputs"][0]["device"]) for m in mirrors] == [
        ("m2", "m4")]
    assert find_differential_pairs(flat, infos) == []


def test_pseudo_pair_rejected():
    flat, infos = setup("diffpair_negative.sp")
    assert find_differential_pairs(flat, infos) == []
    assert find_current_mirrors(flat, infos) == []


def test_passive_circuit_has_no_structures():
    flat, infos = setup("rc_lowpass.sp")
    assert find_current_mirrors(flat, infos) == []
    assert find_differential_pairs(flat, infos) == []
