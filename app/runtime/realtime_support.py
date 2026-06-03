# ORKIO_AO60A_REALTIME_SUPPORT_EXTRACTION
"""Realtime support primitives for ORKIO API.

This module intentionally contains only schema/normalization/helper code.
Realtime FastAPI routes remain in app/main.py for AO60A to keep the patch
small, reversible and low-risk.

Next cycles may move the /api/realtime/* routes into app/routes/realtime.py
after the PWA flow is fully validated.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RealtimeClientSecretReq(BaseModel):
    """Request an ephemeral client secret for the OpenAI Realtime API."""

    agent_id: Optional[str] = None
    voice: str = Field(default="cedar", description="Realtime voice id.")
    model: str = Field(default="gpt-realtime-mini", description="Realtime model name.")
    ttl_seconds: int = Field(default=600, ge=10, le=7200, description="Client secret TTL in seconds.")
    mode: Optional[str] = Field(default=None, description="platform|summit")
    response_profile: Optional[str] = Field(default=None, description="default|stage")
    language_profile: Optional[str] = Field(default=None, description="auto|pt-BR|en")


class RealtimeStartReq(BaseModel):
    agent_id: Optional[str] = None
    thread_id: Optional[str] = None
    voice: str = Field(default="cedar")
    model: str = Field(default="gpt-realtime-mini")
    ttl_seconds: int = Field(default=600, ge=10, le=7200)
    mode: Optional[str] = Field(default=None, description="platform|summit")
    response_profile: Optional[str] = Field(default=None, description="default|stage")
    language_profile: Optional[str] = Field(default=None, description="auto|pt-BR|en")


class RealtimeEventIn(BaseModel):
    session_id: str
    event_type: str
    client_event_id: Optional[str] = None
    role: str = Field(description="user|assistant|system")
    content: Optional[str] = None
    created_at: Optional[int] = None
    is_final: Optional[bool] = None
    meta: Optional[Dict[str, Any]] = None


class RealtimeEndReq(BaseModel):
    session_id: str
    ended_at: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


class RealtimeGuardReq(BaseModel):
    thread_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=4000)


# =========================
# Realtime Voice Normalization
# =========================
# The OpenAI Realtime API supports a restricted set of voice ids.
# Normalize legacy/invalid voice ids to a safe default ("cedar").


REALTIME_VOICE_SUPPORTED = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}


REALTIME_VOICE_ALIASES = {
    # legacy -> supported
    "nova": "cedar",
    "onyx": "echo",
    "fable": "sage",
    "shimmer": "shimmer",
    "echo": "echo",
    "alloy": "alloy",
}


def normalize_realtime_voice(voice: str | None, default: str = "cedar") -> str:
    if not voice:
        return default
    v = str(voice).strip().lower()
    if v in REALTIME_VOICE_SUPPORTED:
        return v
    if v in REALTIME_VOICE_ALIASES:
        return REALTIME_VOICE_ALIASES[v]
    return default


def build_realtime_pwa_error_payload(
    *,
    code: str = "REALTIME_CONNECTION_FAILED",
    message: str | None = None,
    detail: str | None = None,
    status_code: int | None = None,
) -> Dict[str, Any]:
    """Premium, user-safe error payload for PWA Realtime failures.

    AO60A only introduces the helper. AO60C will wire it into the frontend/API
    diagnostic path so users stop seeing only "Failed to fetch".
    """

    safe_code = str(code or "REALTIME_CONNECTION_FAILED").strip() or "REALTIME_CONNECTION_FAILED"
    safe_message = (
        message
        or "Não consegui abrir a voz em tempo real agora. O chat continua funcionando normalmente."
    )
    safe_detail = (
        detail
        or "A conexão de voz não foi concluída. Tente novamente em alguns segundos ou continue por texto."
    )

    payload: Dict[str, Any] = {
        "ok": False,
        "code": safe_code,
        "message": safe_message,
        "detail": safe_detail,
        "fallback": "text_chat",
    }
    if status_code is not None:
        payload["status_code"] = int(status_code)
    return payload
