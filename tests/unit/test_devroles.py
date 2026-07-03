from pathlib import Path

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.devroles import assign_device_roles
from cktdetect.passes.netroles import classify_net_roles

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def roles_for(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return assign_device_roles(flat, classify_net_roles(flat))


def test_five_t_ota_roles():
    roles = roles_for("five_t_ota.sp")
    assert roles["xota.m1"]["role"] == "diff_input"
    assert roles["xota.m2"]["role"] == "diff_input"
    assert roles["xota.m3"]["role"] == "diode"
    assert roles["xota.m4"]["role"] == "current_source"  # pmos mirror out
    assert roles["xota.m5"]["role"] == "current_sink"    # tail
    assert roles["xota.m6"]["role"] == "diode"


def test_two_stage_roles():
    roles = roles_for("two_stage_ota.sp")
    assert roles["m1"]["role"] == "diff_input"
    assert roles["m2"]["role"] == "diff_input"
    assert roles["m6"]["role"] == "common_source"  # second gain stage
    assert roles["m5"]["role"] == "current_sink"
    assert roles["m7"]["role"] == "current_sink"


def test_cascode_role():
    roles = roles_for("cascode_mirror.sp")
    assert roles["m1"]["role"] == "diode"
    assert roles["m2"]["role"] == "diode"
    assert roles["m3"]["role"] == "cascode"
    assert roles["m4"]["role"] == "current_sink"


def test_source_follower_role():
    text = """* nmos source follower
Vdd vdd 0 1.8
Vb nb 0 0.7
Vin in 0 1.2
M1 vdd in out 0 nch W=10u L=0.5u
M2 out nb 0 0 nch W=2u L=2u
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    roles = assign_device_roles(flat, classify_net_roles(flat))
    assert roles["m1"]["role"] == "source_follower"
    assert roles["m2"]["role"] == "current_sink"


def test_common_source_roles_in_inverter_chain():
    roles = roles_for("bulk_vote.sp")
    assert all(r["role"] == "common_source" for r in roles.values())
