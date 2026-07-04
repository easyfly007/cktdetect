"""Differential gain-stage counting (multi-stage FD OTA granularity).

With the main input pair correctly located (CMFB pairs set aside), the
gain stages of a differential amplifier are counted by walking the
differential signal path: each stage is a pair of same-polarity gain
devices whose gates sit on the previous stage's differential net pair
and whose (cascode-extended) drains form the next one. Load and CMFB
devices never qualify -- their gates are not on the differential path.
"""

from __future__ import annotations

from collections import defaultdict

from ..passes.families import control_net, polarity, source_net
from ..passes.structures import _effective_drain

_GAIN_ROLES = ("common_source", "amplifier", "diff_input")
_MAX_STAGES = 5


def differential_stage_chain(ctx, pair) -> list:
    """Return [{devices, nets, kind}] from the input pair to the last
    differential stage it drives."""
    by_source = defaultdict(list)
    for dev in ctx.transistors:
        by_source[source_net(dev)].append(dev)

    def effective(dev):
        return _effective_drain(dev, by_source)

    dev_a = ctx.circuit.device(pair["devices"][0])
    dev_b = ctx.circuit.device(pair["devices"][1])
    current = (effective(dev_a), effective(dev_b))
    chain = [{"devices": list(pair["devices"]), "nets": list(current),
              "kind": "input pair"}]
    used = set(pair["devices"])

    gain_devices = [d for d in ctx.transistors
                    if ctx.role(d.name) in _GAIN_ROLES
                    and d.name not in used]

    while len(chain) < _MAX_STAGES:
        side_a = sorted((d for d in gain_devices
                         if control_net(d) == current[0]
                         and d.name not in used),
                        key=lambda d: d.name)
        side_b = sorted((d for d in gain_devices
                         if control_net(d) == current[1]
                         and d.name not in used),
                        key=lambda d: d.name)
        step = next(((a, b) for a in side_a for b in side_b
                     if polarity(a) == polarity(b)
                     and polarity(a) is not None
                     and a.model == b.model), None)
        if step is None:
            break
        stage_a, stage_b = step
        nets = (effective(stage_a), effective(stage_b))
        if nets[0] == nets[1] or set(nets) == set(current):
            break  # merged or no progress: not a differential stage
        used.update((stage_a.name, stage_b.name))
        chain.append({"devices": [stage_a.name, stage_b.name],
                      "nets": list(nets), "kind": "gain stage"})
        current = nets
    return chain


def attach_stage_chain(ctx, pair, verdict):
    """Add a ``stages`` field and, for multi-stage paths, evidence."""
    chain = differential_stage_chain(ctx, pair)
    verdict["stages"] = len(chain)
    if len(chain) > 1:
        hops = " -> ".join(f"({','.join(s['devices'])})" for s in chain)
        verdict["evidence"].append(
            f"differential signal path {hops} ends at "
            f"{','.join(chain[-1]['nets'])}: {len(chain)} gain stages")
    return verdict
