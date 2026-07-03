from pathlib import Path

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.rails import NetRole, classify_nets

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def roles_for(name, top=None):
    netlist = SpiceParser().parse_file(BENCH / name)
    return classify_nets(flatten(netlist, top=top))


def test_current_mirror_rails():
    roles = roles_for("current_mirror.sp")
    assert roles["vdd"].role is NetRole.POWER
    assert roles["0"].role is NetRole.GROUND
    assert roles["nref"].role is NetRole.SIGNAL
    assert roles["nout"].role is NetRole.SIGNAL


def test_bias_voltage_is_not_a_rail():
    roles = roles_for("two_stage_ota.sp")
    assert roles["vdd"].role is NetRole.POWER
    assert roles["0"].role is NetRole.GROUND
    assert roles["nb"].role is NetRole.SIGNAL  # 0.7V bias, not a rail
    assert roles["tail"].role is NetRole.SIGNAL


def test_bulk_voting_on_nonstandard_names():
    roles = roles_for("bulk_vote.sp")
    assert roles["rail_hi"].role is NetRole.POWER
    assert roles["rail_lo"].role is NetRole.GROUND
    assert roles["in"].role is NetRole.SIGNAL
    assert roles["out1"].role is NetRole.SIGNAL


def test_hierarchical_nets_classified_by_basename():
    roles = roles_for("five_t_ota.sp")
    assert roles["vdd"].role is NetRole.POWER
    assert roles["0"].role is NetRole.GROUND
    assert roles["xota.tail"].role is NetRole.SIGNAL


def test_subckt_port_named_vss():
    roles = roles_for("five_t_ota.sp", top="ota5")
    assert roles["vss"].role is NetRole.GROUND
    assert roles["vdd"].role is NetRole.POWER


def test_every_promotion_has_evidence():
    roles = roles_for("bulk_vote.sp")
    for info in roles.values():
        if info.role is not NetRole.SIGNAL:
            assert info.evidence
