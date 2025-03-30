import routeros_api
from loguru import logger
from mikrotik_proxy_manager.settings import settings


class MikroTikClient:
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self.connection = None

    def connect(self):
        try:
            self.connection = routeros_api.RouterOsApiPool(
                self.host,
                username=self.user,
                password=self.password,
                use_ssl=True,
                ssl_verify=False,
                ssl_verify_hostname=False,
                plaintext_login=True,
            )
            logger.info(f"Success connection to host: {self.host}")
        except Exception as e:
            logger.error("Exception:", str(e))


    def disconnect(self):
        if self.connection:
            self.connection.disconnect()


    def fetch_proxy_list(self) -> list:
        logger.debug("Mikrotik fetch proxy access list")
        proxy_list: list = []
        if not self.connection:
            self.connect()
        if self.connection:
            mikrotik_api = self.connection.get_api()
            proxy_list = mikrotik_api.get_resource("/ip/proxy/access").get()
        else:
            logger.error("Failed to test connection: Connection to MikroTik not established.")
        # self.disconnect()
        return proxy_list
