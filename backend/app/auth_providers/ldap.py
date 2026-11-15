"""Active Directory / LDAP provider. Not verified against a real AD (none available);
tests use a stub connection factory. Production must use LDAPS (use_ssl=True)."""

from collections.abc import Callable
from dataclasses import dataclass

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.auth_providers.base import ExternalUser


@dataclass
class LdapConfig:
    host: str
    base_dn: str
    bind_dn: str
    bind_password: str
    port: int = 636
    use_ssl: bool = True
    user_attr: str = "sAMAccountName"


class LdapProvider:
    name = "ldap"

    def __init__(self, cfg: LdapConfig, connect: Callable[..., Connection] | None = None):
        self.cfg = cfg
        self._connect = connect or self._default_connect

    def _default_connect(self, user: str, password: str) -> Connection:
        server = Server(self.cfg.host, port=self.cfg.port, use_ssl=self.cfg.use_ssl, get_info=ALL)
        return Connection(server, user=user, password=password, auto_bind=True)

    def authenticate(self, username: str, password: str) -> ExternalUser | None:
        if not password:  # an empty password would be an anonymous bind in LDAP
            return None
        try:
            svc = self._connect(self.cfg.bind_dn, self.cfg.bind_password)
            flt = f"({self.cfg.user_attr}={escape_filter_chars(username)})"
            svc.search(self.cfg.base_dn, flt, SUBTREE, attributes=["distinguishedName", "displayName", "mail", "memberOf", self.cfg.user_attr])
            if not svc.entries:
                return None
            entry = svc.entries[0]
            self._connect(str(entry.entry_dn), password)  # raises on bad credentials
        except LDAPException:
            return None
        attrs = entry.entry_attributes_as_dict

        def first(k: str):
            return (attrs.get(k) or [None])[0]

        return ExternalUser(
            external_id=str(entry.entry_dn),
            username=str(first(self.cfg.user_attr) or username),
            full_name=str(first("displayName") or username),
            email=first("mail"),
            groups=tuple(str(g) for g in attrs.get("memberOf", [])),
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._connect(self.cfg.bind_dn, self.cfg.bind_password)
            return True, "اتصال موفق"
        except LDAPException as e:
            return False, f"اتصال ناموفق: {e}"
