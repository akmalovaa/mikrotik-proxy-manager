from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9.-]+$")


class MikrotikProxyRule(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    dst_host: str = Field(default="", alias="dst-host")
    dst_address: str = Field(default="", alias="dst-address")
    dst_port: str = Field(default="", alias="dst-port")
    disabled: bool = False

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> MikrotikProxyRule:
        """Build from a raw RouterOS API dict, normalizing the disabled flag
        which arrives as the strings 'true'/'false'."""
        data = dict(raw)
        if "disabled" in data:
            data["disabled"] = str(data["disabled"]).lower() == "true"
        return cls.model_validate(data)

    @property
    def file_id(self) -> str:
        """RouterOS ids look like '*1A'; the leading '*' is not part of any
        useful filename and must be stripped consistently in one place."""
        return self.id[1:] if self.id.startswith("*") else self.id

    @property
    def slug(self) -> str | None:
        """Underscored full-domain slug used as Traefik router/service name.
        Returns None if dst_host is missing or malformed — that's the signal
        that this rule cannot produce a Traefik config and must be cleaned
        up instead."""
        host = self.dst_host
        if not host or host.count(".") < 1 or host.startswith("."):
            return None
        if not _DOMAIN_RE.match(host):
            return None
        return host.replace(".", "_").replace("-", "_")

    def is_routable(self) -> bool:
        """True iff the rule has all the fields needed to render a Traefik
        router+service entry."""
        return bool(self.slug and self.dst_address and self.dst_port and not self.disabled)
