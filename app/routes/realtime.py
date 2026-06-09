# ORKIO_AO64D_HF4_BACKEND_REALTIME_NO_HARD_TIMEBOX_ESG_ADVISORY_SAFE
# Backend recovery + Realtime client_secret GA payload + JSON serialization + no hard public timebox for app/routes/realtime.py
#
# PURPOSE
# Restore Python syntax and FastAPI router boot after a frontend React hook was
# accidentally pasted into app/routes/realtime.py.
#
# SCOPE
# - Backend only.
# - Exposes build_realtime_router(deps), expected by app/main.py.
# - Keeps /api/realtime/start, /api/realtime/end, /api/realtime/events:batch,
#   /api/realtime/guard and /api/realtime/{session_id} alive.
# - Does not modify frontend, AppConsole, WebRTC, SDP or DataChannel.
# - Converts hard public timebox/cooldown into advisory-only ESG guidance.
#
# IMPORTANT
# This is a safe recovery router, not a premium refactor. Its first job is to
# make the API boot again. After backend health is restored, compare with Git
# history and replace with the last known-good full router when available.

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


try:
    from sqlalchemy import select  # type: ignore
except Exception:  # pragma: no cover
    select = None  # type: ignore


try:
    from sqlalchemy.orm import Session  # type: ignore
except Exception:  # pragma: no cover
    Session = Any  # type: ignore


try:
    from app.runtime.realtime_support import (  # type: ignore
        RealtimeClientSecretReq,
        RealtimeStartReq,
        RealtimeEventIn,
        RealtimeEndReq,
        RealtimeGuardReq,
        normalize_realtime_voice,
    )
except Exception:  # pragma: no cover
    class RealtimeClientSecretReq(BaseModel):
        model: Optional[str] = None
        voice: Optional[str] = None
        ttl_seconds: Optional[int] = 120
        mode: Optional[str] = None
        response_profile: Optional[str] = None
        language_profile: Optional[str] = None
        language: Optional[str] = None
        agent_id: Optional[str] = None
        thread_id: Optional[str] = None

    class RealtimeStartReq(BaseModel):
        agent_id: Optional[str] = None
        thread_id: Optional[str] = None
        voice: Optional[str] = None
        model: Optional[str] = None
        ttl_seconds: Optional[int] = 120
        mode: Optional[str] = None
        response_profile: Optional[str] = None
        language_profile: Optional[str] = None
        language: Optional[str] = None

    class RealtimeEventIn(BaseModel):
        name: Optional[str] = None
        event: Optional[str] = None
        type: Optional[str] = None
        meta: Optional[Dict[str, Any]] = None
        payload: Optional[Dict[str, Any]] = None
        ts: Optional[Any] = None

    class RealtimeEndReq(BaseModel):
        session_id: Optional[str] = None
        reason: Optional[str] = None
        meta: Optional[Dict[str, Any]] = None

    class RealtimeGuardReq(BaseModel):
        thread_id: Optional[str] = None
        message: Optional[str] = None

    def normalize_realtime_voice(raw: Any, default: str = "cedar") -> str:
        voice = str(raw or "").strip().lower()
        allowed = {
            "alloy", "ash", "ballad", "cedar", "coral", "echo", "fable",
            "marin", "nova", "onyx", "sage", "shimmer", "verse",
        }
        aliases = {"marine": "marin"}
        voice = aliases.get(voice, voice)
        return voice if voice in allowed else default


try:
    from app.runtime.realtime_session_builder import (  # type: ignore
        build_openai_realtime_client_secret_payload,
        realtime_session_debug_snapshot,
    )
except Exception:  # pragma: no cover
    build_openai_realtime_client_secret_payload = None  # type: ignore

    def realtime_session_debug_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "has_payload": bool(payload),
            "model": payload.get("model") or payload.get("session", {}).get("model"),
            "voice": payload.get("voice") or payload.get("session", {}).get("voice"),
        }


class RealtimeEventsBatchReq(BaseModel):
    session_id: str
    events: List[RealtimeEventIn] = []


def _now_ts() -> int:
    return int(time.time())


def _new_id(prefix: str = "rt") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(str(os.getenv(name, str(default))).strip())
        return value if value > 0 else default
    except Exception:
        return default


REALTIME_PUBLIC_BETA_MAX_SECONDS = _positive_int_env(
    "ORKIO_REALTIME_PUBLIC_BETA_MAX_SECONDS",
    120,
)
REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS = _positive_int_env(
    "ORKIO_REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS",
    600,
)

# AO64D-HF4:
# Public/user time limits are no longer enforced as hard blockers in this recovery
# router. We still expose advisory metadata so the frontend/product can recommend
# shorter sessions for cost, data, battery and ESG efficiency without interrupting
# a useful voice conversation.
REALTIME_ADVISORY_RECOMMENDED_SECONDS = _positive_int_env(
    "ORKIO_REALTIME_ADVISORY_RECOMMENDED_SECONDS",
    120,
)
REALTIME_CLIENT_SECRET_TTL_SECONDS = _positive_int_env(
    "ORKIO_REALTIME_CLIENT_SECRET_TTL_SECONDS",
    3600,
)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    except Exception:
        return default


def _json_safe(value: Any) -> Any:
    """Convert SDK/Pydantic/SQLAlchemy-ish objects into JSON-safe primitives.

    AO64D-HF4:
    FastAPI/Pydantic v2 can crash during response serialization when an SDK model
    or partially mocked serializer object is returned inside a dict:
    TypeError: 'MockValSer' object cannot be converted to 'SchemaSerializer'.
    This helper prevents leaking those objects into route responses.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    # Pydantic v2 / OpenAI SDK models.
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                if method_name == "model_dump":
                    return _json_safe(method(mode="json"))
                return _json_safe(method())
            except Exception:
                pass

    # Some SDK objects expose to_dict/to_json.
    method = getattr(value, "to_dict", None)
    if callable(method):
        try:
            return _json_safe(method())
        except Exception:
            pass

    method = getattr(value, "to_json", None)
    if callable(method):
        try:
            return _json_safe(json.loads(method()))
        except Exception:
            pass

    # Fallback to public attributes only. Avoid private serializer internals.
    try:
        attrs = {
            str(k): _json_safe(v)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }
        if attrs:
            return attrs
    except Exception:
        pass

    return str(value)


def _json_response(payload: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=_json_safe(payload), status_code=status_code)


def _build_esg_usage_advisory() -> Dict[str, Any]:
    recommended = max(30, int(REALTIME_ADVISORY_RECOMMENDED_SECONDS or 120))
    return {
        "enabled": True,
        "mode": "advisory_only",
        "recommended_seconds": recommended,
        "hard_limit_enforced": False,
        "cooldown_enforced": False,
        "title": "Uso consciente da voz em tempo real",
        "message": (
            "Para economizar créditos, dados móveis, bateria e energia, recomendamos "
            f"sessões de voz objetivas de até {recommended} segundos quando possível. "
            "A conversa não será interrompida automaticamente por essa recomendação."
        ),
        "esg": {
            "cost_efficiency": True,
            "data_saving": True,
            "battery_saving": True,
            "energy_saving": True,
        },
    }


def _is_admin_user(user: Any, db_user: Any = None) -> bool:
    roles = {"admin", "owner", "superadmin", "super_admin", "founder", "dev", "developer"}
    user_role = str(_safe_getattr(user, "role", "") or "").strip().lower()
    db_role = str(_safe_getattr(db_user, "role", "") or "").strip().lower()
    user_scope = str(_safe_getattr(user, "scope", "") or "").strip().lower()
    db_scope = str(_safe_getattr(db_user, "scope", "") or "").strip().lower()
    user_email = str(_safe_getattr(user, "email", "") or _safe_getattr(user, "user_email", "") or "").strip().lower()
    db_email = str(_safe_getattr(db_user, "email", "") or _safe_getattr(db_user, "user_email", "") or "").strip().lower()

    admin_email_env = ",".join([
        os.getenv("ORKIO_SUPER_ADMIN_EMAILS", ""),
        os.getenv("ORKIO_ADMIN_EMAILS", ""),
        os.getenv("SUPER_ADMIN_EMAILS", ""),
        os.getenv("ADMIN_EMAILS", ""),
        os.getenv("VITE_ADMIN_EMAILS", ""),
        "daniel@patroai.com",
    ])
    admin_emails = {
        item.strip().lower()
        for item in admin_email_env.split(",")
        if item.strip()
    }

    return bool(
        user_role in roles
        or db_role in roles
        or user_scope in {"internal", "staff", "admin", "superadmin", "super_admin"}
        or db_scope in {"internal", "staff", "admin", "superadmin", "super_admin"}
        or bool(_safe_getattr(user, "is_admin", False))
        or bool(_safe_getattr(user, "admin", False))
        or bool(_safe_getattr(user, "super_admin", False))
        or bool(_safe_getattr(user, "is_super_admin", False))
        or bool(_safe_getattr(db_user, "is_admin", False))
        or bool(_safe_getattr(db_user, "admin", False))
        or bool(_safe_getattr(db_user, "super_admin", False))
        or bool(_safe_getattr(db_user, "is_super_admin", False))
        or (user_email and user_email in admin_emails)
        or (db_email and db_email in admin_emails)
    )


def _default_current_user() -> Dict[str, Any]:
    raise HTTPException(status_code=401, detail="Not authenticated")


def _default_db() -> None:
    return None


def _resolve_org_safe(deps: SimpleNamespace, user: Any, x_org_slug: Optional[str]) -> str:
    resolver = getattr(deps, "_resolve_org", None)
    if callable(resolver):
        try:
            return str(resolver(user, x_org_slug) or "public")
        except Exception:
            pass

    org = (
        x_org_slug
        or _safe_getattr(user, "org_slug", None)
        or _safe_getattr(user, "org", None)
        or "public"
    )
    return str(org or "public").strip() or "public"


def _lookup_db_user(deps: SimpleNamespace, db: Any, user: Any, org: str) -> Any:
    User = getattr(deps, "User", None)
    uid = _safe_getattr(user, "sub", None) or _safe_getattr(user, "id", None)
    if db is None or User is None or select is None or not uid:
        return None

    try:
        return (
            db.execute(
                select(User).where(
                    User.id == uid,
                    User.org_slug == org,
                )
            )
            .scalar_one_or_none()
        )
    except Exception:
        return None


def _build_basic_realtime_payload(
    *,
    model: Optional[str],
    voice: Optional[str],
    ttl_seconds: Optional[int],
    instructions: Optional[str],
    resolved_language: Optional[str],
) -> Dict[str, Any]:
    # AO64D-HF2_REALTIME_CLIENT_SECRET_GA_PAYLOAD
    # Fallback payload aligned with the GA Realtime client_secrets shape:
    # - expires_after at the top level
    # - session.type = "realtime"
    # - output voice under session.audio.output.voice
    # - VAD/transcription under session.audio.input
    selected_model = (
        str(model or "").strip()
        or os.getenv("OPENAI_REALTIME_MODEL", "").strip()
        or "gpt-4o-realtime-preview"
    )
    selected_voice = normalize_realtime_voice(
        voice or os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"),
        default=os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"),
    )
    ttl = max(10, min(7200, int(ttl_seconds or 120)))
    language = str(resolved_language or "pt").strip().lower() or "pt"

    return {
        "expires_after": {
            "anchor": "created_at",
            "seconds": ttl,
        },
        "session": {
            "type": "realtime",
            "model": selected_model,
            "instructions": instructions
            or "Você é Orkio, agente executivo da PatroAI. Responda em português do Brasil, com objetividade e segurança.",
            "output_modalities": ["audio"],
            "audio": {
                "output": {
                    "voice": selected_voice,
                },
                "input": {
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.72,
                        "prefix_padding_ms": 500,
                        "silence_duration_ms": 1800,
                        "create_response": True,
                        "interrupt_response": True,
                    },
                    "transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        "language": language,
                    },
                },
            },
        },
    }


def _payload_looks_ga_compatible(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    session = payload.get("session")
    if not isinstance(session, dict):
        return False

    audio = session.get("audio")
    if not isinstance(audio, dict):
        return False

    audio_input = audio.get("input")
    audio_output = audio.get("output")
    if not isinstance(audio_input, dict) or not isinstance(audio_output, dict):
        return False

    if not audio_output.get("voice"):
        return False

    if not isinstance(audio_input.get("turn_detection"), dict):
        return False

    # expires_after is the GA client secret TTL contract. Without it, the SDK/REST
    # may still default, but for this recovery patch we keep it explicit.
    if not isinstance(payload.get("expires_after"), dict):
        return False

    return True


def _normalize_realtime_payload_for_ga(
    payload: Any,
    *,
    model: Optional[str],
    voice: Optional[str],
    ttl_seconds: Optional[int],
    instructions: Optional[str],
    resolved_language: Optional[str],
) -> Dict[str, Any]:
    # If a local builder already emits a GA-compatible payload, keep it.
    if _payload_looks_ga_compatible(payload):
        return payload

    # Otherwise, rebuild the minimal known-good GA shape. This protects recovery
    # from stale beta/legacy builders or the simplified ttl_seconds/modalities shape.
    return _build_basic_realtime_payload(
        model=model,
        voice=voice,
        ttl_seconds=ttl_seconds,
        instructions=instructions,
        resolved_language=resolved_language,
    )


def _extract_secret_value(secret_obj: Any) -> tuple[Optional[str], Any]:
    if secret_obj is None:
        return None, None

    safe_obj = _json_safe(secret_obj)

    if isinstance(safe_obj, dict):
        client_secret = safe_obj.get("client_secret") if isinstance(safe_obj.get("client_secret"), dict) else {}
        return (
            safe_obj.get("value")
            or client_secret.get("value")
            or safe_obj.get("secret")
            or safe_obj.get("client_secret_value"),
            safe_obj.get("session"),
        )

    value = getattr(secret_obj, "value", None)
    session = getattr(secret_obj, "session", None)
    return value, _json_safe(session)


def _build_instructions(deps: SimpleNamespace, *, mode: str, response_profile: str, language_profile: str) -> str:
    builder = getattr(deps, "build_summit_instructions", None)
    sensitive_guard = getattr(deps, "_sensitive_guard_instruction", None)

    instructions = ""
    if callable(builder):
        try:
            instructions = str(
                builder(
                    mode=mode,
                    agent_instructions=(
                        "IDENTIDADE OBRIGATÓRIA DO REALTIME\n"
                        "- Você é Orkio, agente da plataforma PatroAI.\n"
                        "- Responda sempre em português do Brasil.\n"
                        "- Seja claro, executivo, útil e seguro.\n"
                    ),
                    language_profile=language_profile,
                    response_profile=response_profile,
                )
                or ""
            ).strip()
        except Exception:
            instructions = ""

    if not instructions:
        instructions = (
            "Você é Orkio, agente executivo da plataforma PatroAI. "
            "Responda sempre em português do Brasil, com clareza, objetividade e segurança."
        )

    if callable(sensitive_guard):
        try:
            guard = str(sensitive_guard() or "").strip()
            if guard:
                instructions = f"{instructions}\n\n{guard}"
        except Exception:
            pass

    return instructions


async def _mint_client_secret(
    deps: SimpleNamespace,
    body: Any,
    *,
    instructions: str,
    resolved_language: str,
    summit_runtime: bool = False,
    logger: logging.Logger,
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")

    model = str(_safe_getattr(body, "model", "") or "").strip() or None
    voice = normalize_realtime_voice(
        _safe_getattr(body, "voice", None) or os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"),
        default=os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"),
    )
    ttl_seconds = int(_safe_getattr(body, "ttl_seconds", None) or REALTIME_PUBLIC_BETA_MAX_SECONDS)

    payload: Dict[str, Any]
    if callable(build_openai_realtime_client_secret_payload):
        try:
            payload = build_openai_realtime_client_secret_payload(
                ttl_seconds=ttl_seconds,
                model=model,
                voice=voice,
                instructions=instructions,
                resolved_language=resolved_language,
                summit_runtime=summit_runtime,
            )
        except Exception:
            payload = _build_basic_realtime_payload(
                model=model,
                voice=voice,
                ttl_seconds=ttl_seconds,
                instructions=instructions,
                resolved_language=resolved_language,
            )
    else:
        payload = _build_basic_realtime_payload(
            model=model,
            voice=voice,
            ttl_seconds=ttl_seconds,
            instructions=instructions,
            resolved_language=resolved_language,
        )

    payload = _normalize_realtime_payload_for_ga(
        payload,
        model=model,
        voice=voice,
        ttl_seconds=ttl_seconds,
        instructions=instructions,
        resolved_language=resolved_language,
    )

    try:
        logger.warning(
            "AO64D_HF4_REALTIME_CLIENT_SECRET_GA_PAYLOAD %s",
            json.dumps(realtime_session_debug_snapshot(payload), ensure_ascii=False, sort_keys=True),
        )
    except Exception:
        pass

    OpenAI = getattr(deps, "OpenAI", None)
    if OpenAI is not None:
        try:
            client = OpenAI(api_key=api_key)
            secret_obj = client.realtime.client_secrets.create(**payload)  # type: ignore[attr-defined]
            value, session = _extract_secret_value(secret_obj)
            if value:
                return {"value": value, "session": session}
        except Exception as sdk_err:
            try:
                logger.warning("AO64D_REALTIME_RECOVERY_SDK_SECRET_FAILED %s", sdk_err)
            except Exception:
                pass

    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.openai.com/v1/realtime/client_secrets",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        value, session = _extract_secret_value(data)
        if not value:
            raise RuntimeError("Realtime client secret missing in REST response")
        return {"value": value, "session": session, "sdk_fallback": True}
    except Exception as rest_err:
        try:
            logger.exception("AO64D_REALTIME_RECOVERY_REST_SECRET_FAILED %s", rest_err)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Failed to mint Realtime client secret")


def _maybe_persist_realtime_session(
    deps: SimpleNamespace,
    db: Any,
    *,
    session_id: str,
    org: str,
    user_id: Optional[str],
    thread_id: Optional[str],
    started_at: int,
    mode: str,
) -> None:
    RealtimeSession = getattr(deps, "RealtimeSession", None)
    if db is None or RealtimeSession is None:
        return

    try:
        rs = RealtimeSession()
        for key, value in {
            "id": session_id,
            "org_slug": org,
            "user_id": user_id,
            "thread_id": thread_id,
            "started_at": started_at,
            "mode": mode,
            "status": "active",
        }.items():
            try:
                setattr(rs, key, value)
            except Exception:
                pass
        db.add(rs)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _maybe_mark_realtime_session_ended(
    deps: SimpleNamespace,
    db: Any,
    *,
    session_id: Optional[str],
    ended_at: int,
    reason: Optional[str],
) -> bool:
    if not session_id:
        return False

    RealtimeSession = getattr(deps, "RealtimeSession", None)
    if db is None or RealtimeSession is None or select is None:
        return False

    try:
        rs = (
            db.execute(select(RealtimeSession).where(RealtimeSession.id == session_id))
            .scalar_one_or_none()
        )
        if not rs:
            return False

        for key, value in {
            "ended_at": ended_at,
            "status": "ended",
            "end_reason": reason or "client_end",
            "reason": reason or "client_end",
        }.items():
            try:
                setattr(rs, key, value)
            except Exception:
                pass
        db.add(rs)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def build_realtime_router(deps: SimpleNamespace) -> APIRouter:
    """Build a safe Realtime router using injected app/main.py dependencies.

    This function intentionally accepts partial deps so that backend import/boot
    does not fail during recovery. Runtime errors are converted to explicit HTTP
    responses instead of crashing Uvicorn at startup.
    """

    router = APIRouter()
    logger = getattr(deps, "logger", None) or logging.getLogger("orkio.realtime.recovery")

    get_current_user = getattr(deps, "get_current_user", None) or _default_current_user
    get_db = getattr(deps, "get_db", None) or _default_db

    @router.post("/api/realtime/guard")
    def realtime_guard(
        body: RealtimeGuardReq,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> Dict[str, Any]:
        org = _resolve_org_safe(deps, user, x_org_slug)
        guard_fn = getattr(deps, "_guard_realtime_message", None)

        blocked_reply = None
        if callable(guard_fn):
            try:
                blocked_reply = guard_fn(_safe_getattr(body, "message", ""))
            except Exception:
                blocked_reply = None

        return {
            "ok": True,
            "blocked": bool(blocked_reply),
            "reply": blocked_reply,
            "org": org,
            "recovery_router": True,
        }

    @router.post("/api/realtime/client_secret")
    async def realtime_client_secret(
        body: RealtimeClientSecretReq,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> Dict[str, Any]:
        org = _resolve_org_safe(deps, user, x_org_slug)
        mode = str(_safe_getattr(body, "mode", "") or "platform").strip().lower()
        response_profile = str(_safe_getattr(body, "response_profile", "") or "natural").strip().lower()
        language_profile = str(
            _safe_getattr(body, "language_profile", None)
            or _safe_getattr(body, "language", None)
            or "pt"
        ).strip().lower() or "pt"

        instructions = _build_instructions(
            deps,
            mode=mode,
            response_profile=response_profile,
            language_profile=language_profile,
        )
        secret = await _mint_client_secret(
            deps,
            body,
            instructions=instructions,
            resolved_language=language_profile,
            summit_runtime=(mode == "summit"),
            logger=logger,
        )
        return _json_response({
            **_json_safe(secret),
            "org": org,
            "recovery_router": True,
            "serialization_safe": "AO64D_HF4",
        })

    @router.post("/api/realtime/start")
    async def realtime_start(
        body: RealtimeStartReq,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> Dict[str, Any]:
        org = _resolve_org_safe(deps, user, x_org_slug)
        db_user = _lookup_db_user(deps, db, user, org)
        uid = str(_safe_getattr(user, "sub", None) or _safe_getattr(user, "id", "") or "").strip() or None
        is_admin = _is_admin_user(user, db_user)

        mode = str(_safe_getattr(body, "mode", "") or "platform").strip().lower()
        response_profile = str(_safe_getattr(body, "response_profile", "") or "natural").strip().lower()
        language_profile = str(
            _safe_getattr(body, "language_profile", None)
            or _safe_getattr(body, "language", None)
            or "pt"
        ).strip().lower() or "pt"

        # AO64D-HF4_NO_HARD_TIMEBOX_ESG_ADVISORY
        # The Realtime client secret still needs a practical TTL, but the product
        # no longer enforces a hard user-facing session timebox/cooldown here.
        ttl_requested = int(
            _safe_getattr(body, "ttl_seconds", None)
            or REALTIME_CLIENT_SECRET_TTL_SECONDS
        )
        effective_ttl = max(60, min(ttl_requested, REALTIME_CLIENT_SECRET_TTL_SECONDS))

        # Mutate body only when possible, preserving existing Pydantic object contract.
        try:
            body.ttl_seconds = effective_ttl
        except Exception:
            pass

        instructions = _build_instructions(
            deps,
            mode=mode,
            response_profile=response_profile,
            language_profile=language_profile,
        )

        secret = await _mint_client_secret(
            deps,
            body,
            instructions=instructions,
            resolved_language=language_profile,
            summit_runtime=(mode == "summit"),
            logger=logger,
        )

        session_id = _new_id("rt")
        thread_id = str(_safe_getattr(body, "thread_id", "") or "").strip() or _new_id("thread")
        started_at = _now_ts()

        _maybe_persist_realtime_session(
            deps,
            db,
            session_id=session_id,
            org=org,
            user_id=uid,
            thread_id=thread_id,
            started_at=started_at,
            mode=mode,
        )

        # AO64D-HF4:
        # Hard timebox/cooldown disabled for all users in this recovery router.
        # Admin is still identified for logs/governance, but non-admin users are
        # no longer interrupted by max_seconds/cooldown here.
        timebox = {
            "limited": False,
            "admin_bypass": bool(is_admin),
            "bypass": "admin" if is_admin else "no_hard_timebox",
            "max_seconds": None,
            "remaining_seconds": None,
            "cooldown_seconds": 0,
            "advisory_only": True,
            "recommended_seconds": REALTIME_ADVISORY_RECOMMENDED_SECONDS,
        }
        usage_advisory = _build_esg_usage_advisory()

        try:
            logger.warning(
                "AO64D_HF4_REALTIME_START_OK_NO_HARD_TIMEBOX user_id=%s org=%s session_id=%s thread_id=%s admin=%s timebox=%s",
                uid,
                org,
                session_id,
                thread_id,
                bool(is_admin),
                json.dumps(timebox, ensure_ascii=False, sort_keys=True),
            )
        except Exception:
            pass

        safe_secret = _json_safe(secret)
        return _json_response({
            "ok": True,
            "session_id": session_id,
            "thread_id": thread_id,
            "client_secret": safe_secret,
            "client_secret_value": safe_secret.get("value") if isinstance(safe_secret, dict) else None,
            "value": safe_secret.get("value") if isinstance(safe_secret, dict) else None,
            "timebox": _json_safe(timebox),
            "usage_advisory": _json_safe(usage_advisory),
            "started_at": started_at,
            "recovery_router": True,
            "serialization_safe": "AO64D_HF4",
            "timebox_policy": "advisory_only_esg",
        })

    @router.post("/api/realtime/events:batch")
    def realtime_events_batch(
        body: RealtimeEventsBatchReq,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> Dict[str, Any]:
        org = _resolve_org_safe(deps, user, x_org_slug)
        events = list(_safe_getattr(body, "events", []) or [])

        try:
            logger.warning(
                "AO64D_REALTIME_RECOVERY_EVENTS_BATCH org=%s session_id=%s count=%s names=%s",
                org,
                _safe_getattr(body, "session_id", None),
                len(events),
                ",".join(
                    [
                        str(
                            _safe_getattr(ev, "name", None)
                            or _safe_getattr(ev, "event", None)
                            or _safe_getattr(ev, "type", None)
                            or "event"
                        )
                        for ev in events[:20]
                    ]
                ),
            )
        except Exception:
            pass

        return {
            "ok": True,
            "session_id": _safe_getattr(body, "session_id", None),
            "received": len(events),
            "recovery_router": True,
        }

    @router.get("/api/realtime/{session_id}")
    def realtime_get_session(
        session_id: str,
        finals_only: Optional[bool] = False,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> JSONResponse:
        """Compatibility read endpoint used by the frontend after Realtime close.

        The recovery router may not have access to the full persisted event/final
        transcript model. Returning 200 prevents noisy 405 loops while preserving
        a safe empty structure. Full transcript recovery should be restored from
        the last known-good router in a later premium patch.
        """
        org = _resolve_org_safe(deps, user, x_org_slug)
        session_id_clean = str(session_id or "").strip()
        snapshot = None

        try:
            snapshot_fn = getattr(deps, "get_realtime_session_snapshot", None)
            if callable(snapshot_fn):
                snapshot = snapshot_fn(session_id_clean, org=org, db=db)
        except Exception:
            snapshot = None

        payload = {
            "ok": True,
            "session_id": session_id_clean,
            "org": org,
            "finals_only": bool(finals_only),
            "session": _json_safe(snapshot) if snapshot else None,
            "finals": {
                "user_text": "",
                "assistant_text": "",
                "turns": [],
            },
            "recovery_router": True,
            "serialization_safe": "AO64D_HF4",
            "compatibility_endpoint": "GET /api/realtime/{session_id}",
        }

        try:
            logger.warning(
                "AO64D_HF4_REALTIME_GET_SESSION_COMPAT org=%s session_id=%s finals_only=%s has_snapshot=%s",
                org,
                session_id_clean,
                bool(finals_only),
                bool(snapshot),
            )
        except Exception:
            pass

        return _json_response(payload)

    @router.post("/api/realtime/end")
    def realtime_end(
        body: RealtimeEndReq,
        x_org_slug: Optional[str] = Header(default=None),
        user: Any = Depends(get_current_user),
        db: Any = Depends(get_db),
    ) -> Dict[str, Any]:
        org = _resolve_org_safe(deps, user, x_org_slug)
        session_id = str(_safe_getattr(body, "session_id", "") or "").strip() or None
        reason = str(_safe_getattr(body, "reason", "") or "client_end").strip() or "client_end"
        ended_at = _now_ts()

        persisted = _maybe_mark_realtime_session_ended(
            deps,
            db,
            session_id=session_id,
            ended_at=ended_at,
            reason=reason,
        )

        try:
            logger.warning(
                "AO64D_REALTIME_RECOVERY_END org=%s session_id=%s reason=%s persisted=%s",
                org,
                session_id,
                reason,
                bool(persisted),
            )
        except Exception:
            pass

        return {
            "ok": True,
            "session_id": session_id,
            "ended_at": ended_at,
            "persisted": bool(persisted),
            "recovery_router": True,
        }

    return router


__all__ = ["build_realtime_router"]
