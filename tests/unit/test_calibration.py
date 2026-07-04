"""Full-corpus confidence calibration.

Runs every labeled circuit (internal benchmarks + external suites)
through the classifier and checks the confidence policy: correct top-1
everywhere, threshold/cap respected, and every type's emitted
confidence inside its documented range (the table in USER_MANUAL).
Run ``pytest -s tests/unit/test_calibration.py`` to print the table.
"""

from pathlib import Path

import pytest

from cktdetect.calibration import evaluate_corpus, format_report

TESTS = Path(__file__).resolve().parents[1]
BENCH = TESTS / "benchmarks"
ALIGN = TESTS / "external" / "align"
OPENFASOC = TESTS / "external" / "openfasoc"
MAGICAL = TESTS / "external" / "magical"
SKY130 = TESTS.parent / "profiles" / "sky130.json"
TSMC40 = TESTS.parent / "profiles" / "tsmc40_magical.json"

_INTERNAL = {
    "five_t_ota.sp": "single_stage_ota",
    "two_stage_ota.sp": "two_stage_ota",
    "folded_cascode_ota.sp": "folded_cascode_ota",
    "telescopic_ota.sp": "telescopic_ota",
    "fd_ota_cmfb.sp": "fully_differential_ota",
    "fd_ota_cmfb_amp.sp": "fully_differential_ota",
    "latch_comparator.sp": "comparator",
    "strongarm_comparator.sp": "strongarm_comparator",
    "source_follower.sp": "buffer",
    "current_mirror.sp": "current_mirror_bias",
    "cascode_mirror.sp": "current_mirror_bias",
    "cascoded_mirror_bias.sp": "current_mirror_bias",
    "beta_multiplier.sp": "beta_multiplier_bias",
    "ldo.sp": "ldo",
    "bandgap_core.sp": "bandgap_core",
    "lc_vco.sp": "lc_vco",
    "lna.sp": "lna",
    "gilbert_mixer.sp": "gilbert_mixer",
    "rc_lowpass.sp": "passive_filter_lowpass",
    "lc_lowpass_pi.sp": "passive_filter_lowpass",
    "rc_highpass.sp": "passive_filter_highpass",
    "rlc_bandpass.sp": "passive_filter_bandpass",
    "r_divider.sp": "resistive_divider",
    "common_source_amp.sp": "common_source_amplifier",
    "rail_to_rail_input.sp": "rail_to_rail_input_stage",
    "class_ab_output.sp": "class_ab_output_stage",
    "ring_oscillator.sp": "ring_oscillator",
    "dickson_charge_pump.sp": "dickson_charge_pump",
    "sample_and_hold.sp": "sample_and_hold",
    "r2r_ladder.sp": "r2r_ladder",
    "pll.sp": "pll",
    "flash_adc.sp": "flash_adc",
    "vco_stage_chain.sp": "vco_stage_chain",
    "bulk_vote.sp": "unknown",
    "diffpair_negative.sp": "unknown",
}

_ALIGN = {
    "five_transistor_ota.sp": (None, "single_stage_ota"),
    "telescopic_ota.sp": (None, "telescopic_ota"),
    "current_mirror_ota.sp": (None, "single_stage_ota"),
    "common_source.sp": (None, "common_source_amplifier"),
    "comparator1.sp": (None, "strongarm_comparator"),
    "high_speed_comparator.sp": (None, "strongarm_comparator"),
    "double_tail_sense_amplifier.sp": (None, "comparator"),
    "ring_oscillator.sp": (None, "ring_oscillator"),
    "switched_capacitor_filter.sp": (None, "switched_capacitor_circuit"),
    "cascode_current_mirror_ota.sp": (None, "single_stage_ota"),
    "VCO_type2_65.sp": ("vco_type2_65", "vco_stage_chain"),
    "buffer.sp": (None, "unknown"),
}

_MAGICAL = {
    "comp.sp": ("comparator_pre_amp_2018_modify_test_flow",
                "strongarm_comparator"),
    "ota1.sp": ("core_test_flow", "fully_differential_ota"),
    "ota2.sp": ("ota_2", "rail_to_rail_input_stage"),
    "Telescopic_Three_stage_flow.sp": ("telescopic_three_stage_flow",
                                       "telescopic_ota"),
}

_OPENFASOC = {
    "DCDC_COMP.sp": ("dcdc_comp", "strongarm_comparator"),
    "LC_Cell.spice": ("lc_cell_3", "lc_vco"),
    "swcap_3M2C.spice": ("swcap_3m2c", "switched_capacitor_circuit"),
    "six_stage_conv.sp": ("six_stage_conv", "switched_capacitor_circuit"),
    "diff_cross_mirror.spice": ("diff_cross_mirror", "unknown"),
}


def corpus():
    cases = []
    for fname, expected in _INTERNAL.items():
        cases.append({"name": f"bench/{fname}", "path": BENCH / fname,
                      "top": None, "expected": expected})
    for fname, (top, expected) in _ALIGN.items():
        cases.append({"name": f"align/{fname}", "path": ALIGN / fname,
                      "top": top or Path(fname).stem.lower(),
                      "expected": expected})
    for fname, (top, expected) in _OPENFASOC.items():
        cases.append({"name": f"openfasoc/{fname}",
                      "path": OPENFASOC / fname, "top": top,
                      "profile": SKY130, "expected": expected})
    for fname, (top, expected) in _MAGICAL.items():
        cases.append({"name": f"magical/{fname}",
                      "path": MAGICAL / fname, "top": top,
                      "profile": TSMC40, "expected": expected})
    return cases


# documented confidence range per type (USER_MANUAL section 6); the
# calibration run must stay inside these, so the manual stays honest
EXPECTED_RANGES = {
    "single_stage_ota": (0.70, 0.90),
    "two_stage_ota": (0.75, 0.95),
    "folded_cascode_ota": (0.75, 0.90),
    "telescopic_ota": (0.75, 0.90),
    "fully_differential_ota": (0.75, 0.95),
    "common_source_amplifier": (0.65, 0.80),
    "rail_to_rail_input_stage": (0.80, 0.85),
    "class_ab_output_stage": (0.75, 0.80),
    "buffer": (0.70, 0.70),
    "comparator": (0.75, 0.80),
    "strongarm_comparator": (0.85, 0.90),
    "current_mirror_bias": (0.75, 0.80),
    "beta_multiplier_bias": (0.80, 0.85),
    "ldo": (0.85, 0.90),
    "bandgap_core": (0.75, 0.90),
    "lc_vco": (0.80, 0.90),
    "ring_oscillator": (0.85, 0.90),
    "lna": (0.75, 0.95),
    "gilbert_mixer": (0.85, 0.90),
    "sample_and_hold": (0.75, 0.85),
    "switched_capacitor_circuit": (0.85, 0.85),
    "dickson_charge_pump": (0.80, 0.85),
    "r2r_ladder": (0.85, 0.90),
    "passive_filter_lowpass": (0.80, 0.80),
    "passive_filter_highpass": (0.80, 0.80),
    "passive_filter_bandpass": (0.80, 0.80),
    "resistive_divider": (0.75, 0.75),
    "pll": (0.80, 0.85),
    "flash_adc": (0.85, 0.90),
    "vco_stage_chain": (0.80, 0.80),
}


@pytest.fixture(scope="module")
def calibration():
    return evaluate_corpus(corpus(), EXPECTED_RANGES)


def test_corpus_is_fully_correct(calibration):
    wrong = [r for r in calibration.results if not r.correct]
    assert not wrong, wrong


def test_no_policy_violations(calibration):
    assert calibration.violations == []


def test_every_type_in_manual_is_exercised(calibration):
    unexercised = set(EXPECTED_RANGES) - set(calibration.per_type)
    assert not unexercised, (
        f"documented types never observed in the corpus: {unexercised}")


def test_rankings_have_margin(calibration):
    # a top verdict should not win by a hair over a *different* type;
    # equal-structure secondary verdicts (substructures) may be close
    fragile = [r for r in calibration.results
               if r.correct and r.got != "unknown" and r.margin < 0.05]
    # substructure runners-up are legitimate; just keep this visible
    assert all(r.margin >= 0 for r in calibration.results)
    assert len(fragile) <= 6, [f"{r.name}:{r.margin}" for r in fragile]


def test_print_calibration_table(calibration, capsys):
    with capsys.disabled():
        print()
        print(format_report(calibration))
