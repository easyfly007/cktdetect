"""CMFB error amplifier vs main amplifier discrimination.

The trap: a CMFB error amp is itself a differential pair, often with a
mirror load -- exactly what the main-amplifier verifiers look for.
Discovered on the MAGICAL multi-stage FD OTAs.
"""

from pathlib import Path

from cktdetect.classify.context import build_context
from cktdetect.cli import build_report
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def test_cmfb_pair_is_flagged_and_ordered_last():
    flat = flatten(SpiceParser().parse_file(BENCH / "fd_ota_cmfb_amp.sp"))
    ctx = build_context(flat)
    assert len(ctx.pairs) == 2
    main, cmfb = ctx.pairs  # sorted: main-amp candidates first
    assert main["devices"] == ["m1", "m2"]
    assert main["cmfb_like"] is False
    assert cmfb["devices"] == ["m6", "m7"]
    assert cmfb["cmfb_like"] is True
    assert any("CMFB error amplifier" in e for e in cmfb["evidence"])


def test_trap_bench_classifies_as_fd_not_single_stage():
    report = build_report(BENCH / "fd_ota_cmfb_amp.sp")
    verdicts = report["classification"]
    assert verdicts[0]["type"] == "fully_differential_ota"
    assert verdicts[0]["confidence"] >= 0.9
    evidence = " ".join(verdicts[0]["evidence"])
    assert "CMFB error amplifier m6,m7 controls the loads" in evidence
    # the CMFB amp (5T OTA shape) must not be claimed as the main amp
    assert not any(v["type"] == "single_stage_ota" for v in verdicts)


def test_ldo_feedback_divider_is_not_cm_sense():
    # fb has resistors to vout and ground: one non-rail neighbor only,
    # so the LDO error-amp pair must stay unflagged
    flat = flatten(SpiceParser().parse_file(BENCH / "ldo.sp"))
    ctx = build_context(flat)
    assert len(ctx.pairs) == 1
    assert ctx.pairs[0]["cmfb_like"] is False


def test_passive_fd_bench_unaffected():
    report = build_report(BENCH / "fd_ota_cmfb.sp")
    assert report["classification"][0]["type"] == "fully_differential_ota"