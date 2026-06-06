# ORKIO_AO66R_HF5_REALTIME_SESSION_BUILDER
"""Realtime session payload builder for ORKIO API.

Purpose:
- Keep app/main.py lean.
- Keep app/routes/realtime.py focused on routing/persistence.
- Centralize OpenAI Realtime session config: voice, STT, VAD, create_response and payload shape.

AO66R-HF5 premium decision:
- For ORKIO voice-to-voice, server_vad.create_response must be True.
- When create_response is False, OpenAI can transcribe user audio but will not automatically create an assistant response/audio turn.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_text(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    text = str(raw).strip()
    if not text:
        return default
    if len(text) >= 2 and ((text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")):
        text = text[1:-1].strip()
    return text or default


def resolve_realtime_create_response(
    *,
    summit_runtime: bool = False,
    explicit: Optional[bool] = None,
) -> bool:
    """Resolve VAD auto-response behavior.

    Critical:
    - The production bug we are fixing is create_response=False during Summit/runtime mode.
    - For voice-to-voice UX, we need the Realtime API to create a response automatically
      after server VAD detects the user's turn end.
    - Keep an emergency env kill-switch for rollback without code revert.
    """

    forced_off = _env_flag("OPENAI_REALTIME_CREATE_RESPONSE_FORCE_OFF", False)
    if forced_off:
        return False

    forced_on = _env_flag("OPENAI_REALTIME_CREATE_RESPONSE_FORCE_ON", True)
    if forced_on:
        return True

    if explicit is not None:
        return bool(explicit)

    # Safe product default for ORKIO Realtime Voice.
    return True


def resolve_realtime_transcription_model() -> str:
    """Prefer stronger PT-BR transcription by default."""

    return _env_text(
        "OPENAI_REALTIME_TRANSCRIBE_MODEL",
        _env_text("OPENAI_STT_MODEL", "gpt-4o-transcribe"),
    )


def build_openai_realtime_session_config(
    *,
    model: str,
    voice: str,
    instructions: Optional[str],
    resolved_language: Optional[str],
    summit_runtime: bool = False,
    explicit_create_response: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build the OpenAI Realtime session config."""

    create_response = resolve_realtime_create_response(
        summit_runtime=summit_runtime,
        explicit=explicit_create_response,
    )

    session_cfg: Dict[str, Any] = {
        "type": "realtime",
        "model": model,
        "audio": {
            "output": {"voice": voice},
            "input": {
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": create_response,
                },
                "transcription": {
                    **({"language": resolved_language} if resolved_language else {}),
                    "model": resolve_realtime_transcription_model(),
                },
            },
        },
    }

    clean_instructions = str(instructions or "").strip()
    if clean_instructions:
        session_cfg["instructions"] = clean_instructions

    return session_cfg


def build_openai_realtime_client_secret_payload(
    *,
    ttl_seconds: int,
    model: str,
    voice: str,
    instructions: Optional[str],
    resolved_language: Optional[str],
    summit_runtime: bool = False,
    explicit_create_response: Optional[bool] = None,
) -> Dict[str, Any]:
    """Build payload for POST /v1/realtime/client_secrets."""

    ttl = int(ttl_seconds or 600)
    session_cfg = build_openai_realtime_session_config(
        model=model,
        voice=voice,
        instructions=instructions,
        resolved_language=resolved_language,
        summit_runtime=summit_runtime,
        explicit_create_response=explicit_create_response,
    )
    return {
        "expires_after": {"anchor": "created_at", "seconds": ttl},
        "session": session_cfg,
    }


def realtime_session_debug_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a safe snapshot for logs without exposing secrets."""

    try:
        session = dict(payload.get("session") or {})
        audio = dict(session.get("audio") or {})
        input_audio = dict(audio.get("input") or {})
        turn_detection = dict(input_audio.get("turn_detection") or {})
        transcription = dict(input_audio.get("transcription") or {})
        output_audio = dict(audio.get("output") or {})
        return {
            "model": session.get("model"),
            "voice": output_audio.get("voice"),
            "create_response": turn_detection.get("create_response"),
            "turn_detection_type": turn_detection.get("type"),
            "transcription_model": transcription.get("model"),
            "transcription_language": transcription.get("language"),
            "has_instructions": bool(str(session.get("instructions") or "").strip()),
            "ttl_seconds": ((payload.get("expires_after") or {}).get("seconds")),
        }
    except Exception:
        return {"snapshot_error": True}
