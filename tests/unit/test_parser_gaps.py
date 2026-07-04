import json

import pytest

from cktdetect.cli import build_report
from cktdetect.ir.device import DeviceType
from cktdetect.ir.flatten import flatten
from cktdetect.parser import parse_netlist
from cktdetect.parser.spice import SpiceParser
from cktdetect.profile import load_profile

# ----------------------------------------------------------------------
# .include / .lib expansion


def test_include_expansion(tmp_path):
    (tmp_path / "devices.inc").write_text(
        ".model nm nmos\nM1 d g s 0 nm W=1u L=1u\n")
    main = tmp_path / "main.sp"
    main.write_text("* include test\n.include devices.inc\nR1 d 0 1k\n.end\n")
    netlist = SpiceParser().parse_file(main)
    assert netlist.top.device("m1").dtype is DeviceType.NMOS
    assert netlist.top.device("r1").dtype is DeviceType.RESISTOR
    assert not netlist.warnings


def test_include_quoted_and_nested(tmp_path):
    (tmp_path / "leaf.inc").write_text("Rleaf x 0 2k\n")
    (tmp_path / "mid.inc").write_text(".include 'leaf.inc'\nRmid x y 1k\n")
    main = tmp_path / "main.sp"
    main.write_text('* nested\n.include "mid.inc"\n.end\n')
    netlist = SpiceParser().parse_file(main)
    names = {d.name for d in netlist.top.devices}
    assert names == {"rleaf", "rmid"}


def test_include_missing_warns(tmp_path):
    main = tmp_path / "m.sp"
    main.write_text("* t\n.include nosuch.inc\nR1 a 0 1k\n.end\n")
    netlist = SpiceParser().parse_file(main)
    assert any("not found" in w for w in netlist.warnings)
    assert netlist.top.device("r1")  # parse continues


def test_include_cycle_warns(tmp_path):
    (tmp_path / "a.inc").write_text(".include b.inc\nRa x 0 1k\n")
    (tmp_path / "b.inc").write_text(".include a.inc\nRb x 0 1k\n")
    main = tmp_path / "m.sp"
    main.write_text("* cycle\n.include a.inc\n.end\n")
    netlist = SpiceParser().parse_file(main)
    assert any("cycle" in w for w in netlist.warnings)
    assert {d.name for d in netlist.top.devices} == {"ra", "rb"}


def test_lib_section(tmp_path):
    (tmp_path / "models.lib").write_text(
        ".lib tt\n.model nm nmos\n.endl\n"
        ".lib ff\n.model nm pmos\n.endl\n")
    main = tmp_path / "m.sp"
    main.write_text("* lib\n.lib 'models.lib' tt\n"
                    "M1 d g s 0 nm W=1u L=1u\n.end\n")
    netlist = SpiceParser().parse_file(main)
    assert netlist.top.device("m1").dtype is DeviceType.NMOS


def test_lib_missing_section_warns(tmp_path):
    (tmp_path / "models.lib").write_text(".lib tt\n.model nm nmos\n.endl\n")
    main = tmp_path / "m.sp"
    main.write_text("* lib\n.lib 'models.lib' ss\n.end\n")
    netlist = SpiceParser().parse_file(main)
    assert any("section 'ss' not found" in w for w in netlist.warnings)


# ----------------------------------------------------------------------
# subckt parameters


def test_subckt_param_default_and_override():
    text = """* subckt params
.subckt r2 a b rv=1k
R1 a b rv
.ends
X1 n1 n2 r2
X2 n2 n3 r2 rv=5k
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    assert flat.device("x1.r1").params["value"] == pytest.approx(1e3)
    assert flat.device("x2.r1").params["value"] == pytest.approx(5e3)


def test_subckt_scoped_param_expression():
    text = """* scoped param references an overridable argument
.subckt amp a vdd w=2u
.param lw='w*2'
M1 a a vdd vdd pch W=lw L=1u
.ends
X1 n1 vdd amp w=4u
X2 n2 vdd amp
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    assert flat.device("x1.m1").params["w"] == pytest.approx(8e-6)
    assert flat.device("x2.m1").params["w"] == pytest.approx(4e-6)


def test_instance_m_multiplies_hierarchically():
    text = """* hierarchical m factor
.subckt cell a b
M1 a b 0 0 nch W=1u L=1u M=2
.ends
.subckt block a b
X1 a b cell m=3
.ends
X0 x y block m=2
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    assert flat.device("x0.x1.m1").params["m"] == pytest.approx(12)


# ----------------------------------------------------------------------
# CDL


def test_cdl_netlist(tmp_path):
    path = tmp_path / "cell.cdl"
    path.write_text("""* cdl export
*.PININFO A:I Z:O VDD:B VSS:B
.SUBCKT inv a z vdd vss
MMP z a vdd vdd pch W=2u L=0.1u $X=100 $Y=200
MMN z a vss vss nch W=1u L=0.1u
.ENDS
XI1 n1 n2 vpow 0 / inv
.END
""")
    netlist = parse_netlist(path)  # .cdl extension -> spice frontend
    assert netlist.top.device("xi1").subckt == "inv"
    flat = flatten(netlist)
    mmp = flat.device("xi1.mmp")
    assert mmp.dtype is DeviceType.PMOS
    assert mmp.terminals["s"] == "vpow"
    assert "$x" not in mmp.params  # $-properties stripped


# ----------------------------------------------------------------------
# PDK profile

SKY_NETLIST = """* opaque pdk model names and rail names
Vp vpwr vgnd 1.8
M1 out in vgnd vgnd s8_dev_a W=1u L=0.15u
M2 out in vpwr vpwr s8_dev_b3v3 W=2u L=0.15u
.end
"""


def test_profile_maps_models_and_rails(tmp_path):
    prof_path = tmp_path / "s8.json"
    prof_path.write_text(json.dumps({
        "models": {"s8_dev_a": "nmos", "s8_dev_b*": "pmos"},
        "power_nets": ["vpwr*"],
        "ground_nets": ["vgnd*"],
    }))
    netlist_path = tmp_path / "cell.sp"
    netlist_path.write_text(SKY_NETLIST)

    # without a profile: polarity unknown, rails only via source+bulk
    bare = SpiceParser().parse_string(SKY_NETLIST)
    assert bare.top.device("m1").dtype is DeviceType.MOS
    assert any("polarity" in w for w in bare.warnings)

    report = build_report(netlist_path, pdk_profile=prof_path)
    assert report["flat"]["devices_by_type"] == {
        "vsource": 1, "nmos": 1, "pmos": 1}
    assert report["net_roles"]["vpwr"]["role"] == "power"
    assert report["net_roles"]["vgnd"]["role"] == "ground"
    assert not report["warnings"]


def test_profile_exact_beats_glob(tmp_path):
    prof_path = tmp_path / "p.json"
    prof_path.write_text(json.dumps({
        "models": {"dev*": "nmos", "devp": "pmos"}}))
    profile = load_profile(prof_path)
    assert profile.model_type("devp") == "pmos"
    assert profile.model_type("devn") == "nmos"
    assert profile.model_type("other") is None
