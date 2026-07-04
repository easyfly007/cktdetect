from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def context_for(name):
    return build_context(flatten(SpiceParser().parse_file(BENCH / name)))


def classify_file(name):
    return classify(context_for(name))


def types(name):
    return [v["type"] for v in classify_file(name)]


def test_common_source_amplifier():
    verdicts = classify_file("common_source_amp.sp")
    assert verdicts[0]["type"] == "common_source_amplifier"
    assert verdicts[0]["confidence"] >= 0.75
    evidence = " ".join(verdicts[0]["evidence"])
    assert "m1" in evidence and "current-source load m2" in evidence


def test_common_source_not_on_other_benches():
    for bench in ("lna.sp", "source_follower.sp", "bulk_vote.sp",
                  "sample_and_hold.sp", "beta_multiplier.sp"):
        assert "common_source_amplifier" not in types(bench), bench


def test_rail_to_rail_input_stage():
    verdicts = classify_file("rail_to_rail_input.sp")
    assert verdicts[0]["type"] == "rail_to_rail_input_stage"
    assert verdicts[0]["confidence"] >= 0.8
    # the mixer's two switching pairs share LO inputs but same polarity
    assert "rail_to_rail_input_stage" not in types("gilbert_mixer.sp")


def test_class_ab_output_stage():
    verdicts = classify_file("class_ab_output.sp")
    assert verdicts[0]["type"] == "class_ab_output_stage"
    evidence = " ".join(verdicts[0]["evidence"])
    assert "mp" in evidence and "mn" in evidence
    # inverter chain shares one gate net per stage: stays out of scope
    assert "class_ab_output_stage" not in types("bulk_vote.sp")


def test_ring_oscillator():
    verdicts = classify_file("ring_oscillator.sp")
    assert verdicts[0]["type"] == "ring_oscillator"
    assert verdicts[0]["confidence"] >= 0.85
    assert any("3 inverting stages" in e for e in verdicts[0]["evidence"])


def test_inverter_chain_is_not_a_ring():
    ctx = context_for("bulk_vote.sp")
    assert len(ctx.inverters) == 2
    assert ctx.inverter_rings == []
    assert types("bulk_vote.sp") == ["unknown"]


def test_dickson_charge_pump():
    verdicts = classify_file("dickson_charge_pump.sp")
    assert verdicts[0]["type"] == "dickson_charge_pump"
    assert verdicts[0]["confidence"] >= 0.8
    evidence = " ".join(verdicts[0]["evidence"])
    assert "4 diode-connected" in evidence
    assert "clk1" in evidence and "clk2" in evidence
    # a plain mirror's diode is not a pump chain
    assert "dickson_charge_pump" not in types("current_mirror.sp")
    assert "dickson_charge_pump" not in types("cascode_mirror.sp")


def test_sample_and_hold():
    verdicts = classify_file("sample_and_hold.sp")
    assert verdicts[0]["type"] == "sample_and_hold"
    assert verdicts[0]["confidence"] >= 0.8
    evidence = " ".join(verdicts[0]["evidence"])
    assert "ms" in evidence and "ch" in evidence and "mb" in evidence
    # strongarm precharge switches must not read as sample-and-hold
    assert "sample_and_hold" not in types("strongarm_comparator.sp")


def test_r2r_ladder():
    verdicts = classify_file("r2r_ladder.sp")
    assert verdicts[0]["type"] == "r2r_ladder"
    assert verdicts[0]["confidence"] >= 0.85
    assert any("terminator rt" in e for e in verdicts[0]["evidence"])
    # a plain 2-resistor divider is not a ladder
    assert "r2r_ladder" not in types("r_divider.sp")
    assert "r2r_ladder" not in types("rc_lowpass.sp")


def test_prior_classifications_unchanged():
    expectations = {
        "five_t_ota.sp": "single_stage_ota",
        "two_stage_ota.sp": "two_stage_ota",
        "folded_cascode_ota.sp": "folded_cascode_ota",
        "telescopic_ota.sp": "telescopic_ota",
        "fd_ota_cmfb.sp": "fully_differential_ota",
        "latch_comparator.sp": "comparator",
        "strongarm_comparator.sp": "strongarm_comparator",
        "source_follower.sp": "buffer",
        "current_mirror.sp": "current_mirror_bias",
        "beta_multiplier.sp": "beta_multiplier_bias",
        "ldo.sp": "ldo",
        "bandgap_core.sp": "bandgap_core",
        "lc_vco.sp": "lc_vco",
        "lna.sp": "lna",
        "gilbert_mixer.sp": "gilbert_mixer",
        "rc_lowpass.sp": "passive_filter_lowpass",
        "r_divider.sp": "resistive_divider",
    }
    for bench, expected in expectations.items():
        assert types(bench)[0] == expected, bench
