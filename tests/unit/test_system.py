from pathlib import Path

from cktdetect.cli import build_report

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def test_pll():
    report = build_report(BENCH / "pll.sp")
    verdicts = report["classification"]
    assert verdicts[0]["type"] == "pll"
    assert verdicts[0]["confidence"] >= 0.8
    evidence = " ".join(verdicts[0]["evidence"])
    assert "xosc" in evidence and "xpd" in evidence and "xlf" in evidence
    assert "'vctl'" in evidence  # tuning net identified
    assert "reference input 'ref'" in evidence
    # the flattened ring is still visible as a block-level verdict
    assert "ring_oscillator" in [v["type"] for v in verdicts]


def test_pll_subckt_analysis():
    report = build_report(BENCH / "pll.sp")
    sub = report["subckt_analysis"]
    assert sub["ring_osc"][0]["type"] == "ring_oscillator"
    assert sub["loop_filter"][0]["type"] == "passive_filter_lowpass"


def test_flash_adc():
    report = build_report(BENCH / "flash_adc.sp")
    verdicts = report["classification"]
    assert verdicts[0]["type"] == "flash_adc"
    assert verdicts[0]["confidence"] >= 0.85
    evidence = " ".join(verdicts[0]["evidence"])
    assert "3 comparator instances" in evidence
    assert "every comparator has its own ladder tap" in evidence
    assert report["subckt_analysis"]["comp"][0]["type"] == \
        "strongarm_comparator"


def test_hierarchical_ota_gets_no_system_verdict():
    report = build_report(BENCH / "five_t_ota.sp")
    assert report["classification"][0]["type"] == "single_stage_ota"
    assert "pll" not in [v["type"] for v in report["classification"]]
    assert "flash_adc" not in [v["type"] for v in report["classification"]]


def test_source_less_subckt_filter_classified_via_ports():
    report = build_report(BENCH / "pll.sp", top="loop_filter")
    assert report["classification"][0]["type"] == "passive_filter_lowpass"
