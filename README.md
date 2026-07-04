# cktdetect

Rule-based circuit type detection from SPICE netlists — no neural
networks, no LLMs. Feed it a netlist, get back what the circuit is and
which device plays which role, with evidence for every conclusion.

```console
$ cktdetect ota.sp
{
  "classification": [
    {"type": "single_stage_ota", "confidence": 0.9,
     "evidence": ["differential pair xota.m1,xota.m2 (tail net 'xota.tail')",
                  "current-mirror load (reference xota.m3)",
                  "tail current source xota.m5", ...]}
  ],
  "device_roles": {"xota.m5": {"role": "tail_current_source", ...}, ...},
  ...
}
```

## How it works

Instead of generic subgraph pattern matching, cktdetect reads a circuit
the way an analog designer does (see `DESIGN.md`):

1. find the rails, label every net (power / ground / bias / signal) —
   current mirrors fall out of the bias-net labeling for free;
2. decompose the circuit into DC branches ("legs") between the rails —
   a differential pair is just a fork in a leg;
3. label each device's role from where its gate connects and its
   position in the stack (tail, cascode, diode, pass device, ...);
4. run per-type verifiers (Required / Optional / Forbidden evidence)
   on the tiny branch-level graph.

Precision over recall: when nothing matches, the answer is `unknown`,
never a guess.

## Supported circuit types

OTA (single-stage, two-stage Miller, folded cascode, telescopic,
fully differential with CMFB), comparators (static latch and StrongARM
dynamic), buffer, current-mirror and beta-multiplier bias networks,
LDO, bandgap core, LC VCO, LNA, Gilbert mixer, passive filters
(RC/LC low/high/bandpass) and resistive dividers.

## Usage

```console
cktdetect NETLIST [--top SUBCKT] [--dialect auto|spice|spectre]
          [--templates DIR] [--html report.html]
          [--diff OTHER_NETLIST] [-o report.json]
```

- **Dialects**: generic SPICE (standard / ngspice / HSPICE core) and
  Spectre; auto-detected by content and file extension.
- **Hierarchy**: `.subckt` designs are classified bottom-up; the report
  includes per-subckt classification and an instance composition table.
- **Templates** (`--templates`): drop labeled reference netlists into a
  directory — anything graph-isomorphic (name- and S/D-independent) is
  labeled without writing code.
- **Viewer** (`--html`): self-contained HTML report with a color-coded
  branch/role diagram.
- **Diff** (`--diff`): structure-level comparison of two netlists —
  classifications, shared structures, and what each side has that the
  other lacks.

## Development

```console
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/python -m pytest
```

Every recognition rule ships with positive *and* negative benchmark
netlists under `tests/benchmarks/`. Design rationale, pipeline stages,
and milestone history live in `DESIGN.md`.
