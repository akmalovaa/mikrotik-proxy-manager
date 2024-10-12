import time
import yaml
import os
import sys

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from loguru import logger

from mikrotik_proxy_manager.settings import settings

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="{time:DD.MM.YY HH:mm:ss} {level} {message}",
)

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, filename):
        self.filename = filename
        self.last_position = 0
    def on_modified(self, event):
        if event.src_path.endswith(self.filename):
            try:
                with open(event.src_path, 'r') as file:
                    file.seek(self.last_position)
                    new_lines = file.readlines()
                    self.last_position = file.tell()

                    for line in new_lines:
                        if "ip proxy" in line.lower():
                            events = proxy_events(line.strip())
                            traefik_config_generate(events)
                        else:
                            logger.debug(f"Skip log line: {line.strip()}")
            except Exception as e:
                logger.error(f"Error reading file: {str(e)}")


def proxy_events(log_line:str) -> dict:
    logger.debug(f"Parse log line: {log_line}")
    start_index: int = log_line.find('/ip proxy access')
    event: str = ""
    event_number: str = ""
    proxy_events: dict = {}
    if start_index != -1:
        command = log_line[start_index:]
        events_str: str = command.replace('/ip proxy access ', '').strip(')')
        events_list: list = events_str.split()
        event = events_list[0]
        
        # ADD event log structure changed
        if event == 'add':
            star_pos = log_line.find('(*')
            if star_pos != -1:
                start_pos = log_line.find('(', star_pos)
                close_pos = log_line.find('=', start_pos)
                if start_pos != -1 and close_pos != -1:
                    event_number = log_line[start_pos + 2:close_pos]
        else:
            event_number = events_list[1].strip('*')
        
        proxy_events: dict = {
            'event': event,
            'number': event_number.replace(' ', ''),
            'disabled': "",
            'dst-address': "",
            'dst-host': "",
            'dst-port': ""
        }
        if event == 'set' or event == 'add':
            for part in events_list[2:]:
                key, value = part.split('=')
                proxy_events[key] = value
    return proxy_events


def traefik_config_rm(file:str) -> None:
    try:
        os.remove(file)
        logger.info(f"Remove config: {file}")
    except Exception as e:
        logger.error(f"Error deleting:{file}, {e}")


def traefik_config_add(config:str, file:str) -> None:
    try:
        with open(file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Add config: {file}")
    except Exception as e:
        logger.error(f"Error when adding a file:{file}, {e}")


def traefik_config_generate(events: dict) -> None:
    logger.debug(f"Generate config: {events}")
    event = events.get("event")
    host = events.get("dst-host")
    ip = events.get("dst-address")
    port = events.get("dst-port")
    disabled = events.get("disabled")
    number = events.get("number")
    file = f"./traefik/dynamic/{number}.yaml"
    name = f"{number}-{host.split('.')[0]}"
    traefik_router = {
        f'{name}-router': {
            'entryPoints': ['websecure'],
            'rule': f"Host(`{host}`)",
            'service': f'{name}-service',
            'tls': {
                'certResolver': 'letsEncrypt'
            }
        }
    }
    traefik_service = {
        f'{name}-service': {
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
    if event == "add" and disabled == "no" or event == "set" and disabled == "no":
        traefik_config_add(config, file)
    if event == "remove" or disabled == "yes":
        traefik_config_rm(file)


if __name__ == "__main__":
    logger.info(f"Start watch log file: {settings.mikrotik_log_file}")
    handler = LogFileHandler(settings.mikrotik_log_file)
    
    observer = Observer()
    observer.schedule(handler, path='./logs', recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
