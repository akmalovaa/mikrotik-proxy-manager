from __future__ import annotations

import contextlib
import os
import tempfile
from typing import Any

import yaml
from loguru import logger

from mikrotik_proxy_manager.models import MikrotikProxyRule


def render_config(rule: MikrotikProxyRule, tls_cert_resolver: str) -> dict[str, Any]:
    """Build the Traefik dynamic-config dict for a single rule. Pure: no IO.

    If ``tls_cert_resolver`` is empty, the router emits ``tls: {}`` so it
    inherits the resolver (and any wildcard ``domains`` block) from the
    entryPoint-level ``http.tls`` config. This lets a single wildcard cert
    serve every generated subdomain without per-host ACME requests."""
    slug = rule.slug
    if slug is None:
        raise ValueError(f"Rule {rule.id} has no usable slug; check is_routable() first")
    tls_block: dict[str, Any] = {"certResolver": tls_cert_resolver} if tls_cert_resolver else {}
    return {
        "http": {
            "routers": {
                f"{slug}_router": {
                    "entryPoints": ["websecure"],
                    "rule": f"Host(`{rule.dst_host}`)",
                    "service": f"{slug}_service",
                    "tls": tls_block,
                }
            },
            "services": {
                f"{slug}_service": {
                    "loadBalancer": {
                        "servers": [{"url": f"http://{rule.dst_address}:{rule.dst_port}"}]
                    }
                }
            },
        }
    }


def write_config(rule: MikrotikProxyRule, configs_dir: str, tls_cert_resolver: str) -> bool:
    """Atomically write a rule's config file. Returns True on success.

    Atomic write: dump to a sibling temp file, then os.replace() onto the
    target. Traefik's file provider watches this directory; without atomic
    replace it can read a truncated/half-written file and drop the router
    for a tick. The temp file MUST live in the same directory (same FS) so
    os.replace stays atomic, and must NOT use a .yaml/.yml suffix or
    Traefik would try to parse it."""
    file = f"{configs_dir}/{rule.file_id}.yaml"
    config = render_config(rule, tls_cert_resolver)
    logger.debug(f"Result config: {config}")

    dir_ = os.path.dirname(file) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=f".{rule.file_id}.", suffix=".tmp", dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, file)
        logger.info(f"Add config: {file}")
        return True
    except Exception as e:
        logger.error(f"Error when adding a file:{file}, {e}")
        if os.path.exists(tmp_path):
            with contextlib.suppress(OSError):
                os.remove(tmp_path)
        return False


def remove_config(file_id: str | None, configs_dir: str) -> bool:
    """Remove a generated config file. Returns True on success or if the file
    was already absent (both are 'desired state achieved'); False if the
    delete itself failed so the caller can retry on the next tick."""
    if not file_id:
        return False
    file = f"{configs_dir}/{file_id}.yaml"
    logger.debug(f"Attempting to remove config: {file}")
    if not os.path.exists(file):
        logger.debug(f"File does not exist: {file}")
        return True
    try:
        os.remove(file)
        logger.info(f"Removed config: {file}")
        return True
    except Exception as e:
        logger.warning(f"Error deleting {file}: {e}")
        return False
