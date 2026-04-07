"""Domain model: slug derivation, file_id stripping, routability, API parsing."""

from __future__ import annotations

import pytest

from mikrotik_proxy_manager.models import MikrotikProxyRule


def _make(**overrides) -> MikrotikProxyRule:
    base = {
        "id": "*1",
        "dst-host": "app.foo.com",
        "dst-address": "10.0.0.10",
        "dst-port": "80",
    }
    base.update(overrides)
    return MikrotikProxyRule.from_api(base)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("hgg.akmalov.com", "hgg_akmalov_com"),
        ("foo.bar", "foo_bar"),
        ("my-app.example.com", "my_app_example_com"),
        ("a.b.c.d", "a_b_c_d"),
    ],
)
def test_slug_full_domain(host: str, expected: str) -> None:
    assert _make(**{"dst-host": host}).slug == expected


def test_slug_collision_avoidance() -> None:
    """#1: hosts with the same leading label must NOT collide."""
    assert _make(**{"dst-host": "app.foo.com"}).slug != _make(**{"dst-host": "app.foo.net"}).slug


@pytest.mark.parametrize(
    "host",
    ["", "nodot", ".leadingdot.com", "bad host.com", "with/slash.com", "host_under.com"],
)
def test_slug_invalid_returns_none(host: str) -> None:
    assert _make(**{"dst-host": host}).slug is None


def test_file_id_strips_leading_star() -> None:
    assert _make(id="*1A").file_id == "1A"


def test_file_id_without_star_passthrough() -> None:
    assert _make(id="42").file_id == "42"


def test_disabled_string_coerced_to_bool() -> None:
    assert _make(disabled="true").disabled is True
    assert _make(disabled="false").disabled is False


def test_is_routable_happy_path() -> None:
    assert _make().is_routable() is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"dst-host": ""},
        {"dst-port": ""},
        {"dst-address": ""},
        {"disabled": "true"},
        {"dst-host": "nodot"},
    ],
)
def test_is_routable_negative(overrides: dict) -> None:
    assert _make(**overrides).is_routable() is False


def test_extra_fields_ignored() -> None:
    """RouterOS may add fields over time; we shouldn't crash on them."""
    rule = MikrotikProxyRule.from_api(
        {
            "id": "*1",
            "dst-host": "a.b.com",
            "dst-address": "1.1.1.1",
            "dst-port": "80",
            "comment": "whatever",
            "redirect-to": "ignored",
        }
    )
    assert rule.dst_host == "a.b.com"
