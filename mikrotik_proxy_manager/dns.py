from __future__ import annotations

from typing import Protocol


class _DnsClient(Protocol):
    def add_dns_static_record(self, ip: str, host: str) -> bool: ...
    def remove_dns_static_record(self, host: str) -> bool: ...


class _SettingsLike(Protocol):
    mikrotik_dns_manager: bool
    reverse_proxy_ip: str | None
    mikrotik_host: str


class DnsManager:
    def __init__(self, client: _DnsClient, settings: _SettingsLike) -> None:
        self._client = client
        self._settings = settings

    def add(self, host: str) -> None:
        if not host or not self._settings.mikrotik_dns_manager:
            return
        ip = self._settings.reverse_proxy_ip or self._settings.mikrotik_host
        self._client.add_dns_static_record(ip, host)

    def remove(self, host: str) -> None:
        if not host or not self._settings.mikrotik_dns_manager:
            return
        self._client.remove_dns_static_record(host)
