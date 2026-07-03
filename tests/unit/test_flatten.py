from pathlib import Path

import pytest

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def parse(name):
    return SpiceParser().parse_file(BENCH / name)


def test_flatten_hierarchy():
    flat = flatten(parse("five_t_ota.sp"))
    assert len(flat.devices) == 11  # 6 in subckt + 5 top-level

    m1 = flat.device("xota.m1")
    assert m1.terminals["g"] == "inp"        # port -> top net
    assert m1.terminals["s"] == "xota.tail"  # internal net prefixed
    assert m1.terminals["b"] == "0"          # node 0 stays global

    m3 = flat.device("xota.m3")
    assert m3.terminals["s"] == "vdd"
    assert m3.terminals["d"] == "xota.n1"


def test_flatten_named_subckt_as_top():
    flat = flatten(parse("five_t_ota.sp"), top="ota5")
    assert len(flat.devices) == 6
    assert flat.device("m1").terminals["g"] == "vip"
    assert flat.ports == ["vip", "vin", "vout", "ibias", "vdd", "vss"]


def test_recursive_instantiation_rejected():
    text = """* recursive
.subckt loop a b
X1 a b loop
.ends
X0 n1 n2 loop
.end
"""
    with pytest.raises(ValueError, match="recursive"):
        flatten(SpiceParser().parse_string(text))


def test_undefined_subckt_rejected():
    text = """* undefined
X1 a b nosuch
.end
"""
    with pytest.raises(ValueError, match="undefined subckt"):
        flatten(SpiceParser().parse_string(text))


def test_port_count_mismatch_rejected():
    text = """* mismatch
.subckt buf a b
R1 a b 1k
.ends
X1 n1 buf
.end
"""
    with pytest.raises(ValueError, match="ports"):
        flatten(SpiceParser().parse_string(text))
