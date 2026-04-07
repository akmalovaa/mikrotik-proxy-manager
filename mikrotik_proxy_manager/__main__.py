from __future__ import annotations

import signal
import sys
import time
from types import FrameType

from loguru import logger

from mikrotik_proxy_manager.dns import DnsManager
from mikrotik_proxy_manager.mikrotik_client import MikroTikClient
from mikrotik_proxy_manager.models import MikrotikProxyRule
from mikrotik_proxy_manager.settings import settings
from mikrotik_proxy_manager.sync import sync_once

logger.remove()
if settings.log_json:
    # serialize=True emits one JSON object per record on stderr, matching
    # Traefik's `log.format: json` so a single log shipper can ingest both.
    logger.add(sys.stderr, level=settings.log_level, serialize=True)
else:
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="{time:DD.MM.YY HH:mm:ss} {level} {message}",
    )


_shutdown: bool = False


def _request_shutdown(signum: int, frame: FrameType | None) -> None:
    # Signal handlers must be minimal: no I/O, no logging, no sys.exit.
    # The main loop polls this flag and performs cleanup itself.
    global _shutdown
    _shutdown = True


def main() -> None:
    state: list[MikrotikProxyRule] = []

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    interval = settings.mikrotik_sync_interval_seconds
    logger.info(f"Mikrotik Proxy Manager started, sync every {interval}s")

    # The `with` block guarantees disconnect() runs even if the loop body
    # raises something we didn't anticipate.
    with MikroTikClient(
        settings.mikrotik_host, settings.mikrotik_user, settings.mikrotik_password
    ) as client:
        dns = DnsManager(client, settings)
        while not _shutdown:
            state = sync_once(
                client,
                state,
                configs_dir=settings.traefik_configs_path,
                tls_cert_resolver=settings.tls_cert_resolver,
                dns=dns,
            )
            # Sleep in 1s slices so SIGTERM is honoured within the grace period.
            for _ in range(interval):
                if _shutdown:
                    break
                time.sleep(1)

    logger.info("Mikrotik Proxy Manager stopped")


if __name__ == "__main__":
    main()
