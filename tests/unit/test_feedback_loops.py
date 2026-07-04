from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def loops_for(name):
    ctx = build_context(flatten(SpiceParser().parse_file(BENCH / name)))
    return ctx.feedback_loops


def test_ldo_regulation_loop_is_negative():
    loops = loops_for("ldo.sp")
    reg = [l for l in loops
           if "vout" in l["nets"] and "fb" in l["nets"] and not l["ac"]]
    assert reg, "the regulation loop must be found"
    assert all(l["polarity"] == "negative" for l in reg)
    devices = set(reg[0]["devices"])
    assert "mp" in devices and "r1" in devices


def test_ldo_evidence_confirms_polarity():
    from cktdetect.cli import build_report
    report = build_report(BENCH / "ldo.sp")
    top = report["classification"][0]
    assert top["type"] == "ldo"
    evidence = " ".join(top["evidence"])
    assert "negative dc feedback" in evidence
    assert "WARNING" not in evidence


def test_latch_regeneration_is_positive():
    loops = loops_for("latch_comparator.sp")
    two_cycles = [l for l in loops if set(l["nets"]) == {"o1", "o2"}]
    assert two_cycles
    assert all(l["polarity"] == "positive" for l in two_cycles)


def test_miller_compensation_is_local_negative_ac_loop():
    loops = loops_for("two_stage_ota.sp")
    miller = [l for l in loops
              if "cc" in l["devices"] and "m6" in l["devices"]]
    assert miller
    assert miller[0]["polarity"] == "negative"
    assert miller[0]["ac"] is True


def test_open_loop_ota_has_no_dc_loop():
    loops = loops_for("five_t_ota.sp")
    assert all(l["ac"] for l in loops) or not loops


def test_miswired_positive_regulation_loop_is_flagged():
    # feedback into the non-mirror input makes the loop positive; the
    # ldo verdict must carry the warning instead of silently passing
    text = (BENCH / "ldo.sp").read_text()
    swapped = text.replace("M1 n1 fb tail 0 nch W=4u L=0.5u",
                           "M1 n1 vref tail 0 nch W=4u L=0.5u") \
                  .replace("M2 na vref tail 0 nch W=4u L=0.5u",
                           "M2 na fb tail 0 nch W=4u L=0.5u")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ldo_miswired.sp"
        path.write_text(swapped)
        from cktdetect.cli import build_report
        report = build_report(path)
    top = report["classification"][0]
    assert top["type"] == "ldo"
    evidence = " ".join(top["evidence"])
    assert "positive dc feedback" in evidence
    assert "WARNING" in evidence