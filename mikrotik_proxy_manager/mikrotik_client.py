from __future__ import annotations

from types import TracebackType

import routeros_api
from loguru import logger


class MikroTikClient:
    def __init__(self, host: str, user: str, password: str) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.connection: routeros_api.RouterOsApiPool | None = None
        # Local cache of /ip/dns/static records we manage. Maps host -> id of
        # the corresponding record on the router. None means "not yet loaded";
        # any DNS API error invalidates it back to None so the next call
        # rebuilds it from the live router state. This avoids hammering the
        # API with add/remove round-trips on every sync tick when nothing
        # actually changed.
        self._dns_cache: dict[str, dict[str, str]] | None = None

    def _ensure_dns_cache(self) -> dict[str, dict[str, str]]:
        if self._dns_cache is not None:
            return self._dns_cache
        records = self.fetch_dns_static_list()
        cache: dict[str, dict[str, str]] = {}
        for r in records:
            name = r.get("name")
            if name:
                cache[name] = {"id": r.get("id", ""), "address": r.get("address", "")}
        self._dns_cache = cache
        return self._dns_cache

    def _invalidate_dns_cache(self) -> None:
        self._dns_cache = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> MikroTikClient:
        # NB: connect() is NOT called here on purpose. If the router happens
        # to be unreachable at process start we don't want main() to crash —
        # the sync loop should keep retrying. The first ensure_connected()
        # inside sync_once() opens the pool when the router becomes available.
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.disconnect()

    def ensure_connected(self) -> None:
        """Idempotent: open the pool if it isn't already. Raises on failure
        so the caller can treat it as a transient outage and retry."""
        if self.connection is not None:
            return
        self.connect()

    def connect(self) -> None:
        """Open the API pool. Raises on failure — callers must handle it."""
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
            logger.error(f"Connect to {self.host} failed: {e}")
            self.connection = None
            raise

    def disconnect(self) -> None:
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None

    def _require_connection(self) -> routeros_api.RouterOsApiPool:
        """Return the live API pool or raise. All API methods funnel through
        this so the 'is the pool open?' check lives in exactly one place."""
        if self.connection is None:
            raise RuntimeError(
                "MikroTikClient used without an active connection — call ensure_connected() first"
            )
        return self.connection

    def fetch_proxy_list(self) -> list[dict[str, str]]:
        """Fetch /ip/proxy/access. Raises on API errors so the caller can
        skip the sync tick instead of treating an outage as an empty rule
        list (which would wipe all configs and DNS records)."""
        logger.debug("Mikrotik fetch proxy access list")
        conn = self._require_connection()
        try:
            return conn.get_api().get_resource("/ip/proxy/access").get()
        except Exception as e:
            logger.error(f"Failed to fetch proxy list: {e}")
            self.disconnect()
            raise

    def fetch_dns_static_list(self) -> list[dict[str, str]]:
        logger.debug("Fetching DNS static list")
        try:
            conn = self._require_connection()
            dns_list = conn.get_api().get_resource("/ip/dns/static").get()
            logger.info(f"Successfully fetched {len(dns_list)} DNS list")
            return dns_list
        except Exception as e:
            logger.error(f"Failed to fetch DNS list: {e}")
            return []

    def add_dns_static_record(self, ip_address: str, host_name: str) -> bool:
        logger.debug(f"Adding DNS static record: {host_name} -> {ip_address}")
        try:
            conn = self._require_connection()
        except RuntimeError as e:
            logger.error(str(e))
            return False

        try:
            cache = self._ensure_dns_cache()
        except Exception as e:
            logger.error(f"Failed to load DNS cache: {e}")
            self._invalidate_dns_cache()
            return False

        existing = cache.get(host_name)
        if existing and existing.get("address") == ip_address:
            logger.debug(
                f"DNS static record already up-to-date (cache hit): {host_name} -> {ip_address}"
            )
            return True

        try:
            dns_resource = conn.get_api().get_resource("/ip/dns/static")

            # If the host exists but points to a different IP, drop it first
            # so the new record can take its place.
            if existing:
                try:
                    dns_resource.remove(id=existing["id"])
                except Exception as e:
                    logger.warning(f"Failed to remove stale DNS record for {host_name}: {e}")

            # ADD DNS + comment mpm (MikroTik Proxy Manager)
            new_record = dns_resource.add(
                address=ip_address, name=host_name, type="A", comment="mpm"
            )

            # routeros_api returns the new id; if not, refetch lazily next call.
            new_id = new_record if isinstance(new_record, str) else ""
            cache[host_name] = {"id": new_id, "address": ip_address}
            if not new_id:
                # Force a rebuild on next access so we learn the real id.
                self._invalidate_dns_cache()

            logger.info(f"Successfully added DNS static record: {host_name} -> {ip_address}")
            return True

        except Exception as e:
            self._invalidate_dns_cache()
            error_str = str(e)
            if "entry already exists" in error_str:
                logger.info(f"DNS static record already exists: {host_name} -> {ip_address}")
                return True
            logger.error(f"Failed to add DNS static record: {error_str}")
            return False

    def remove_dns_static_record(self, host_name: str) -> bool:
        logger.debug(f"Removing DNS static record: name={host_name}")
        try:
            conn = self._require_connection()
        except RuntimeError as e:
            logger.error(str(e))
            return False

        try:
            cache = self._ensure_dns_cache()
        except Exception as e:
            logger.error(f"Failed to load DNS cache: {e}")
            self._invalidate_dns_cache()
            return False

        if host_name not in cache:
            logger.debug(f"DNS record absent (cache hit): {host_name}")
            return True

        try:
            dns_resource = conn.get_api().get_resource("/ip/dns/static")
            record_id = cache[host_name]["id"]
            if record_id:
                dns_resource.remove(id=record_id)
                logger.info(f"Removed DNS record: {host_name} (ID: {record_id})")
            else:
                # No id captured (e.g. cache built from a partial response):
                # fall back to a name lookup so we still remove it.
                for record in dns_resource.get():
                    if record.get("name") == host_name:
                        dns_resource.remove(id=record["id"])
                        logger.info(f"Removed DNS record: {host_name} (ID: {record['id']})")
            cache.pop(host_name, None)
            return True
        except Exception as e:
            self._invalidate_dns_cache()
            logger.error(f"Failed to remove DNS static record: {e}")
            return False
