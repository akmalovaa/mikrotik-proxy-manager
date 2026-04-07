"""Pure-function tests for the snapshot diff."""

from __future__ import annotations

from mikrotik_proxy_manager.models import MikrotikProxyRule
from mikrotik_proxy_manager.sync import diff_snapshots


def _r(rule_id: str, host: str = "a.b.com") -> MikrotikProxyRule:
    return MikrotikProxyRule.from_api(
        {
            "id": rule_id,
            "dst-host": host,
            "dst-address": "1.1.1.1",
            "dst-port": "80",
        }
    )


def test_empty_snapshots() -> None:
    diff = diff_snapshots([], [])
    assert diff.deleted == []
    assert diff.host_changed == []


def test_detects_deletion() -> None:
    r1, r2 = _r("*1"), _r("*2", "c.d.com")
    diff = diff_snapshots([r1, r2], [r1])
    assert diff.deleted == [r2]
    assert diff.host_changed == []


def test_detects_host_change() -> None:
    diff = diff_snapshots([_r("*1", "old.com")], [_r("*1", "new.com")])
    assert diff.deleted == []
    assert len(diff.host_changed) == 1
    prev, current = diff.host_changed[0]
    assert prev.dst_host == "old.com"
    assert current.dst_host == "new.com"


def test_no_changes_when_identical() -> None:
    r = _r("*1")
    diff = diff_snapshots([r], [r])
    assert diff.deleted == []
    assert diff.host_changed == []


def test_addition_is_not_in_diff() -> None:
    """New rules are NOT in the diff — they're handled by reconcile, not the
    cleanup phase. The diff only tracks things that need cleanup."""
    diff = diff_snapshots([], [_r("*1")])
    assert diff.deleted == []
    assert diff.host_changed == []


def test_host_change_ignored_if_old_host_was_empty() -> None:
    """No old DNS to remove → not a host_changed event."""
    old = _r("*1")
    old_no_host = MikrotikProxyRule.from_api(
        {
            "id": "*1",
            "dst-host": "",
            "dst-address": "1.1.1.1",
            "dst-port": "80",
        }
    )
    diff = diff_snapshots([old_no_host], [old])
    assert diff.host_changed == []
