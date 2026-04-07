"""#2/#3 (transient outage) and #5 (dst-host change cleanup) via sync_once."""

from __future__ import annotations

from pathlib import Path

from mikrotik_proxy_manager.dns import DnsManager
from mikrotik_proxy_manager.models import MikrotikProxyRule
from mikrotik_proxy_manager.sync import sync_once
from tests.conftest import FakeMikroTik

TLS = "letsEncrypt"


def _rule(rule_id: str, host: str, ip: str = "10.0.0.10", port: str = "80") -> dict[str, str]:
    return {
        "id": rule_id,
        "dst-host": host,
        "dst-address": ip,
        "dst-port": port,
        "disabled": "false",
    }


def _tick(client: FakeMikroTik, state, configs_dir: Path, dns: DnsManager):
    return sync_once(client, state, configs_dir=str(configs_dir), tls_cert_resolver=TLS, dns=dns)


def test_fetch_failure_does_not_wipe_state(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    """#2/#3: a transient API error must NOT delete files or DNS records."""
    initial_dict = _rule("*1", "a.foo.com")
    fake_mikrotik.proxy_list = [initial_dict]
    state = _tick(fake_mikrotik, [], configs_dir, dns)
    assert (configs_dir / "1.yaml").exists()
    expected = [MikrotikProxyRule.from_api(initial_dict)]
    assert state == expected

    fake_mikrotik.fetch_error = ConnectionError("router unreachable")
    state = _tick(fake_mikrotik, state, configs_dir, dns)

    assert (configs_dir / "1.yaml").exists()
    assert state == expected
    assert fake_mikrotik.removed == []


def test_dst_host_change_removes_old_dns(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    """#5: same id, new dst-host → old A-record must be removed."""
    fake_mikrotik.proxy_list = [_rule("*1", "old.foo.com")]
    state = _tick(fake_mikrotik, [], configs_dir, dns)
    assert ("old.foo.com", "10.0.0.1") in fake_mikrotik.added

    fake_mikrotik.proxy_list = [_rule("*1", "new.foo.com")]
    state = _tick(fake_mikrotik, state, configs_dir, dns)

    assert "old.foo.com" in fake_mikrotik.removed
    assert ("new.foo.com", "10.0.0.1") in fake_mikrotik.added


def test_deleted_rule_cleans_up_file_and_dns(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    fake_mikrotik.proxy_list = [_rule("*1", "a.foo.com"), _rule("*2", "b.foo.com")]
    state = _tick(fake_mikrotik, [], configs_dir, dns)
    assert (configs_dir / "1.yaml").exists()
    assert (configs_dir / "2.yaml").exists()

    fake_mikrotik.proxy_list = [_rule("*1", "a.foo.com")]
    state = _tick(fake_mikrotik, state, configs_dir, dns)

    assert (configs_dir / "1.yaml").exists()
    assert not (configs_dir / "2.yaml").exists()
    assert "b.foo.com" in fake_mikrotik.removed


def test_connect_failure_does_not_wipe_state(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    """#11: ensure_connected() failure must be treated like a fetch failure
    — preserve state, drop the (broken) pool, retry next tick."""
    fake_mikrotik.proxy_list = [_rule("*1", "a.foo.com")]
    state = _tick(fake_mikrotik, [], configs_dir, dns)
    expected = state[:]

    fake_mikrotik.connect_error = ConnectionRefusedError("nope")
    new_state = _tick(fake_mikrotik, state, configs_dir, dns)

    assert new_state == expected
    assert fake_mikrotik.disconnect_calls >= 1  # broken pool dropped


def test_no_op_tick_when_state_unchanged(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    fake_mikrotik.proxy_list = [_rule("*1", "a.foo.com")]
    state = _tick(fake_mikrotik, [], configs_dir, dns)
    fake_mikrotik.added.clear()
    fake_mikrotik.removed.clear()

    state = _tick(fake_mikrotik, state, configs_dir, dns)
    assert fake_mikrotik.added == []
    assert fake_mikrotik.removed == []
