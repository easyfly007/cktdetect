from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.netroles import classify_net_roles
from cktdetect.passes.rails import NetRole

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def classify_file(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return classify(build_context(flat))


def top_type(name):
    return classify_file(name)[0]["type"]


def test_single_stage_ota():
    verdicts = classify_file("five_t_ota.sp")
    assert verdicts[0]["type"] == "single_stage_ota"
    assert verdicts[0]["confidence"] >= 0.85
    assert not any(v["type"] == "two_stage_ota" for v in verdicts)


def test_two_stage_ota():
    verdicts = classify_file("two_stage_ota.sp")
    assert verdicts[0]["type"] == "two_stage_ota"
    assert verdicts[0]["confidence"] >= 0.9
    assert any("Miller" in e for e in verdicts[0]["evidence"])
    assert not any(v["type"] == "single_stage_ota" for v in verdicts)


def test_folded_cascode_ota():
    verdicts = classify_file("folded_cascode_ota.sp")
    assert verdicts[0]["type"] == "folded_cascode_ota"
    assert verdicts[0]["confidence"] >= 0.85


def test_comparator():
    assert top_type("latch_comparator.sp") == "comparator"


def test_buffer():
    assert top_type("source_follower.sp") == "buffer"


def test_mirror_bias():
    assert top_type("current_mirror.sp") == "current_mirror_bias"
    verdicts = classify_file("cascode_mirror.sp")
    assert verdicts[0]["type"] == "current_mirror_bias"
    assert any("cascode" in e for e in verdicts[0]["evidence"])


def test_unknown_for_out_of_scope_circuits():
    assert top_type("bulk_vote.sp") == "unknown"        # digital inverters
    assert top_type("diffpair_negative.sp") == "unknown"


def test_cascode_bias_gate_net_is_bias():
    flat = flatten(SpiceParser().parse_file(BENCH / "folded_cascode_ota.sp"))
    infos = classify_net_roles(flat)
    assert infos["nbc"].role is NetRole.BIAS   # cascode gates, dc-driven
    assert infos["nbp"].role is NetRole.BIAS   # folding source gates
    assert infos["vip"].role is NetRole.SIGNAL  # diff-pair input


def test_follower_input_stays_signal():
    flat = flatten(SpiceParser().parse_file(BENCH / "source_follower.sp"))
    infos = classify_net_roles(flat)
    assert infos["in"].role is NetRole.SIGNAL


def test_cross_coupled_detection():
    flat = flatten(SpiceParser().parse_file(BENCH / "latch_comparator.sp"))
    ctx = build_context(flat)
    assert len(ctx.cross_coupled) == 1
    assert ctx.cross_coupled[0]["devices"] == ["m3", "m4"]
    assert ctx.cross_coupled[0]["nets"] == ["o1", "o2"]


def test_stage_edges_two_stage():
    flat = flatten(SpiceParser().parse_file(BENCH / "two_stage_ota.sp"))
    ctx = build_context(flat)
    # the second stage m6 must be driven from the input-stage branch
    assert any(e["receiver"] == "m6" and e["kind"] == "dc"
               for e in ctx.stage_edges)
