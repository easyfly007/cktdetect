"""Supply / ground net classification (DESIGN.md P4, rail step).

Every downstream rule (bias nets, branches, device roles) depends on
knowing the power rails. Classification is evidence-based and
conservative: a net is only promoted from SIGNAL when independent
evidence agrees, and every promotion records why.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from ..ir.circuit import Circuit
from ..ir.device import DeviceType


class NetRole(str, Enum):
    POWER = "power"
    GROUND = "ground"
    BIAS = "bias"  # assigned by the net-role pass, never by rail detection
    SIGNAL = "signal"


@dataclass
class NetInfo:
    role: NetRole = NetRole.SIGNAL
    evidence: list = field(default_factory=list)


_POWER_NAME_RE = re.compile(r"^[ad]?(vdd|vcc|vpwr)")
_GROUND_NAME_RE = re.compile(r"^([ad]?(gnd|vss|vgnd)|vee)")


def classify_nets(circuit: Circuit, profile=None) -> dict:
    """Return {net: NetInfo} with rails identified.

    ``profile`` (PdkProfile) adds user-supplied power/ground net name
    patterns, checked before the built-in heuristics.
    """
    infos = {net: NetInfo() for net in sorted(circuit.nets())}

    bulk_power = Counter()
    bulk_ground = Counter()
    bulk_conns = Counter()
    connections = Counter()
    for dev in circuit.devices:
        for net in dev.terminals.values():
            connections[net] += 1
        bulk = dev.terminals.get("b")
        if bulk is not None and dev.dtype in (DeviceType.PMOS, DeviceType.NMOS):
            bulk_conns[bulk] += 1
            if dev.dtype is DeviceType.PMOS:
                bulk_power[bulk] += 1
            else:
                bulk_ground[bulk] += 1

    def promote(net, role, why):
        infos[net].role = role
        infos[net].evidence.append(why)

    # 1. structural / name evidence (profile patterns take precedence)
    for net in infos:
        base = net.rsplit(".", 1)[-1].rstrip("!")
        profile_role = profile.net_role(base) if profile else None
        if net == "0":
            promote(net, NetRole.GROUND, "node 0")
        elif profile_role == "ground":
            promote(net, NetRole.GROUND, f"pdk profile ground net '{base}'")
        elif profile_role == "power":
            promote(net, NetRole.POWER, f"pdk profile power net '{base}'")
        elif _GROUND_NAME_RE.match(base):
            promote(net, NetRole.GROUND, f"net name '{base}'")
        elif _POWER_NAME_RE.match(base):
            promote(net, NetRole.POWER, f"net name '{base}'")

    # 2. strong bulk evidence: same-polarity bulks dominate the net's
    #    connections (a tail net touched by a couple of bulks stays signal)
    for net, info in infos.items():
        if info.role is not NetRole.SIGNAL:
            continue
        votes_p, votes_g = bulk_power[net], bulk_ground[net]
        if votes_p and votes_g:
            continue  # ambiguous
        votes = votes_p + votes_g
        if votes >= 2 and bulk_conns[net] * 2 >= connections[net]:
            role = NetRole.POWER if votes_p else NetRole.GROUND
            kind = "pmos" if votes_p else "nmos"
            promote(net, role, f"bulk of {votes} {kind} devices")

    # 3. dc source referenced to ground, corroborated by at least one bulk
    #    (a lone dc source is a bias voltage, not a rail)
    for _ in range(2):
        for dev in circuit.devices:
            if dev.dtype is not DeviceType.VSOURCE:
                continue
            dc = dev.params.get("dc")
            if not isinstance(dc, (int, float)) or dc == 0:
                continue
            pos, neg = dev.terminals.get("p"), dev.terminals.get("n")
            if pos is None or neg is None:
                continue
            if infos[neg].role is NetRole.GROUND and \
                    infos[pos].role is NetRole.SIGNAL:
                if dc > 0 and bulk_power[pos]:
                    promote(pos, NetRole.POWER,
                            f"dc source {dev.name}={dc}V above ground, "
                            f"pmos bulk agrees")
                elif dc < 0 and bulk_ground[pos]:
                    promote(pos, NetRole.GROUND,
                            f"dc source {dev.name}={dc}V below ground, "
                            f"nmos bulk agrees")

    return infos
