"""Differential gain-stage counting on multi-stage FD amplifiers."""

from pathlib import Path

from cktdetect.cli import build_report

TESTS = Path(__file__).resolve().parents[1]
BENCH = TESTS / "benchmarks"
MAGICAL = TESTS / "external" / "magical"
TSMC40 = TESTS.parent / "profiles" / "tsmc40_magical.json"


def top_verdict(path, top=None, profile=None):
    report = build_report(path, top=top, pdk_profile=profile)
    return report["classification"][0]


def test_fd_two_stage_miller_counts_two():
    verdict = top_verdict(MAGICAL / "ota1.sp", "core_test_flow", TSMC40)
    assert verdict["type"] == "fully_differential_ota"
    assert verdict["stages"] == 2
    assert any("2 gain stages" in e for e in verdict["evidence"])


def test_three_stage_telescopic_counts_three():
    verdict = top_verdict(MAGICAL / "Telescopic_Three_stage_flow.sp",
                          "telescopic_three_stage_flow", TSMC40)
    assert verdict["type"] == "telescopic_ota"
    assert verdict["stages"] == 3
    evidence = " ".join(verdict["evidence"])
    assert "3 gain stages" in evidence
    assert "outm,outp" in evidence  # the path reaches the output ports


def test_feedforward_ota_counts_two():
    verdict = top_verdict(MAGICAL / "ota2.sp", "ota_2", TSMC40)
    assert verdict["type"] == "rail_to_rail_input_stage"
    assert verdict["stages"] == 2


def test_single_stage_circuits_stay_at_one():
    for bench in ("fd_ota_cmfb.sp", "fd_ota_cmfb_amp.sp",
                  "telescopic_ota.sp"):
        verdict = top_verdict(BENCH / bench)
        assert verdict["stages"] == 1, bench
        assert not any("gain stages" in e for e in verdict["evidence"])