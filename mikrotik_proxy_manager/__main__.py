import yaml
import os
import sys
import schedule
import time
import re

from loguru import logger
from mikrotik_proxy_manager.settings import settings
from mikrotik_proxy_manager.mikrotik_client import MikroTikClient

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="{time:DD.MM.YY HH:mm:ss} {level} {message}",
)

mikrotik = MikroTikClient(settings.mikrotik_host, settings.mikrotik_user, settings.mikrotik_password)

PROXY_LAST_CONFIG:list[dict] = []


def traefik_config_rm(id:str | None) -> None:
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


def traefik_config_add(rule:dict, rule_name:str) -> None:
    id = rule.get('id')
    ip = rule.get('dst-address')
    port = rule.get('dst-port')
    host = rule.get('dst-host')
    file_id = id[1:] if id else "unknown"
    file = f"{settings.traefik_configs_path}/{file_id}.yaml"

    traefik_router = {
        f'{rule_name}-router': {
            'entryPoints': ['websecure'],
            'rule': f"Host(`{host}`)",
            'service': f'{rule_name}-service',
            'tls': {
                'certResolver': 'letsEncrypt'
            }
        }
    }
    traefik_service = {
        f'{rule_name}-service': {
            'loadBalancer': {
                'servers': [{'url': f'http://{ip}:{port}'}]
            }
        }
    }
    config = {
        'http': {
            'routers': traefik_router,
            'services': traefik_service,
        }
    }
    logger.debug(f"Result config: {config}")


    try:
        with open(file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Add config: {file}")
    except Exception as e:
        logger.error(f"Error when adding a file:{file}, {e}")


def extract_name_from_domain(domain: str) -> str | None:
    """Extract name from domain for traefik config, to create router and service"""
    logger.debug(f"Extract name from domain: {domain}")
    if not domain:
        return None
    if domain.count('.') < 1 or domain.startswith('.'):
        logger.warning(f"dst-host - incorrect domain format: {domain}")
        return None
    if not re.match(r'^[a-zA-Z0-9.-]+$', domain):
        logger.warning(f"dst-host - invalid domain format: {domain}")
        return None
    parts = domain.split('.')
    if len(parts) >= 3:
        return f"{parts[0]}_{parts[-2]}"
    return parts[0]


def generate_traefik_config(proxy_list: list) -> list:
    for rule in proxy_list:
        id = rule.get('id')
        if rule.get('disabled') == 'true':
            logger.info(f"Rule with id: {id} is disabled")
            traefik_config_rm(id)
            continue
        dst_host: str = rule.get('dst-host', '')
        rule_name: str | None = extract_name_from_domain(dst_host)
        if not rule_name:
            logger.warning(f"Missing dst-host in the rule with id: {id}")
            traefik_config_rm(id)
            continue
        dst_port: str = rule.get('dst-port', '')
        if not dst_port:
            logger.warning(f"Missing dst-port in the rule with id: {id}")
            traefik_config_rm(id)
            continue
        dst_address: str = rule.get('dst-address', '')
        if not dst_address:
            logger.warning(f"Missing dst-address in the rule with id: {id}")
            traefik_config_rm(id)
            continue
        traefik_config_add(rule, rule_name)
    return proxy_list


def sync_proxy_config():
    global PROXY_LAST_CONFIG
    proxy_list = mikrotik.fetch_proxy_list()
    if PROXY_LAST_CONFIG == proxy_list:
        logger.debug("No changes in the proxy list")
        return
    else:
        PROXY_LAST_CONFIG = generate_traefik_config(proxy_list)


def run_scheduler():
    logger.info("Run scheduler: sync traefik config every 10 seconds")
    
    schedule.every(5).seconds.do(sync_proxy_config)
    
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    logger.info("Mikrotik Proxy Manager started")
    run_scheduler()
