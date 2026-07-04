from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passive.ladder import r_divider_taps

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def classify_file(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return classify(build_context(flat))


def test_ldo():
    verdicts = classify_file("ldo.sp")
    assert verdicts[0]["type"] == "ldo"
    assert verdicts[0]["confidence"] >= 0.85
    assert any("pass device mp" in e for e in verdicts[0]["evidence"])
    # the closed loop must not be mistaken for an open-loop two-stage OTA
    assert not any(v["type"] == "two_stage_ota" for v in verdicts)


def test_bandgap_core():
    verdicts = classify_file("bandgap_core.sp")
    assert verdicts[0]["type"] == "bandgap_core"
    assert verdicts[0]["confidence"] >= 0.85
    assert any("area ratio 8:1" in e for e in verdicts[0]["evidence"])


def test_lc_lowpass():
    verdicts = classify_file("lc_lowpass_pi.sp")
    assert verdicts[0]["type"] == "passive_filter_lowpass"
    assert any("order 3" in e for e in verdicts[0]["evidence"])


def test_rc_lowpass_now_classified():
    verdicts = classify_file("rc_lowpass.sp")
    assert verdicts[0]["type"] == "passive_filter_lowpass"
    assert any("order 1" in e for e in verdicts[0]["evidence"])


def test_rc_highpass():
    assert classify_file("rc_highpass.sp")[0]["type"] == \
        "passive_filter_highpass"


def test_rlc_bandpass():
    verdicts = classify_file("rlc_bandpass.sp")
    assert verdicts[0]["type"] == "passive_filter_bandpass"
    assert any("order 2" in e for e in verdicts[0]["evidence"])


def test_resistive_divider():
    verdicts = classify_file("r_divider.sp")
    assert verdicts[0]["type"] == "resistive_divider"
    assert any("mid" in e for e in verdicts[0]["evidence"])


def test_bjt_mirror():
    text = """* bjt current mirror
.model qn npn
Vcc vcc 0 5
Ib vcc nref 100u
Q1 nref nref 0 qn
Q2 out nref 0 qn
Rload vcc out 10k
.end
"""
    flat = flatten(SpiceParser().parse_string(text))
    ctx = build_context(flat)
    assert len(ctx.mirrors) == 1
    assert ctx.mirrors[0]["reference"] == "q1"
    assert ctx.mirrors[0]["outputs"][0]["device"] == "q2"
    assert classify(ctx)[0]["type"] == "current_mirror_bias"
    # two undegenerated BJTs are not a bandgap
    assert not any(v["type"] == "bandgap_core" for v in classify(ctx))


def test_r_divider_taps_helper():
    flat = flatten(SpiceParser().parse_file(BENCH / "ldo.sp"))
    ctx = build_context(flat)
    assert r_divider_taps(flat, ctx.infos, "vout") == {"fb"}
