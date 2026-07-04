"""Confidence calibration harness.

Rule-based confidences are hand-assigned weights; this module grounds
them empirically against the labeled corpus (internal benchmarks plus
external third-party suites). For every case it records the top verdict,
its confidence, and the margin to the runner-up, then aggregates
per-type ranges and policy violations.

Confidence policy (see USER_MANUAL "置信度语义"):
- < 0.60          rejected (never reported as the answer)
- 0.60 - 0.74     Required structure present, little optional evidence
- 0.75 - 0.89     Required plus most optional evidence
- 0.90 - 0.95     full evidence chain; 0.95 is the cap for rule verdicts
- 0.97            reserved for template graph-isomorphism matches
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cli import build_report

THRESHOLD = 0.6
RULE_CAP = 0.95
TEMPLATE_CONFIDENCE = 0.97


@dataclass
class CaseResult:
    name: str
    expected: str
    got: str
    confidence: float
    margin: float  # top-1 minus top-2 confidence (1.0 when unrivaled)
    correct: bool


@dataclass
class CalibrationReport:
    results: list = field(default_factory=list)
    per_type: dict = field(default_factory=dict)  # type -> stats dict
    violations: list = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.correct for r in self.results) / len(self.results)


def evaluate_case(case: dict) -> CaseResult:
    report = build_report(case["path"], top=case.get("top"),
                          pdk_profile=case.get("profile"))
    verdicts = report["classification"]
    top = verdicts[0]
    # margin compares within one scope: system verdicts rank above
    # block verdicts by design, not by confidence
    rival = next((v for v in verdicts[1:]
                  if v.get("scope", "block") == top.get("scope", "block")),
                 None)
    margin = top["confidence"] - rival["confidence"] if rival else 1.0
    return CaseResult(
        name=case["name"],
        expected=case["expected"],
        got=top["type"],
        confidence=top["confidence"],
        margin=round(margin, 3),
        correct=top["type"] == case["expected"],
    )


def evaluate_corpus(cases: list, expected_ranges: dict | None = None
                    ) -> CalibrationReport:
    report = CalibrationReport()
    for case in cases:
        result = evaluate_case(case)
        report.results.append(result)

        if not result.correct:
            report.violations.append(
                f"{result.name}: expected {result.expected}, "
                f"got {result.got} ({result.confidence})")
            continue
        if result.got == "unknown":
            continue

        if result.confidence < THRESHOLD:
            report.violations.append(
                f"{result.name}: accepted verdict below threshold "
                f"({result.confidence})")
        cap = (TEMPLATE_CONFIDENCE if result.got.startswith("template:")
               else RULE_CAP)
        if result.confidence > cap:
            report.violations.append(
                f"{result.name}: confidence {result.confidence} exceeds "
                f"the {cap} cap")
        if expected_ranges is not None:
            bounds = expected_ranges.get(result.got)
            if bounds is None:
                report.violations.append(
                    f"{result.name}: type '{result.got}' has no "
                    f"documented confidence range")
            else:
                low, high = bounds
                if not low <= result.confidence <= high:
                    report.violations.append(
                        f"{result.name}: {result.got} confidence "
                        f"{result.confidence} outside documented "
                        f"[{low}, {high}]")

        stats = report.per_type.setdefault(result.got, {
            "count": 0, "min_confidence": 1.0, "max_confidence": 0.0,
            "min_margin": 1.0,
        })
        stats["count"] += 1
        stats["min_confidence"] = min(stats["min_confidence"],
                                      result.confidence)
        stats["max_confidence"] = max(stats["max_confidence"],
                                      result.confidence)
        stats["min_margin"] = min(stats["min_margin"], result.margin)
    return report


def format_report(report: CalibrationReport) -> str:
    lines = [f"corpus: {len(report.results)} circuits, "
             f"accuracy {report.accuracy:.0%}",
             f"{'type':32s} {'n':>2s} {'conf range':>12s} {'min margin':>10s}"]
    for kind in sorted(report.per_type):
        stats = report.per_type[kind]
        lines.append(
            f"{kind:32s} {stats['count']:2d} "
            f"{stats['min_confidence']:.2f}-{stats['max_confidence']:.2f}"
            f"{'':>4s} {stats['min_margin']:10.2f}")
    if report.violations:
        lines.append("violations:")
        lines.extend(f"  {v}" for v in report.violations)
    return "\n".join(lines)
