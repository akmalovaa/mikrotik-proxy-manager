import time
import yaml
import os
import sys

from loguru import logger

from mikrotik_proxy_manager.settings import settings

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="{time:DD.MM.YY HH:mm:ss} {level} {message}",
)

class FileMonitor:
    def __init__(self, filename: str):
        self.filename = filename
        self.last_position: int = 0
        
    def read_new_lines(self) -> None:
        try:
            with open(self.filename, 'r') as file:
                file.seek(self.last_position)
                lines = file.readlines()
                
                for line in lines:
                    if "ip proxy" in line.lower():
                        logger.info(f"proxy event: {line.strip()}")
                        events = proxy_events(line.strip())
                        traefik_config_generate(events)
                    else:
                        logger.debug(f"skip line: {line.strip()}")
                    # if line.strip():
                    #     logger.info(f"New line: {line.strip()}")
                
                self.last_position = file.tell()
                
        except FileNotFoundError:
            logger.info("File not found")
            raise
        except IOError as e:
            logger.info(f"File reading error: {e}")
            time.sleep(5) # Wait before retrying

            
    def monitor(self) -> None:
        while True:
            try:
                self.read_new_lines()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard Interrupt")
                break
            except Exception as e:
                logger.info(f"Error: {e}")
                time.sleep(5)



def proxy_events(log_line:str) -> dict:
    logger.debug(f"Parse log line: {log_line}")
    start_index: int = log_line.find('/ip proxy access')
    event: str = ""
    event_number: str = ""
    # proxy_events: dict = {}
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
    file = f"{settings.traefik_configs_path}/{number}.yaml"
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
    logger.info(f"Monitoring of the {settings.mikrotik_log_file} file is running")
    monitor = FileMonitor(settings.mikrotik_log_file)
    monitor.monitor()
