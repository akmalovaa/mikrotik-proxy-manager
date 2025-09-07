import routeros_api
from loguru import logger


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

    def fetch_proxy_list(self) -> list[dict[str, str]]:
        logger.debug("Mikrotik fetch proxy access list")
        proxy_list: list[dict[str, str]] = []
        if not self.connection:
            self.connect()
        if self.connection:
            mikrotik_api = self.connection.get_api()
            proxy_list = mikrotik_api.get_resource("/ip/proxy/access").get()
        else:
            logger.error(
                "Failed to test connection: Connection to MikroTik not established."
            )
        return proxy_list

    def fetch_dns_static_list(self) -> list:
        logger.debug("Fetching DNS static list")

        if not self.connection:
            self.connect()

        if not self.connection:
            logger.error(
                "Failed to fetch DNS list: Connection to MikroTik not established."
            )
            return []

        try:
            mikrotik_api = self.connection.get_api()
            dns_resource = mikrotik_api.get_resource("/ip/dns/static")
            dns_list = dns_resource.get()

            logger.info(f"Successfully fetched {len(dns_list)} DNS list")
            return dns_list

        except Exception as e:
            logger.error(f"Failed to fetch DNS list: {str(e)}")
            return []

    def add_dns_static_record(self, ip_address: str, host_name: str) -> bool:
        logger.debug(f"Adding DNS static record: {host_name} -> {ip_address}")

        if not self.connection:
            self.connect()

        if not self.connection:
            logger.error(
                "Failed to add DNS static record: Connection to MikroTik not established."
            )
            return False

        try:
            mikrotik_api = self.connection.get_api()
            dns_resource = mikrotik_api.get_resource("/ip/dns/static")

            # ADD DNS + comment mpm (MikroTik Proxy Manager)
            dns_resource.add(
                address=ip_address, name=host_name, type="A", comment="mpm"
            )

            logger.info(
                f"Successfully added DNS static record: {host_name} -> {ip_address}"
            )
            return True

        except Exception as e:
            error_str = str(e)
            if "entry already exists" in error_str:
                logger.info(
                    f"DNS static record already exists: {host_name} -> {ip_address}"
                )
                return True
            else:
                logger.error(f"Failed to add DNS static record: {error_str}")
                return False

    def remove_dns_static_record(self, host_name: str) -> bool:
        logger.debug(f"Removing DNS static record: name={host_name}")

        if not self.connection:
            self.connect()

        if not self.connection:
            logger.error(
                "Failed to remove DNS static record: Connection to MikroTik not established."
            )
            return False

        try:
            mikrotik_api = self.connection.get_api()
            dns_resource = mikrotik_api.get_resource("/ip/dns/static")

            # Get all records to search by name
            records = dns_resource.get()
            records_to_remove = []

            # Find records with the specified host name
            for record in records:
                if record.get("name") == host_name:
                    records_to_remove.append(record)

            # Remove found records
            removed_count = 0
            for record in records_to_remove:
                try:
                    dns_resource.remove(id=record["id"])
                    logger.info(
                        f"Removed DNS record: {record.get('name', 'N/A')} -> {record.get('address', 'N/A')} (ID: {record['id']})"
                    )
                    removed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to remove DNS record with ID {record['id']}: {str(e)}"
                    )

            if removed_count > 0:
                logger.info(
                    f"Successfully removed {removed_count} DNS static record(s)"
                )
                return True
            else:
                logger.warning(f"No DNS records found with hostname: {host_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to remove DNS static record: {str(e)}")
            return False
