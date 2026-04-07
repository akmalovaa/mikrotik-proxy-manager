"""Shared test fixtures.

After the #8 split there is no module-level state to monkeypatch — sync,
reconcile and writers all take their dependencies as arguments. Tests just
construct a FakeMikroTik + DnsManager and pass them in."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from mikrotik_proxy_manager.dns import DnsManager
from mikrotik_proxy_manager.settings import settings


@dataclass
class FakeMikroTik:
    """In-memory stand-in for MikroTikClient. Records DNS calls; never opens
    a socket. Implements both _ProxyClient and _DnsClient protocols."""

    proxy_list: list[dict[str, str]] = field(default_factory=list)
    fetch_error: Exception | None = None
    connect_error: Exception | None = None
    added: list[tuple[str, str]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    ensure_calls: int = 0
    disconnect_calls: int = 0

    def ensure_connected(self) -> None:
        self.ensure_calls += 1
        if self.connect_error:
            raise self.connect_error

    def fetch_proxy_list(self) -> list[dict[str, str]]:
        if self.fetch_error:
            raise self.fetch_error
        return list(self.proxy_list)

    def add_dns_static_record(self, ip: str, host: str) -> bool:
        self.added.append((host, ip))
        return True

    def remove_dns_static_record(self, host: str) -> bool:
        self.removed.append(host)
        return True

    def disconnect(self) -> None:
        self.disconnect_calls += 1


@pytest.fixture
def fake_mikrotik() -> FakeMikroTik:
    return FakeMikroTik()


@pytest.fixture
def configs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "mikrotik_dns_manager", True)
    monkeypatch.setattr(settings, "reverse_proxy_ip", "10.0.0.1")
    return tmp_path


@pytest.fixture
def dns(fake_mikrotik: FakeMikroTik, configs_dir: Path) -> DnsManager:
    # configs_dir dependency ensures settings are patched before DnsManager
    # reads them on the first call.
    return DnsManager(fake_mikrotik, settings)
