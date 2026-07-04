from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def classify_file(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return classify(build_context(flat))


def types(name):
    return [v["type"] for v in classify_file(name)]


def test_telescopic_ota():
    verdicts = classify_file("telescopic_ota.sp")
    assert verdicts[0]["type"] == "telescopic_ota"
    assert verdicts[0]["confidence"] >= 0.85
    evidence = " ".join(verdicts[0]["evidence"])
    assert "m3" in evidence and "m4" in evidence
    assert "mirror load" in evidence
    # not folded (cascodes are same polarity), not plain single-stage
    assert "folded_cascode_ota" not in types("telescopic_ota.sp")
    assert "single_stage_ota" not in types("telescopic_ota.sp")


def test_folded_cascode_still_folded():
    assert "telescopic_ota" not in types("folded_cascode_ota.sp")
    assert types("folded_cascode_ota.sp")[0] == "folded_cascode_ota"


def test_strongarm_comparator():
    verdicts = classify_file("strongarm_comparator.sp")
    assert verdicts[0]["type"] == "strongarm_comparator"
    assert verdicts[0]["confidence"] >= 0.9
    evidence = " ".join(verdicts[0]["evidence"])
    assert "clock" in evidence
    assert "m0" in evidence
    # the latch nets sit above the pair outputs, so the static-comparator
    # rule must not fire; nor is this a fully differential OTA
    assert "comparator" not in types("strongarm_comparator.sp")
    assert "fully_differential_ota" not in types("strongarm_comparator.sp")


def test_static_latch_comparator_unchanged():
    assert types("latch_comparator.sp")[0] == "comparator"
    assert "strongarm_comparator" not in types("latch_comparator.sp")


def test_beta_multiplier():
    verdicts = classify_file("beta_multiplier.sp")
    assert verdicts[0]["type"] == "beta_multiplier_bias"
    assert verdicts[0]["confidence"] >= 0.85
    evidence = " ".join(verdicts[0]["evidence"])
    assert "rs" in evidence
    assert "4:1" in evidence


def test_plain_mirror_is_not_beta_multiplier():
    assert "beta_multiplier_bias" not in types("current_mirror.sp")
    assert "beta_multiplier_bias" not in types("cascode_mirror.sp")
    assert "beta_multiplier_bias" not in types("bandgap_core.sp")


def test_fully_differential_ota():
    verdicts = classify_file("fd_ota_cmfb.sp")
    assert verdicts[0]["type"] == "fully_differential_ota"
    assert verdicts[0]["confidence"] >= 0.9
    evidence = " ".join(verdicts[0]["evidence"])
    assert "common-mode feedback" in evidence
    assert "vcm" in evidence


def test_single_ended_otas_not_fully_differential():
    for bench in ("five_t_ota.sp", "two_stage_ota.sp",
                  "folded_cascode_ota.sp", "telescopic_ota.sp",
                  "gilbert_mixer.sp"):
        assert "fully_differential_ota" not in types(bench), bench


def test_existing_classifications_unchanged():
    assert types("five_t_ota.sp")[0] == "single_stage_ota"
    assert types("two_stage_ota.sp")[0] == "two_stage_ota"
    assert types("ldo.sp")[0] == "ldo"
    assert types("lc_vco.sp")[0] == "lc_vco"
    assert types("gilbert_mixer.sp")[0] == "gilbert_mixer"
