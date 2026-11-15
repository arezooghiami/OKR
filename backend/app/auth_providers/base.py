from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExternalUser:
    external_id: str
    username: str
    full_name: str
    email: str | None = None
    groups: tuple[str, ...] = ()


class AuthProvider(Protocol):
    name: str

    def authenticate(self, username: str, password: str) -> ExternalUser | None: ...
