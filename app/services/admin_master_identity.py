from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException
from app.security import decode_token

_ADMIN_MASTER_ROLE_SET = {"admin_master", "master_admin"}
_ADMIN_CONSOLE_ROLE_SET = {
    "admin",
    "owner",
    "superadmin",
    "super_admin",
    "admin_master",
    "master_admin",
    "creator",
}
_ADMIN_MASTER_ENV_KEYS = (
    "ADMIN_MASTER_EMAILS",
    "MASTER_ADMIN_EMAILS",
    "ORKIO_ADMIN_MASTER_EMAILS",
    "SUPER_ADMIN_EMAILS",
)


def _clean(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 2 and ((raw[0] == raw[-1] == '"') or (raw[0] == raw[-1] == "'")):
        raw = raw[1:-1].strip()
    return raw


def _csv_env(*keys: str) -> set[str]:
    values: set[str] = set()
    for key in keys:
        raw = _clean(os.getenv(key, ""))
        if not raw:
            continue
        for item in raw.split(","):
            norm = _clean(item).lower()
            if norm:
                values.add(norm)
    return values


def get_admin_master_emails() -> set[str]:
    return _csv_env(*_ADMIN_MASTER_ENV_KEYS)


def admin_master_emails_configured() -> bool:
    return bool(get_admin_master_emails())


def get_master_admin_key() -> str:
    return _clean(os.getenv("MASTER_ADMIN_KEY", "")) or _clean(os.getenv("ADMIN_API_KEY", ""))


def extract_identity_email(subject: Any) -> str:
    if isinstance(subject, dict):
        return _clean(subject.get("email") or subject.get("user_email") or subject.get("preferred_username")).lower()
    return _clean(getattr(subject, "email", "")).lower()


def extract_identity_name(subject: Any) -> str:
    if isinstance(subject, dict):
        return _clean(
            subject.get("name")
            or subject.get("full_name")
            or subject.get("display_name")
            or subject.get("given_name")
            or extract_identity_email(subject)
            or "Usuário autenticado"
        )
    return _clean(getattr(subject, "name", "") or extract_identity_email(subject) or "Usuário autenticado")


def extract_identity_role(subject: Any) -> str:
    if isinstance(subject, dict):
        role = _clean(subject.get("role")).lower()
        if role:
            return role
        if bool(subject.get("is_admin")) or bool(subject.get("admin")) or bool(subject.get("admin_console_access")):
            return "admin"
        return "user"
    role = _clean(getattr(subject, "role", "")).lower()
    if role:
        return role
    if bool(getattr(subject, "is_admin", False)) or bool(getattr(subject, "admin", False)):
        return "admin"
    return "user"


def extract_identity_sub(subject: Any) -> str:
    if isinstance(subject, dict):
        return _clean(subject.get("sub") or subject.get("id") or "unknown") or "unknown"
    return _clean(getattr(subject, "id", "") or getattr(subject, "sub", "") or "unknown") or "unknown"


def is_admin_master(subject: Any) -> bool:
    if subject is None:
        return False
    if isinstance(subject, dict):
        if bool(subject.get("is_admin_master")) or bool(subject.get("master_admin")) or bool(subject.get("write_approval_authority")):
            return True
    else:
        if bool(getattr(subject, "is_admin_master", False)) or bool(getattr(subject, "master_admin", False)) or bool(getattr(subject, "write_approval_authority", False)):
            return True
    email = extract_identity_email(subject)
    role = extract_identity_role(subject)
    configured = get_admin_master_emails()
    if email and configured and email in configured:
        return True
    return role in _ADMIN_MASTER_ROLE_SET


def has_admin_console_access(subject: Any) -> bool:
    if subject is None:
        return False
    if is_admin_master(subject):
        return True
    if isinstance(subject, dict):
        if bool(subject.get("admin_console_access")) or bool(subject.get("is_admin")) or bool(subject.get("admin")):
            return True
    else:
        if bool(getattr(subject, "admin_console_access", False)) or bool(getattr(subject, "is_admin", False)) or bool(getattr(subject, "admin", False)):
            return True
    role = extract_identity_role(subject)
    return role in _ADMIN_CONSOLE_ROLE_SET


def authority_source(subject: Any) -> str:
    email = extract_identity_email(subject)
    role = extract_identity_role(subject)
    configured = get_admin_master_emails()
    if email and configured and email in configured:
        return "admin_master_identity"
    if role in _ADMIN_MASTER_ROLE_SET:
        return "master_admin_role"
    if has_admin_console_access(subject):
        return "admin_console_role_without_write_approval"
    return "none"


def build_admin_authority_context(subject: Any) -> Dict[str, Any]:
    master = is_admin_master(subject)
    admin_access = has_admin_console_access(subject)
    role = extract_identity_role(subject)
    return {
        "authenticated": bool(extract_identity_sub(subject) != "unknown" or extract_identity_email(subject)),
        "name": extract_identity_name(subject),
        "email": extract_identity_email(subject) or "unknown",
        "sub": extract_identity_sub(subject),
        "role": "admin_master" if master else role,
        "is_admin_master": bool(master),
        "is_admin_like": bool(admin_access),
        "admin_console_access": bool(admin_access),
        "write_approval_authority": bool(master),
        "write_authority": bool(master),
        "authority_source": authority_source(subject),
        "admin_master_configured": admin_master_emails_configured(),
        "approval_model": "tokenized_pending_proposal_scope",
    }


def _payload_from_auth(
    authorization: Optional[str],
    x_admin_key: Optional[str],
    *,
    require_master: bool,
) -> Dict[str, Any]:
    master_key = get_master_admin_key()
    if x_admin_key and master_key and x_admin_key == master_key:
        base = {"role": "master_admin", "via": "x_admin_key", "email": "x-admin-key", "sub": "x-admin-key"}
        return {**base, **build_admin_authority_context(base)}

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Master admin required" if require_master else "Admin console access required")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    context = {**payload, **build_admin_authority_context(payload), "via": "bearer"}
    if require_master:
        if not context.get("write_approval_authority"):
            raise HTTPException(status_code=403, detail="Master admin email required")
    else:
        if not context.get("admin_console_access"):
            raise HTTPException(status_code=403, detail="Admin console access required")
    return context


def require_admin_console_access(
    authorization: Optional[str] = Header(default=None),
    x_admin_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    return _payload_from_auth(authorization, x_admin_key, require_master=False)


def require_master_admin_access(
    authorization: Optional[str] = Header(default=None),
    x_admin_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    return _payload_from_auth(authorization, x_admin_key, require_master=True)
