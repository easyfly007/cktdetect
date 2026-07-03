import pytest

from cktdetect.parser.values import parse_value, resolve_value


@pytest.mark.parametrize("token,expected", [
    ("1k", 1e3),
    ("10meg", 1e7),
    ("2u", 2e-6),
    ("1.5n", 1.5e-9),
    ("100", 100.0),
    ("1e-3", 1e-3),
    ("2.0pF", 2e-12),
    ("-0.5m", -5e-4),
    (".5u", 5e-7),
    ("3.3", 3.3),
])
def test_parse_value(token, expected):
    assert parse_value(token) == pytest.approx(expected)


@pytest.mark.parametrize("token", ["abc", "", "u2", "wl", None])
def test_parse_value_rejects(token):
    assert parse_value(token) is None


def test_resolve_param_reference():
    assert resolve_value("wl", {"wl": 5e-6}) == pytest.approx(5e-6)


def test_resolve_expression():
    assert resolve_value("'wl*2'", {"wl": 5e-6}) == pytest.approx(1e-5)
    assert resolve_value("{wl+1e-6}", {"wl": 5e-6}) == pytest.approx(6e-6)


def test_resolve_unknown_returns_none():
    assert resolve_value("nosuch*2", {}) is None
