import yaml
import os
import sys
import schedule
import time
import re
import signal
from typing import Any

from loguru import logger
from mikrotik_proxy_manager.settings import settings
from mikrotik_proxy_manager.mikrotik_client import MikroTikClient

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="{time:DD.MM.YY HH:mm:ss} {level} {message}",
)

mikrotik = MikroTikClient(
    settings.mikrotik_host, settings.mikrotik_user, settings.mikrotik_password
)

PROXY_LAST_CONFIG: list[dict[str, str]] = []


def traefik_config_rm(id: str | None) -> None:
    if not id:
        return
    else:
        file_id = id[1:] if id else 0
    file = f"{settings.traefik_configs_path}/{file_id}.yaml"
    logger.debug(f"Attempting to remove config: {file}")
    if os.path.exists(file):
        try:
            os.remove(file)
            logger.info(f"Removed config: {file}")
        except Exception as e:
            logger.warning(f"Error deleting {file}: {e}")
    else:
        logger.debug(f"File does not exist: {file}")


def add_dns_record(host: str) -> None:
    """Add DNS record to proxy service or self router IP"""
    proxy_server_ip = (
        settings.reverse_proxy_ip
        if settings.reverse_proxy_ip
        else settings.mikrotik_host
    )
    if settings.mikrotik_dns_manager:
        mikrotik.add_dns_static_record(proxy_server_ip, host)


def remove_dns_record(host: str) -> None:
    """Remove DNS record if mikrotik_dns is enabled"""
    if settings.mikrotik_dns_manager and host:
        mikrotik.remove_dns_static_record(host)


def traefik_config_add(rule: dict[str, str], rule_name: str) -> None:
    id = rule.get("id")
    ip = rule.get("dst-address")
    port = rule.get("dst-port")
    host = rule.get("dst-host")
    file_id = id[1:] if id else "unknown"
    file = f"{settings.traefik_configs_path}/{file_id}.yaml"

    traefik_router = {
        f"{rule_name}_router": {
            "entryPoints": ["websecure"],
            "rule": f"Host(`{host}`)",
            "service": f"{rule_name}_service",
            "tls": {"certResolver": settings.tls_cert_resolver},
        }
    }
    traefik_service = {
        f"{rule_name}_service": {
            "loadBalancer": {"servers": [{"url": f"http://{ip}:{port}"}]}
        }
    }
    config = {
        "http": {
            "routers": traefik_router,
            "services": traefik_service,
        }
    }
    logger.debug(f"Result config: {config}")

    try:
        with open(file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Add config: {file}")
        if host and ip:
            add_dns_record(host)
    except Exception as e:
        logger.error(f"Error when adding a file:{file}, {e}")


def extract_name_from_domain(domain: str) -> str | None:
    """Extract name from domain for traefik config, to create router and service"""
    logger.debug(f"Extract name from domain: {domain}")
    if not domain:
        return None
    if domain.count(".") < 1 or domain.startswith("."):
        logger.warning(f"dst-host - incorrect domain format: {domain}")
        return None
    if not re.match(r"^[a-zA-Z0-9.-]+$", domain):
        logger.warning(f"dst-host - invalid domain format: {domain}")
        return None
    parts = domain.split(".")
    if len(parts) >= 3:
        return f"{parts[0]}_{parts[-2]}"
    return parts[0]


def generate_traefik_config(proxy_list: list[dict[str, str]]) -> list[dict[str, str]]:
    for rule in proxy_list:
        id = rule.get("id")
        dst_host: str = rule.get("dst-host", "")

        if rule.get("disabled") == "true":
            logger.info(f"Rule with id: {id} is disabled")
            traefik_config_rm(id)
            if dst_host:
                remove_dns_record(dst_host)
            continue

        rule_name: str | None = extract_name_from_domain(dst_host)
        if not rule_name:
            logger.warning(f"Missing dst-host in the rule with id: {id}")
            traefik_config_rm(id)
            if dst_host:
                remove_dns_record(dst_host)
            continue
        dst_port: str = rule.get("dst-port", "")
        if not dst_port:
            logger.warning(f"Missing dst-port in the rule with id: {id}")
            traefik_config_rm(id)
            if dst_host:
                remove_dns_record(dst_host)
            continue
        dst_address: str = rule.get("dst-address", "")
        if not dst_address:
            logger.warning(f"Missing dst-address in the rule with id: {id}")
            traefik_config_rm(id)
            if dst_host:
                remove_dns_record(dst_host)
            continue
        traefik_config_add(rule, rule_name)
    return proxy_list


def sync_proxy_config() -> None:
    global PROXY_LAST_CONFIG
    proxy_list = mikrotik.fetch_proxy_list()
    if PROXY_LAST_CONFIG == proxy_list:
        logger.debug("No changes in the proxy list")
        return
    else:
        # Check for deleted rules and clean up their configs and DNS
        if PROXY_LAST_CONFIG:
            current_ids = {rule.get("id") for rule in proxy_list}
            last_ids = {rule.get("id") for rule in PROXY_LAST_CONFIG}
            deleted_ids = last_ids - current_ids

            for deleted_id in deleted_ids:
                if deleted_id:
                    logger.info(f"Rule with id: {deleted_id} was deleted, cleaning up")
                    # Find the deleted rule to get its dst-host
                    deleted_rule = next(
                        (
                            rule
                            for rule in PROXY_LAST_CONFIG
                            if rule.get("id") == deleted_id
                        ),
                        None,
                    )
                    if deleted_rule:
                        dst_host = deleted_rule.get("dst-host", "")
                        traefik_config_rm(deleted_id)
                        if dst_host:
                            remove_dns_record(dst_host)

        PROXY_LAST_CONFIG = generate_traefik_config(proxy_list)
        logger.debug(f"Proxy list: {proxy_list}")


def run_scheduler() -> None:
    sync_interval: int = settings.mikrotik_sync_interval_seconds
    logger.info(f"Run scheduler: sync traefik config every {sync_interval} seconds")

    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Received shutdown signal, closing MikroTik connection...")
        mikrotik.disconnect()
        logger.info("Mikrotik Proxy Manager stopped")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    schedule.every(sync_interval).seconds.do(sync_proxy_config)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    logger.info("Mikrotik Proxy Manager started")
    run_scheduler()
