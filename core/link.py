import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

LINK_CODE_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class LinkRequest:
    code: str
    ha_user_id: str
    expires_at: datetime


_codes: dict[str, LinkRequest] = {}


def _purge_expired(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    expired = [code for code, req in _codes.items() if req.expires_at <= now]
    for code in expired:
        _codes.pop(code, None)


def create_link_code(ha_user_id: str) -> LinkRequest:
    _purge_expired()
    code = secrets.token_hex(3).upper()
    expires_at = datetime.now(UTC) + LINK_CODE_TTL
    req = LinkRequest(code=code, ha_user_id=ha_user_id, expires_at=expires_at)
    _codes[code] = req
    return req


def consume_link_code(code: str) -> str | None:
    _purge_expired()
    normalized = code.strip().upper()
    req = _codes.pop(normalized, None)
    if req is None or req.expires_at <= datetime.now(UTC):
        return None
    return req.ha_user_id
