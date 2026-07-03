from pathlib import Path

import pytest

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.device import DeviceType
from cktdetect.ir.flatten import flatten
from cktdetect.parser import parse_netlist
from cktdetect.parser.spectre import SpectreParser

SPECTRE_OTA = """// five transistor ota in spectre syntax
simulator lang=spectre
global 0
subckt ota5 vip vin vout ibias vdd vss
M1 (n1 vip tail vss) nch w=4u l=0.5u
M2 (vout vin tail vss) nch w=4u l=0.5u
M3 (n1 n1 vdd vdd) pch w=8u l=1u
M4 (vout n1 vdd vdd) pch w=8u l=1u
M5 (tail ibias vss vss) nch w=2u l=2u
M6 (ibias ibias vss vss) nch w=2u l=2u
ends ota5
Xota (inp inn out nbias vdd 0) ota5
Vdd (vdd 0) vsource dc=1.8
Ib (vdd nbias) isource dc=10u
Vip (inp 0) vsource dc=0.9
Vin (inn 0) vsource dc=0.9
CL (out 0) capacitor c=1p
"""


def test_spectre_parse():
    netlist = SpectreParser().parse_string(SPECTRE_OTA)
    assert "ota5" in netlist.subckts
    sub = netlist.subckts["ota5"]
    assert sub.ports == ["vip", "vin", "vout", "ibias", "vdd", "vss"]
    m1 = sub.device("m1")
    assert m1.dtype is DeviceType.NMOS
    assert m1.terminals == {"d": "n1", "g": "vip", "s": "tail", "b": "vss"}
    assert m1.params["w"] == pytest.approx(4e-6)
    cl = netlist.top.device("cl")
    assert cl.dtype is DeviceType.CAPACITOR
    assert cl.params["value"] == pytest.approx(1e-12)
    assert netlist.top.device("vdd").params["dc"] == pytest.approx(1.8)


def test_spectre_classifies_same_as_spice():
    netlist = SpectreParser().parse_string(SPECTRE_OTA)
    flat = flatten(netlist)
    verdicts = classify(build_context(flat))
    assert verdicts[0]["type"] == "single_stage_ota"


def test_spectre_model_statement():
    text = """simulator lang=spectre
model nfet bsim4 type=n
model pfet bsim4 type=p
M1 (d g s 0) nfet w=1u l=0.1u
M2 (d2 g vdd vdd) pfet w=2u l=0.1u
"""
    netlist = SpectreParser().parse_string(text)
    assert netlist.top.device("m1").dtype is DeviceType.NMOS
    assert netlist.top.device("m2").dtype is DeviceType.PMOS


def test_dialect_autodetect(tmp_path):
    spectre_file = tmp_path / "ota.txt"
    spectre_file.write_text(SPECTRE_OTA)
    netlist = parse_netlist(spectre_file)
    assert "ota5" in netlist.subckts  # detected via simulator lang line

    scs = tmp_path / "plain.scs"
    scs.write_text("R1 (a b) resistor r=1k\n")
    netlist = parse_netlist(scs)  # detected via extension
    assert netlist.top.device("r1").dtype is DeviceType.RESISTOR


def test_unknown_master_is_subckt_instance():
    text = """simulator lang=spectre
subckt amp in out
R1 (in out) resistor r=1k
ends amp
X1 (a b) amp
X2 (a b) mystery
"""
    netlist = SpectreParser().parse_string(text)
    assert netlist.top.device("x1").subckt == "amp"
    assert netlist.top.device("x2").dtype is DeviceType.SUBCKT
