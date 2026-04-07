from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from loguru import logger

from mikrotik_proxy_manager.dns import DnsManager
from mikrotik_proxy_manager.models import MikrotikProxyRule
from mikrotik_proxy_manager.traefik_writer import remove_config, write_config


class _ProxyClient(Protocol):
    def ensure_connected(self) -> None: ...
    def fetch_proxy_list(self) -> list[dict[str, str]]: ...
    def disconnect(self) -> None: ...


@dataclass
class SyncDiff:
    deleted: list[MikrotikProxyRule] = field(default_factory=list)
    host_changed: list[tuple[MikrotikProxyRule, MikrotikProxyRule]] = field(default_factory=list)


def diff_snapshots(
    old: list[MikrotikProxyRule],
    new: list[MikrotikProxyRule],
) -> SyncDiff:
    """Pure diff between two snapshots, keyed by rule id.

    - 'deleted': rules present in *old* but not in *new*. Their config files
      and DNS records need to be cleaned up.
    - 'host_changed': pairs (prev, current) where the rule kept its id but
      the dst-host moved. Without this, the old DNS A-record would leak."""
    old_by_id = {r.id: r for r in old}
    new_ids = {r.id for r in new}

    deleted = [old_by_id[i] for i in (set(old_by_id) - new_ids)]

    host_changed: list[tuple[MikrotikProxyRule, MikrotikProxyRule]] = []
    for r in new:
        prev = old_by_id.get(r.id)
        if prev and prev.dst_host and prev.dst_host != r.dst_host:
            host_changed.append((prev, r))

    return SyncDiff(deleted=deleted, host_changed=host_changed)


def reconcile(
    rules: list[MikrotikProxyRule],
    *,
    configs_dir: str,
    tls_cert_resolver: str,
    dns: DnsManager,
) -> list[MikrotikProxyRule]:
    """Reconcile each rule with disk + DNS state. Returns ONLY rules that
    were successfully processed (either written, or intentionally skipped
    after a clean cleanup). Rules whose file write failed are left out so
    the next sync tick will retry them instead of treating them as done."""
    processed: list[MikrotikProxyRule] = []

    def _cleanup(rule: MikrotikProxyRule) -> bool:
        ok = remove_config(rule.file_id, configs_dir)
        dns.remove(rule.dst_host)
        return ok

    for rule in rules:
        if not rule.is_routable():
            if rule.disabled:
                logger.info(f"Rule with id: {rule.id} is disabled")
            else:
                logger.warning(
                    f"Rule {rule.id} not routable (host/port/address missing or invalid)"
                )
            if _cleanup(rule):
                processed.append(rule)
            continue

        if write_config(rule, configs_dir, tls_cert_resolver):
            dns.add(rule.dst_host)
            processed.append(rule)
        # else: leave out → next tick will retry the write

    return processed


def sync_once(
    client: _ProxyClient,
    state: list[MikrotikProxyRule],
    *,
    configs_dir: str,
    tls_cert_resolver: str,
    dns: DnsManager,
) -> list[MikrotikProxyRule]:
    """Run one sync tick. Returns the new state.

    On a fetch error the previous *state* is returned unchanged so a
    transient outage doesn't wipe configs or DNS records."""
    try:
        client.ensure_connected()
        raw = client.fetch_proxy_list()
    except Exception as e:
        logger.warning(f"Sync skipped, MikroTik unreachable: {e}")
        # Drop the (possibly half-dead) pool so the next tick reconnects
        # cleanly instead of reusing a broken socket.
        client.disconnect()
        return state

    new = [MikrotikProxyRule.from_api(r) for r in raw]
    if state == new:
        logger.debug("No changes in the proxy list")
        return state

    diff = diff_snapshots(state, new)
    for deleted in diff.deleted:
        logger.info(f"Rule with id: {deleted.id} was deleted, cleaning up")
        remove_config(deleted.file_id, configs_dir)
        dns.remove(deleted.dst_host)
    for prev, current in diff.host_changed:
        logger.info(
            f"Rule {current.id} dst-host changed: {prev.dst_host} -> {current.dst_host}, removing stale DNS"
        )
        dns.remove(prev.dst_host)

    return reconcile(
        new,
        configs_dir=configs_dir,
        tls_cert_resolver=tls_cert_resolver,
        dns=dns,
    )
