"""External validation against ALIGN benchmark netlists.

These files come from an independent source (see tests/external/README.md
for provenance, license, and per-file analysis). Expectations marked
"unknown" are honest rejections -- flipping one to a real label is an
improvement, and this test failing on such a flip is the signal to
update the README table alongside.
"""

from pathlib import Path

import pytest

from cktdetect.cli import build_report

ALIGN = Path(__file__).resolve().parents[1] / "external" / "align"

EXPECTED = {
    "five_transistor_ota": "single_stage_ota",
    "telescopic_ota": "telescopic_ota",
    "current_mirror_ota": "single_stage_ota",
    "common_source": "common_source_amplifier",
    "comparator1": "strongarm_comparator",
    "high_speed_comparator": "strongarm_comparator",
    "double_tail_sense_amplifier": "comparator",
    "ring_oscillator": "ring_oscillator",
    "switched_capacitor_filter": "switched_capacitor_circuit",
    "cascode_current_mirror_ota": "single_stage_ota",  # via series
    # normalization + composite-diode (cascoded) mirror detection
    # honest rejections (see README: out of scope / known gaps)
    "buffer": "unknown",
    "VCO_type2_65": "unknown",
}


@pytest.mark.parametrize("stem,expected", sorted(EXPECTED.items()))
def test_align_benchmark(stem, expected):
    report = build_report(ALIGN / f"{stem}.sp", top=stem.lower())
    assert report["classification"][0]["type"] == expected


def test_every_align_file_has_an_expectation():
    stems = {p.stem for p in ALIGN.glob("*.sp")}
    assert stems == set(EXPECTED)


def test_no_misjudgment_on_known_gaps():
    # the known-gap circuit must stay unknown rather than being
    # claimed as something else with low evidence
    report = build_report(ALIGN / "VCO_type2_65.sp", top="vco_type2_65")
    assert report["classification"][0]["type"] == "unknown"


def test_cascoded_mirror_ota_evidence():
    report = build_report(ALIGN / "cascode_current_mirror_ota.sp",
                          top="cascode_current_mirror_ota")
    top = report["classification"][0]
    assert top["type"] == "single_stage_ota"
    mirrors = [s for s in report["structures"]
               if s["type"] == "current_mirror"
               and s.get("variant") == "cascode"]
    assert mirrors, "composite-diode mirrors should be reported"


def test_sc_filter_keeps_embedded_ota_as_secondary():
    report = build_report(ALIGN / "switched_capacitor_filter.sp",
                          top="switched_capacitor_filter")
    kinds = [v["type"] for v in report["classification"]]
    assert kinds[0] == "switched_capacitor_circuit"
    assert "telescopic_ota" in kinds  # the embedded amplifier is real
