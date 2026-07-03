from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.rf.detect import find_lc_tanks

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def context_for(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return build_context(flat)


def test_lc_vco():
    ctx = context_for("lc_vco.sp")
    verdicts = classify(ctx)
    assert verdicts[0]["type"] == "lc_vco"
    assert verdicts[0]["confidence"] >= 0.85
    # a resonated cross-coupled pair must not be reported as a comparator
    assert not any(v["type"] == "comparator" for v in verdicts)


def test_differential_tank_detected():
    ctx = context_for("lc_vco.sp")
    styles = {t["style"] for t in ctx.tanks}
    assert "differential" in styles
    diff_tank = next(t for t in ctx.tanks if t["style"] == "differential")
    assert diff_tank["nets"] == ["o1", "o2"]


def test_lna():
    verdicts = classify(context_for("lna.sp"))
    assert verdicts[0]["type"] == "lna"
    assert verdicts[0]["confidence"] >= 0.9
    evidence = " ".join(verdicts[0]["evidence"])
    assert "degeneration ls" in evidence
    assert "matching" in evidence
    assert "cascode" in evidence


def test_gilbert_mixer():
    verdicts = classify(context_for("gilbert_mixer.sp"))
    assert verdicts[0]["type"] == "gilbert_mixer"
    assert verdicts[0]["confidence"] >= 0.85
    evidence = " ".join(verdicts[0]["evidence"])
    assert "m3" in evidence and "m7" in evidence


def test_single_ended_tank():
    flat = flatten(SpiceParser().parse_file(BENCH / "lna.sp"))
    ctx = build_context(flat)
    tanks = find_lc_tanks(flat, ctx.infos)
    assert any(t["style"] == "single_ended" and t["nets"] == ["out"]
               for t in tanks)


def test_amplifiers_unaffected_by_rf_verifiers():
    assert classify(context_for("five_t_ota.sp"))[0]["type"] == \
        "single_stage_ota"
    assert classify(context_for("latch_comparator.sp"))[0]["type"] == \
        "comparator"
