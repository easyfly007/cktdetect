"""Analysis context shared by all verifiers."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..graph.feedback import find_cross_coupled_pairs
from ..graph.stagegraph import build_stage_edges
from ..ir.circuit import Circuit
from ..ir.device import DeviceType
from ..passes.branches import decompose_branches
from ..passes.devroles import assign_device_roles
from ..passes.families import is_transistor
from ..passes.netroles import classify_net_roles
from ..passes.structures import (apply_structure_roles, find_current_mirrors,
                                 find_differential_pairs)
from ..rf.detect import find_lc_tanks


@dataclass
class Context:
    circuit: Circuit
    infos: dict
    branches: list
    non_dc: list
    roles: dict
    mirrors: list
    pairs: list
    cross_coupled: list
    tanks: list = field(default_factory=list)
    stage_edges: list = field(default_factory=list)

    @property
    def transistors(self) -> list:
        return [d for d in self.circuit.devices if is_transistor(d)]

    def role(self, name: str) -> str | None:
        return self.roles.get(name, {}).get("role")

    def devices_by_role(self, *wanted) -> list:
        return [d for d in self.transistors if self.role(d.name) in wanted]

    def has_type(self, dtype: DeviceType) -> bool:
        return any(d.dtype is dtype for d in self.circuit.devices)


def build_context(flat: Circuit) -> Context:
    infos = classify_net_roles(flat)
    branches, non_dc = decompose_branches(flat, infos)
    mirrors = find_current_mirrors(flat, infos)
    pairs = find_differential_pairs(flat, infos)
    roles = assign_device_roles(flat, infos)
    apply_structure_roles(roles, mirrors, pairs)
    ctx = Context(
        circuit=flat, infos=infos, branches=branches, non_dc=non_dc,
        roles=roles, mirrors=mirrors, pairs=pairs,
        cross_coupled=find_cross_coupled_pairs(flat),
        tanks=find_lc_tanks(flat, infos),
    )
    ctx.stage_edges = build_stage_edges(flat, infos, branches, roles)
    return ctx
