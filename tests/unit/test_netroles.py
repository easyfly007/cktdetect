from pathlib import Path

from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.netroles import classify_net_roles
from cktdetect.passes.rails import NetRole

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def roles_for(name):
    return classify_net_roles(flatten(SpiceParser().parse_file(BENCH / name)))


def test_diode_driven_nets_are_bias():
    infos = roles_for("five_t_ota.sp")
    assert infos["nbias"].role is NetRole.BIAS      # diode m6
    assert infos["xota.n1"].role is NetRole.BIAS    # diode m3 (mirror gate)
    assert infos["xota.tail"].role is NetRole.SIGNAL
    assert infos["out"].role is NetRole.SIGNAL


def test_dc_driven_input_gate_stays_signal():
    # inp is driven by a dc source but gates a device whose source is the
    # tail (not a rail) -- it is an input, not a bias
    infos = roles_for("five_t_ota.sp")
    assert infos["inp"].role is NetRole.SIGNAL
    assert infos["inn"].role is NetRole.SIGNAL


def test_dc_source_gate_only_net_is_bias():
    infos = roles_for("two_stage_ota.sp")
    assert infos["nb"].role is NetRole.BIAS   # Vb drives gates of m5/m7
    assert infos["n1"].role is NetRole.BIAS   # diode m3
    assert infos["n2"].role is NetRole.SIGNAL
    assert infos["tail"].role is NetRole.SIGNAL


def test_cascode_bias_nets():
    infos = roles_for("cascode_mirror.sp")
    assert infos["n1"].role is NetRole.BIAS
    assert infos["n2"].role is NetRole.BIAS
    assert infos["n3"].role is NetRole.SIGNAL
    assert infos["nout"].role is NetRole.SIGNAL


def test_passive_only_circuit_has_no_bias():
    infos = roles_for("rc_lowpass.sp")
    assert all(i.role is not NetRole.BIAS for i in infos.values())
