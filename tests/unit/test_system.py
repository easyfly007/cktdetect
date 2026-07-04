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


def test_vco_stage_chain():
    report = build_report(BENCH / "vco_stage_chain.sp")
    verdicts = report["classification"]
    assert verdicts[0]["type"] == "vco_stage_chain"
    evidence = " ".join(verdicts[0]["evidence"])
    assert "4 identical inverting stages" in evidence
    assert "'vb'" in evidence


def test_buffer_chain_without_control_net_is_not_a_vco():
    text = """* plain buffer chain: no shared tuning input
.subckt buf_stage vin vout vdd vss
Mn vout vin vss vss nch W=2u L=0.1u
Mp vout vin vdd vdd pch W=4u L=0.1u
.ends
X1 a b vdd 0 buf_stage
X2 b c vdd 0 buf_stage
X3 c d vdd 0 buf_stage
X4 d e vdd 0 buf_stage
Vdd vdd 0 1.2
.end
"""
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as tmp:
        path = P(tmp) / "chain.sp"
        path.write_text(text)
        report = build_report(path)
    assert "vco_stage_chain" not in [v["type"]
                                     for v in report["classification"]]


def test_source_less_subckt_filter_classified_via_ports():
    report = build_report(BENCH / "pll.sp", top="loop_filter")
    assert report["classification"][0]["type"] == "passive_filter_lowpass"
