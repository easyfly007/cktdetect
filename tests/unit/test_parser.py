from pathlib import Path

import pytest

from cktdetect.ir.device import DeviceType
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def parse(name):
    return SpiceParser().parse_file(BENCH / name)


def test_current_mirror_devices():
    netlist = parse("current_mirror.sp")
    top = netlist.top
    assert len(top.devices) == 5

    m1 = top.device("m1")
    assert m1.dtype is DeviceType.NMOS
    assert m1.terminals == {"d": "nref", "g": "nref", "s": "0", "b": "0"}
    assert m1.params["w"] == pytest.approx(2e-6)

    assert top.device("m2").params["m"] == pytest.approx(2)
    rload = top.device("rload")
    assert rload.dtype is DeviceType.RESISTOR
    assert rload.params["value"] == pytest.approx(10e3)
    assert top.device("vdd").params["dc"] == pytest.approx(1.8)
    ibias = top.device("ibias")
    assert ibias.dtype is DeviceType.ISOURCE
    assert ibias.params["dc"] == pytest.approx(10e-6)


def test_title_and_subckt():
    netlist = parse("five_t_ota.sp")
    assert "five transistor" in netlist.title.lower()
    assert "ota5" in netlist.subckts
    sub = netlist.subckts["ota5"]
    assert sub.ports == ["vip", "vin", "vout", "ibias", "vdd", "vss"]
    assert len(sub.devices) == 6
    assert len(netlist.top.devices) == 6  # instance + 4 sources + load cap


def test_param_model_and_continuation():
    netlist = parse("two_stage_ota.sp")
    top = netlist.top
    m1 = top.device("m1")
    assert m1.dtype is DeviceType.NMOS  # via .model nm nmos
    assert m1.params["w"] == pytest.approx(5e-6)  # .param wl=5u
    assert top.device("m3").dtype is DeviceType.PMOS  # via .model pm pmos
    assert top.device("m6").params["w"] == pytest.approx(20e-6)  # continuation
    assert top.device("cc").params["value"] == pytest.approx(2e-12)


def test_model_card_after_device():
    text = """* model card after device
M1 d g s b nm W=1u L=1u
.model nm pmos
.end
"""
    netlist = SpiceParser().parse_string(text)
    assert netlist.top.device("m1").dtype is DeviceType.PMOS


def test_bjt_and_diode():
    text = """* bjt and diode
.model qn npn
Q1 c1 b1 e1 qn
D1 a k dmod
.end
"""
    netlist = SpiceParser().parse_string(text)
    q1 = netlist.top.device("q1")
    assert q1.dtype is DeviceType.NPN
    assert q1.terminals == {"c": "c1", "b": "b1", "e": "e1"}
    assert netlist.top.device("d1").dtype is DeviceType.DIODE


def test_ac_source_has_no_dc():
    netlist = parse("rc_lowpass.sp")
    vin = netlist.top.device("vin")
    assert "dc" not in vin.params
    assert vin.params["spec"] == "ac 1"


def test_unknown_cards_warn_but_do_not_crash():
    text = """* tolerance test
FWEIRD a b vdd 1
.strange card
M1 d g s b nch W=1u L=1u
.end
"""
    netlist = SpiceParser().parse_string(text)
    assert len(netlist.top.devices) == 1
    assert len(netlist.warnings) == 2


def test_unknown_mos_polarity_warns():
    text = """* opaque model name
M1 d g s b xyz123 W=1u L=1u
.end
"""
    netlist = SpiceParser().parse_string(text)
    assert netlist.top.device("m1").dtype is DeviceType.MOS
    assert any("polarity" in w for w in netlist.warnings)
