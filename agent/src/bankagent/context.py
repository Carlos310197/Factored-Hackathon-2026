"""Verified session identity. customer_id only ever comes from a verified token."""
from dataclasses import dataclass

SCOPE_READ = "inquiry:read"
SCOPE_DISPUTE = "dispute:create"


class PermissionDenied(Exception):
    """The session lacks the scope an action requires."""


@dataclass(frozen=True)
class SessionContext:
    customer_id: str
    session_id: str
    scopes: frozenset[str]
    lang: str
    expires_at: int

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise PermissionDenied(scope)
