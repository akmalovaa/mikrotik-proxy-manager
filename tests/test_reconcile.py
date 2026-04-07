"""#4 / #6 / #9: reconcile + atomic write + retry semantics."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mikrotik_proxy_manager import traefik_writer
from mikrotik_proxy_manager.dns import DnsManager
from mikrotik_proxy_manager.models import MikrotikProxyRule
from mikrotik_proxy_manager.sync import reconcile
from mikrotik_proxy_manager.traefik_writer import remove_config, render_config
from tests.conftest import FakeMikroTik

TLS = "letsEncrypt"


def _rule(
    rule_id: str = "*1",
    host: str = "app.foo.com",
    ip: str = "10.0.0.10",
    port: str = "8080",
    disabled: str = "false",
) -> MikrotikProxyRule:
    return MikrotikProxyRule.from_api(
        {
            "id": rule_id,
            "dst-host": host,
            "dst-address": ip,
            "dst-port": port,
            "disabled": disabled,
        }
    )


def _reconcile(rules, configs_dir: Path, dns: DnsManager):
    return reconcile(rules, configs_dir=str(configs_dir), tls_cert_resolver=TLS, dns=dns)


def test_writes_valid_yaml_with_expected_structure(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    rule = _rule()
    processed = _reconcile([rule], configs_dir, dns)
    assert processed == [rule]

    written = configs_dir / "1.yaml"
    assert written.exists()
    data = yaml.safe_load(written.read_text())
    routers = data["http"]["routers"]
    services = data["http"]["services"]
    assert "app_foo_com_router" in routers
    assert routers["app_foo_com_router"]["rule"] == "Host(`app.foo.com`)"
    assert services["app_foo_com_service"]["loadBalancer"]["servers"][0]["url"] == (
        "http://10.0.0.10:8080"
    )


def test_dns_record_added_for_valid_rule(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    _reconcile([_rule()], configs_dir, dns)
    assert fake_mikrotik.added == [("app.foo.com", "10.0.0.1")]


def test_disabled_rule_is_cleaned_up_and_marked_processed(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    (configs_dir / "1.yaml").write_text("stale: true\n")

    processed = _reconcile([_rule(disabled="true")], configs_dir, dns)

    assert not (configs_dir / "1.yaml").exists()
    assert fake_mikrotik.removed == ["app.foo.com"]
    assert len(processed) == 1


def test_invalid_rule_missing_port_is_cleaned_and_marked_processed(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    rule = _rule(port="")
    processed = _reconcile([rule], configs_dir, dns)
    assert processed == [rule]
    assert not (configs_dir / "1.yaml").exists()


def test_failed_write_excludes_rule_from_processed(
    configs_dir: Path,
    fake_mikrotik: FakeMikroTik,
    dns: DnsManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#4: failed file write must NOT enter the processed snapshot."""

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(traefik_writer.os, "replace", boom)

    processed = _reconcile([_rule()], configs_dir, dns)
    assert processed == []


def test_atomic_write_leaves_no_tmp_files_on_success(
    configs_dir: Path, fake_mikrotik: FakeMikroTik, dns: DnsManager
) -> None:
    """#9: tmp file must be replaced, not left behind."""
    _reconcile([_rule()], configs_dir, dns)
    leftover = [p for p in configs_dir.iterdir() if p.name.endswith(".tmp")]
    assert leftover == []


def test_atomic_write_cleans_tmp_file_on_failure(
    configs_dir: Path,
    fake_mikrotik: FakeMikroTik,
    dns: DnsManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(traefik_writer.os, "replace", boom)

    _reconcile([_rule()], configs_dir, dns)
    leftover = [p for p in configs_dir.iterdir() if p.name.endswith(".tmp")]
    assert leftover == []


def test_remove_config_returns_true_when_file_absent(configs_dir: Path) -> None:
    """#6: missing file is success (idempotent)."""
    assert remove_config("99", str(configs_dir)) is True


def test_remove_config_returns_false_for_empty_id(configs_dir: Path) -> None:
    assert remove_config(None, str(configs_dir)) is False
    assert remove_config("", str(configs_dir)) is False


def test_render_config_emits_cert_resolver_when_set() -> None:
    cfg = render_config(_rule(), tls_cert_resolver="cloudflare")
    router = cfg["http"]["routers"]["app_foo_com_router"]
    assert router["tls"] == {"certResolver": "cloudflare"}


def test_render_config_emits_empty_tls_when_resolver_unset() -> None:
    """Empty resolver ⇒ ``tls: {}`` so the router inherits the entryPoint-level
    cert resolver + wildcard ``domains`` block (no per-host ACME requests)."""
    cfg = render_config(_rule(), tls_cert_resolver="")
    router = cfg["http"]["routers"]["app_foo_com_router"]
    assert router["tls"] == {}
