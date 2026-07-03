import pytest

from cktdetect.parser.spice import SpiceParser
from cktdetect.passes.normalize import merge_parallel_mos


def parse_top(text):
    return SpiceParser().parse_string(text).top


def test_identical_parallel_mos_merge():
    top = parse_top("""* split device
M1a d g s b nch W=1u L=1u
M1b d g s b nch W=1u L=1u
.end
""")
    merged = merge_parallel_mos(top)
    assert len(merged.devices) == 1
    dev = merged.devices[0]
    assert dev.params["m"] == pytest.approx(2)
    assert dev.params["merged_from"] == ["m1a", "m1b"]


def test_swapped_source_drain_still_parallel():
    top = parse_top("""* reversed orientation
M1 n1 g n2 b nch W=1u L=1u
M2 n2 g n1 b nch W=1u L=1u
.end
""")
    assert len(merge_parallel_mos(top).devices) == 1


def test_m_factors_accumulate():
    top = parse_top("""* m factors
M1 d g s b nch W=1u L=1u M=3
M2 d g s b nch W=1u L=1u
.end
""")
    assert merge_parallel_mos(top).devices[0].params["m"] == pytest.approx(4)


def test_different_geometry_not_merged():
    top = parse_top("""* different widths
M1 d g s b nch W=1u L=1u
M2 d g s b nch W=2u L=1u
.end
""")
    assert len(merge_parallel_mos(top).devices) == 2


def test_different_gate_not_merged():
    top = parse_top("""* different gates
M1 d g1 s b nch W=1u L=1u
M2 d g2 s b nch W=1u L=1u
.end
""")
    assert len(merge_parallel_mos(top).devices) == 2


def test_non_mos_untouched():
    top = parse_top("""* passives
R1 a b 1k
R2 a b 1k
.end
""")
    assert len(merge_parallel_mos(top).devices) == 2
