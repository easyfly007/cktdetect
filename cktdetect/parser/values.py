"""SPICE numeric values and simple parameter expressions."""

from __future__ import annotations

import ast
import operator
import re

_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "x": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
    "a": 1e-18,
}

# number, optional scale suffix, optional trailing unit letters ("2.0pF")
_VALUE_RE = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(meg|[tgxkmunpfa])?[a-z]*$"
)

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def parse_value(token) -> float | None:
    """Parse a SPICE numeric literal like ``2u``, ``10meg``, ``1.5e-9``.

    Returns None when the token is not a plain number.
    """
    if token is None:
        return None
    match = _VALUE_RE.match(str(token).strip().lower())
    if match is None:
        return None
    value = float(match.group(1))
    if match.group(2):
        value *= _SUFFIX[match.group(2)]
    return value


def safe_eval(expr: str, names: dict) -> float:
    """Evaluate a simple arithmetic expression over known parameter names."""

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in names:
                return float(names[node.id])
            raise ValueError(f"unknown parameter '{node.id}'")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported expression")

    return ev(ast.parse(expr, mode="eval"))


def resolve_value(token, params: dict | None = None) -> float | None:
    """Resolve a token to a float: literal, parameter reference, or expression.

    SPICE scale suffixes are only supported in plain literals, not inside
    arithmetic expressions. Returns None when the token cannot be resolved.
    """
    params = params or {}
    text = str(token).strip().strip("'\"").strip("{}")
    value = parse_value(text)
    if value is not None:
        return value
    numeric = {k: float(v) for k, v in params.items() if isinstance(v, (int, float))}
    if text in numeric:
        return numeric[text]
    try:
        return float(safe_eval(text, numeric))
    except (ValueError, SyntaxError):
        return None
