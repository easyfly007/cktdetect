from pathlib import Path

import pytest

from cktdetect.classify.context import build_context
from cktdetect.classify.engine import classify
from cktdetect.ir.flatten import flatten
from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.netroles import classify_net_roles
from cktdetect.passes.normalize import merge_series_mos
from cktdetect.passes.structures import find_current_mirrors

BENCH = Path(__file__).resolve().parents[1] / "benchmarks"


def parse_top(text):
    return SpiceParser().parse_string(text).top


# ----------------------------------------------------------------------
# series stack normalization


def test_same_gate_series_stack_merges():
    top = parse_top("""* split long-channel device
M1 out g mid b nch W=1u L=1u
M2 mid g 0 b nch W=1u L=1u
.end
""")
    merged = merge_series_mos(top)
    assert len(merged.devices) == 1
    dev = merged.devices[0]
    assert dev.terminals["d"] == "out" and dev.terminals["s"] == "0"
    assert dev.params["l"] == pytest.approx(2e-6)
    assert dev.params["merged_series"] == ["m1", "m2"]


def test_three_segment_stack_merges_to_one():
    top = parse_top("""* triple stack
M1 out g a b nch W=1u L=1u
M2 a g c b nch W=1u L=1u
M3 c g 0 b nch W=1u L=1u
.end
""")
    merged = merge_series_mos(top)
    assert len(merged.devices) == 1
    assert merged.devices[0].params["l"] == pytest.approx(3e-6)


def test_cascode_with_different_gate_not_merged():
    top = parse_top("""* cascode: different gates
M1 out gc mid b nch W=1u L=1u
M2 mid g 0 b nch W=1u L=1u
.end
""")
    assert len(merge_series_mos(top).devices) == 2


def test_mid_net_with_extra_connection_not_merged():
    top = parse_top("""* mid node is observable
M1 out g mid b nch W=1u L=1u
M2 mid g 0 b nch W=1u L=1u
Cload mid 0 1p
.end
""")
    assert len(merge_series_mos(top).devices) == 3


# ----------------------------------------------------------------------
# cascoded current mirror (composite diode)


def setup(name):
    flat = flatten(SpiceParser().parse_file(BENCH / name))
    return flat, classify_net_roles(flat)


def test_cascoded_mirror_detected():
    flat, infos = setup("cascoded_mirror_bias.sp")
    mirrors = find_current_mirrors(flat, infos)
    assert len(mirrors) == 1
    m = mirrors[0]
    assert m["variant"] == "cascode"
    assert m["reference"] == "mb"
    assert m["cascode"] == "mc"
    assert m["gate_net"] == "g1"
    assert m["ref_drain_net"] == "g1"
    out = m["outputs"][0]
    assert out["device"] == "mo"
    assert out["drain_net"] == "nout"  # effective drain through mco
    assert out["ratio"] == pytest.approx(2.0)


def test_cascoded_mirror_classified_as_bias():
    flat, _ = setup("cascoded_mirror_bias.sp")
    verdicts = classify(build_context(flat))
    assert verdicts[0]["type"] == "current_mirror_bias"


def test_simple_mirrors_still_simple_variant():
    flat, infos = setup("current_mirror.sp")
    mirrors = find_current_mirrors(flat, infos)
    assert mirrors[0]["variant"] == "simple"
    assert "cascode" not in mirrors[0]


def test_no_composite_diode_in_ota_benches():
    # cascodes inside amplifiers must not fabricate mirrors
    for bench in ("folded_cascode_ota.sp", "telescopic_ota.sp",
                  "latch_comparator.sp"):
        flat, infos = setup(bench)
        for m in find_current_mirrors(flat, infos):
            assert m["variant"] == "simple", (bench, m)
