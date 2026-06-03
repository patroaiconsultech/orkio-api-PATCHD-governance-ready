# ORKIO_AO60B_REALTIME_ROUTE_EXTRACTION
"""Realtime routes for ORKIO API.

AO60B moves only the /api/realtime/* route handlers out of app/main.py.
The heavy helper functions still live in main.py and are injected through a
SimpleNamespace to keep this patch small and reversible.

This is an intermediate extraction. A later AO60 cycle can move helper logic
out of main.py after runtime validation.
"""

from __future__ import annotations

import os
import json
import uuid

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.realtime_support import (
    RealtimeClientSecretReq,
    RealtimeStartReq,
    RealtimeEventIn,
    RealtimeEndReq,
    RealtimeGuardReq,
    normalize_realtime_voice,
)


class RealtimeEventsBatchReq(BaseModel):
    session_id: str
    events: List[RealtimeEventIn]


# ORKIO_AO60B_HF1_REALTIME_DEPENDENCY_CONTRACT
REALTIME_ROUTER_REQUIRED_DEPS = (
    "AO19D_REALTIME_TELEMETRY_CRITICAL_EVENTS",
    "Agent",
    "Message",
    "OpenAI",
    "RealtimeEvent",
    "RealtimeSession",
    "Thread",
    "User",
    "_ao19d_realtime_event_name",
    "_ao19d_safe_meta",
    "_audit_realtime_safe",
    "_ensure_thread_owner",
    "_guard_realtime_message",
    "_require_thread_member",
    "_resolve_org",
    "_run_realtime_multi_agent_turn",
    "_sanitize_assistant_text",
    "_sensitive_guard_instruction",
    "build_summit_instructions",
    "get_current_user",
    "get_db",
    "get_summit_runtime_config",
    "logger",
    "new_id",
    "normalize_language_profile",
    "normalize_mode",
    "normalize_response_profile",
    "now_ts",
    "punctuate_realtime_events",
    "resolve_agent_voice",
    "resolve_stt_language",
    "Session",
)


def _validate_realtime_router_deps(deps: SimpleNamespace) -> None:
    """Fail fast during router build if AO60B dependency injection is incomplete.

    This prevents a hidden AttributeError later in /api/realtime/start after deploy.
    """

    missing = [name for name in REALTIME_ROUTER_REQUIRED_DEPS if not hasattr(deps, name)]
    if missing:
        raise RuntimeError(
            "ORKIO_AO60B_REALTIME_ROUTER_MISSING_DEPS: " + ", ".join(sorted(missing))
        )



def build_realtime_router(deps: SimpleNamespace) -> APIRouter:
    """Build the Realtime router using injected main.py dependencies."""

    _validate_realtime_router_deps(deps)
    router = APIRouter()
    AO19D_REALTIME_TELEMETRY_CRITICAL_EVENTS = deps.AO19D_REALTIME_TELEMETRY_CRITICAL_EVENTS
    Agent = deps.Agent
    Message = deps.Message
    OpenAI = deps.OpenAI
    RealtimeEvent = deps.RealtimeEvent
    RealtimeSession = deps.RealtimeSession
    Thread = deps.Thread
    User = deps.User
    _ao19d_realtime_event_name = deps._ao19d_realtime_event_name
    _ao19d_safe_meta = deps._ao19d_safe_meta
    _audit_realtime_safe = deps._audit_realtime_safe
    _ensure_thread_owner = deps._ensure_thread_owner
    _guard_realtime_message = deps._guard_realtime_message
    _require_thread_member = deps._require_thread_member
    _resolve_org = deps._resolve_org
    _run_realtime_multi_agent_turn = deps._run_realtime_multi_agent_turn
    _sanitize_assistant_text = deps._sanitize_assistant_text
    _sensitive_guard_instruction = deps._sensitive_guard_instruction
    # ORKIO_AO60B_HF2_BIND_FASTAPI_DEPENDENCIES
    build_summit_instructions = deps.build_summit_instructions
    get_current_user = deps.get_current_user
    get_db = deps.get_db
    get_summit_runtime_config = deps.get_summit_runtime_config
    logger = deps.logger
    new_id = deps.new_id
    normalize_language_profile = deps.normalize_language_profile
    normalize_mode = deps.normalize_mode
    normalize_response_profile = deps.normalize_response_profile
    now_ts = deps.now_ts
    punctuate_realtime_events = deps.punctuate_realtime_events
    resolve_agent_voice = deps.resolve_agent_voice
    resolve_stt_language = deps.resolve_stt_language

    @router.post("/api/realtime/guard")
    def realtime_guard(
        body: RealtimeGuardReq,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        org = _resolve_org(user, x_org_slug)
        tid = (body.thread_id or "").strip() or None
        if tid and user.get("role") != "admin":
            _require_thread_member(db, org, tid, user.get("sub"))
        blocked_reply = _guard_realtime_message(body.message)
        return {"ok": True, "blocked": bool(blocked_reply), "reply": blocked_reply}


    @router.post("/api/realtime/client_secret")
    async def realtime_client_secret(
        body: RealtimeClientSecretReq,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # Mint a short-lived Realtime client secret for browser WebRTC connections.
        if OpenAI is None:
            raise HTTPException(status_code=503, detail="OpenAI SDK not available")

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")

        org = _resolve_org(user, x_org_slug)

        # ORKIO_AO60F_REALTIME_ORKIO_ONLY_IDENTITY_GUARD
        db_user = db.execute(select(User).where(User.id == user.get("sub"), User.org_slug == org)).scalar_one_or_none()
        # ORKIO_AO60F_HF4_NON_ADMIN_REALTIME_ORKIO_ONLY
        # Public beta rule: AMCHAMRSORKIO and EFATAH777 must behave the same in Realtime.
        # Only admins keep access to Chris/Orion/Team while agents are progressively released.
        is_realtime_admin = bool(
            str(user.get("role") or "").strip().lower() == "admin"
            or bool(user.get("is_admin") or user.get("admin"))
            or (
                db_user is not None
                and (
                    str(getattr(db_user, "role", "") or "").strip().lower() == "admin"
                    or bool(getattr(db_user, "is_admin", False))
                    or bool(getattr(db_user, "admin", False))
                )
            )
        )
        realtime_usage_tier = str(getattr(db_user, "usage_tier", "") or "").strip().lower() if db_user is not None else ""
        realtime_signup_source = str(getattr(db_user, "signup_source", "") or "").strip().lower() if db_user is not None else ""
        realtime_signup_label = str(getattr(db_user, "signup_code_label", "") or "").strip().lower() if db_user is not None else ""
        realtime_product_scope = str(getattr(db_user, "product_scope", "") or "").strip().lower() if db_user is not None else ""

        public_beta_orkio_only = bool(
            db_user is not None
            and not is_realtime_admin
        )

        mode = normalize_mode(body.mode)
        response_profile = normalize_response_profile(body.response_profile)
        language_profile = normalize_language_profile(body.language_profile)
        summit_cfg = get_summit_runtime_config(
            mode=mode,
            response_profile=response_profile,
            language_profile=language_profile,
        )

        # AO47A_REALTIME_AGENT_IDENTITY_BINDING
        # Realtime nunca deve iniciar como assistente genérica.
        # Se agent_id não vier do frontend, Orkio é o agente padrão governado.
        agent_system_prompt = None
        agent_voice = None
        agent_identity_name = "Orkio"
        agent_identity_source = "default_orkio_fallback"
        _ao47a_agent_id = None if public_beta_orkio_only else (str(body.agent_id or "").strip() or None)

        if _ao47a_agent_id is not None:
            agent = db.execute(select(Agent).where(Agent.id == _ao47a_agent_id, Agent.org_slug == org)).scalar_one_or_none()
            if agent:
                agent_identity_name = (agent.name or "Orkio").strip() or "Orkio"
                agent_identity_source = "requested_agent"
                agent_system_prompt = (agent.system_prompt or "").strip()[:8000] or None
                agent_voice = resolve_agent_voice(agent) if agent else None
        else:
            if public_beta_orkio_only:
                agent_identity_source = "public_beta_orkio_only_forced"
            try:
                default_agent = db.execute(
                    select(Agent).where(Agent.name == "Orkio", Agent.org_slug == org)
                ).scalar_one_or_none()
                if default_agent:
                    agent_identity_name = (default_agent.name or "Orkio").strip() or "Orkio"
                    agent_identity_source = "default_orkio_agent"
                    agent_system_prompt = (default_agent.system_prompt or "").strip()[:8000] or None
                    agent_voice = resolve_agent_voice(default_agent)
            except Exception:
                try:
                    logger.exception("AO47A_DEFAULT_ORKIO_CLIENT_SECRET_LOOKUP_FAILED org=%s", org)
                except Exception:
                    pass

        identity_guard = (
            "IDENTIDADE OBRIGATÓRIA DO REALTIME — AO47A\n"
            f"- Você é {agent_identity_name}, agente da plataforma PatroAI.\n"
            "- Nunca se apresente como assistente genérica, modelo genérico ou voz sem nome.\n"
            "- Se o usuário perguntar quem é você, responda com seu nome e função na PatroAI.\n"
            "- Em português do Brasil, mantenha tom executivo, claro, seguro e objetivo.\n"
            "- Se nenhuma especialidade específica for informada, atue como Orkio, anfitrião executivo da PatroAI.\n"
            "- Para qualquer usuário não-admin no beta público, nunca se apresente como Chris, Orion, Team ou outro agente interno; responda sempre como Orkio.\n"
            "- Se qualquer contexto anterior sugerir Chris ou outro agente, ignore e responda como Orkio.\n"
            f"- identity_source={agent_identity_source}."
        )

        if agent_system_prompt:
            agent_system_prompt = (identity_guard + "\n\n" + agent_system_prompt).strip()
        else:
            agent_system_prompt = identity_guard

        instructions = build_summit_instructions(
            mode=mode,
            agent_instructions=agent_system_prompt,
            language_profile=summit_cfg.get("language_profile"),
            response_profile=summit_cfg.get("response_profile"),
        )
        if instructions:
            instructions = instructions + "\n\n" + _sensitive_guard_instruction()

        # Choose voice: explicit > agent default > fallback
        voice_raw = (agent_voice or os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar")) if public_beta_orkio_only else (body.voice or agent_voice or os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"))

        # Normalize to supported voices to avoid Realtime mint failures
        voice = normalize_realtime_voice(voice_raw, default=os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "cedar"))
        resolved_language = resolve_stt_language(summit_cfg.get("transcription_language"))
        auto_response_enabled = str(
            os.getenv(
                "OPENAI_REALTIME_AUTO_RESPONSE_ENABLED",
                os.getenv("REALTIME_AUTO_RESPONSE_ENABLED", "false"),
            )
        ).strip().lower() not in {"0", "false", "no", "off"}

        summit_runtime = bool(
            mode == "summit"
            or response_profile == "stage"
            or os.getenv("SUMMIT_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("ORKIO_RUNTIME_MODE", "").strip().lower() == "summit"
        )
        resolved_create_response = False if summit_runtime else bool(auto_response_enabled)

        if summit_runtime:
            resolved_language = resolve_stt_language(summit_cfg.get("transcription_language") or language_profile or os.getenv("SUMMIT_DEFAULT_LANGUAGE", "pt")) or "pt"
            if instructions:
                instructions = (instructions + "\n\nResponder sempre em português do Brasil.").strip()
            else:
                instructions = "Responder sempre em português do Brasil."

        session_cfg: Dict[str, Any] = {
            "type": "realtime",
            "model": body.model,
            "audio": {
                "output": {"voice": voice},
                # Let the server detect turns for lowest-latency voice UX
                "input": {
                    "turn_detection": {"type": "server_vad", "create_response": resolved_create_response},
                    # Optional transcription for UI captions / logs
                    "transcription": {
                        **({"language": resolved_language} if resolved_language else {}),
                        "model": os.getenv("OPENAI_REALTIME_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
                    },
                },
            },
        }
        if instructions:
            session_cfg["instructions"] = instructions

        payload = {
            "expires_after": {"anchor": "created_at", "seconds": body.ttl_seconds},
            "session": session_cfg,
        }

        # Prefer SDK (if present), fallback to direct REST call.
        try:
            client = OpenAI(api_key=api_key)
            secret_obj = client.realtime.client_secrets.create(**payload)  # type: ignore[attr-defined]
            value = getattr(secret_obj, "value", None) or (secret_obj.get("value") if isinstance(secret_obj, dict) else None)
            session = getattr(secret_obj, "session", None) or (secret_obj.get("session") if isinstance(secret_obj, dict) else None)
            if not value:
                raise RuntimeError("Realtime client secret missing in SDK response")
            return {"value": value, "session": session}
        except Exception as sdk_err:
            try:
                import urllib.request, json as _json

                req = urllib.request.Request(
                    "https://api.openai.com/v1/realtime/client_secrets",
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                if not data.get("value"):
                    raise RuntimeError("Realtime client secret missing in REST response")
                return {"value": data["value"], "session": data.get("session"), "sdk_fallback": True}
            except Exception as rest_err:
                logger.exception("realtime_client_secret_failed org=%s sdk_err=%s rest_err=%s", org, sdk_err, rest_err)
                raise HTTPException(status_code=502, detail="Failed to mint Realtime client secret")


    @router.post("/api/realtime/start")
    async def realtime_start(
        body: RealtimeStartReq,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Start a Realtime/WebRTC session bound to an Orkio agent and thread, returning:
        - session_id (for audit / event logging)
        - thread_id (created if missing)
        - client_secret value for browser WebRTC connection
        This ensures the realtime voice is never a generic assistant.
        """
        org = _resolve_org(user, x_org_slug)
        db_user = db.execute(select(User).where(User.id == user.get("sub"), User.org_slug == org)).scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if db_user.role != "admin" and not bool(getattr(db_user, "onboarding_completed", False)):
            raise HTTPException(status_code=403, detail="Onboarding incomplete")
        uid = user.get("sub")
        uname = user.get("name")
        # ORKIO_AO60F_HF4_NON_ADMIN_REALTIME_ORKIO_ONLY
        # Public beta rule: AMCHAMRSORKIO and EFATAH777 must behave the same in Realtime.
        # Only admins keep access to Chris/Orion/Team while agents are progressively released.
        is_realtime_admin = bool(
            str(user.get("role") or "").strip().lower() == "admin"
            or bool(user.get("is_admin") or user.get("admin"))
            or (
                db_user is not None
                and (
                    str(getattr(db_user, "role", "") or "").strip().lower() == "admin"
                    or bool(getattr(db_user, "is_admin", False))
                    or bool(getattr(db_user, "admin", False))
                )
            )
        )
        realtime_usage_tier = str(getattr(db_user, "usage_tier", "") or "").strip().lower() if db_user is not None else ""
        realtime_signup_source = str(getattr(db_user, "signup_source", "") or "").strip().lower() if db_user is not None else ""
        realtime_signup_label = str(getattr(db_user, "signup_code_label", "") or "").strip().lower() if db_user is not None else ""
        realtime_product_scope = str(getattr(db_user, "product_scope", "") or "").strip().lower() if db_user is not None else ""

        public_beta_orkio_only = bool(
            db_user is not None
            and not is_realtime_admin
        )

        # Resolve thread
        tid = body.thread_id
        if not tid:
            t = Thread(id=new_id(), org_slug=org, title="Realtime", created_at=now_ts())
            db.add(t)
            db.commit()
            tid = t.id
            _ensure_thread_owner(db, org, tid, uid)
        else:
            if user.get("role") != "admin":
                _require_thread_member(db, org, tid, uid)

        mode = normalize_mode(body.mode)
        response_profile = normalize_response_profile(body.response_profile)
        language_profile = normalize_language_profile(body.language_profile)
        summit_cfg = get_summit_runtime_config(
            mode=mode,
            response_profile=response_profile,
            language_profile=language_profile,
        )

        # AO47A_REALTIME_AGENT_IDENTITY_BINDING
        # Se o frontend não enviar agent_id, bindar Orkio como default seguro.
        requested_agent_id = str(body.agent_id or "").strip() or None
        agent_id = None if public_beta_orkio_only else requested_agent_id
        agent_name = None
        agent_voice = None
        agent_identity_source = "public_beta_orkio_only_forced" if public_beta_orkio_only else "requested_agent"

        if agent_id is not None:
            agent = db.execute(select(Agent).where(Agent.id == agent_id, Agent.org_slug == org)).scalar_one_or_none()
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found for this tenant")
            agent_name = (agent.name or "Orkio").strip() or "Orkio"
            agent_voice = resolve_agent_voice(agent) if agent else None
        else:
            agent_identity_source = "default_orkio_fallback"
            try:
                default_agent = db.execute(
                    select(Agent).where(Agent.name == "Orkio", Agent.org_slug == org)
                ).scalar_one_or_none()
                if default_agent:
                    agent_id = str(default_agent.id)
                    agent_name = (default_agent.name or "Orkio").strip() or "Orkio"
                    agent_voice = resolve_agent_voice(default_agent)
                    agent_identity_source = "default_orkio_agent"
                else:
                    agent_name = "Orkio"
            except Exception:
                try:
                    logger.exception("AO47A_DEFAULT_ORKIO_REALTIME_START_LOOKUP_FAILED org=%s user_id=%s", org, uid)
                except Exception:
                    pass
                agent_name = "Orkio"
                agent_identity_source = "default_orkio_fallback_error"

        default_realtime_voice = (os.getenv("OPENAI_REALTIME_VOICE_DEFAULT", "") or os.getenv("OPENAI_TTS_VOICE_DEFAULT", "cedar")).strip() or "cedar"
        voice = normalize_realtime_voice((agent_voice or default_realtime_voice) if public_beta_orkio_only else (body.voice or agent_voice or default_realtime_voice), default=default_realtime_voice)

        sid = str(uuid.uuid4())
        rs = None
        try:
            # Create session record
            rs = RealtimeSession(
                id=sid,
                org_slug=org,
                thread_id=tid,
                agent_id=str(agent_id) if agent_id is not None else None,
                agent_name=agent_name,
                user_id=uid,
                user_name=uname,
                model=body.model,
                voice=voice,
                started_at=now_ts(),
                meta=json.dumps({
                    "ttl_seconds": body.ttl_seconds,
                    "mode": summit_cfg.get("mode"),
                    "response_profile": summit_cfg.get("response_profile"),
                    "language_profile": summit_cfg.get("language_profile"),
                    "transcription_language": summit_cfg.get("transcription_language"),
                    "stage_guidance": summit_cfg.get("stage_guidance"),
                    "agent_identity_binding": "AO47A_REALTIME_AGENT_IDENTITY_BINDING",
                    "agent_identity_source": agent_identity_source,
                    "public_beta_orkio_only": public_beta_orkio_only,
                    "realtime_orkio_only_reason": "non_admin_public_beta" if public_beta_orkio_only else "admin_full_access",
                    "realtime_usage_tier": realtime_usage_tier,
                    "realtime_signup_source": realtime_signup_source,
                    "realtime_signup_label": realtime_signup_label,
                    "realtime_product_scope": realtime_product_scope,
                    "requested_agent_id": str(requested_agent_id or ""),
                    "resolved_agent_id": str(agent_id or ""),
                    "resolved_agent_name": agent_name or "Orkio",
                }, ensure_ascii=False),
            )
            db.add(rs)
            db.commit()

            # Mint client secret using the same logic as /client_secret, but ensure instructions are injected.
            r = await realtime_client_secret(
                RealtimeClientSecretReq(
                    agent_id=agent_id,
                    voice=voice,
                    model=body.model,
                    ttl_seconds=body.ttl_seconds,
                    mode=summit_cfg.get("mode"),
                    response_profile=summit_cfg.get("response_profile"),
                    language_profile=summit_cfg.get("language_profile"),
                ),
                x_org_slug=x_org_slug,
                user=user,
                db=db,
            )
        except HTTPException:
            if rs is not None:
                try:
                    rs.ended_at = now_ts()
                    db.add(rs)
                    db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
            raise
        except Exception as err:
            try:
                logger.exception("realtime_start_failed org=%s user_id=%s thread_id=%s agent_id=%s", org, uid, tid, agent_id)
            except Exception:
                pass
            if rs is not None:
                try:
                    rs.ended_at = now_ts()
                    db.add(rs)
                    db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
            raise HTTPException(status_code=502, detail="Failed to start Realtime session") from err

        # Audit
        _audit_realtime_safe(db, org, uid, action="realtime.session.start", meta={
            "session_id": sid,
            "thread_id": tid,
            "agent_id": agent_id,
            "agent_name": agent_name or "Orkio",
            "agent_identity_source": agent_identity_source,
            "model": body.model,
            "voice": voice,
            "mode": summit_cfg.get("mode"),
            "response_profile": summit_cfg.get("response_profile"),
            "language_profile": summit_cfg.get("language_profile"),
        })

        return {
            "ok": True,
            "session_id": sid,
            "thread_id": tid,
            "agent": {"id": agent_id, "name": agent_name or "Orkio", "identity_source": agent_identity_source},
            "model": body.model,
            "voice": voice,
            "mode": summit_cfg.get("mode"),
            "response_profile": summit_cfg.get("response_profile"),
            "language_profile": summit_cfg.get("language_profile"),
            "client_secret": {"value": r.get("value")},
            "client_secret_value": r.get("value"),
            "realtime_session": r.get("session"),
            "summit_config": summit_cfg,
        }


    @router.post("/api/realtime/event")
    def realtime_event(
        body: RealtimeEventIn,
        background_tasks: BackgroundTasks,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Persist realtime transcript/response events for auditability.
        Frontend should POST here for:
          - transcript deltas/finals (role=user)
          - response deltas/finals (role=assistant)
        If is_final=True, we also persist a Message into the thread timeline.
        """
        org = _resolve_org(user, x_org_slug)
        uid = user.get("sub")

        rs = db.execute(select(RealtimeSession).where(RealtimeSession.id == body.session_id, RealtimeSession.org_slug == org)).scalar_one_or_none()
        if not rs:
            raise HTTPException(status_code=404, detail="Realtime session not found")

        if user.get("role") != "admin":
            _require_thread_member(db, org, rs.thread_id, uid)

        ts = int(body.created_at or now_ts())
        speaker_type = (body.role or "user").strip() or "user"
        speaker_id = rs.user_id if speaker_type == "user" else rs.agent_id
        agent_id = rs.agent_id if speaker_type != "user" else None
        agent_name = rs.agent_name if speaker_type != "user" else None
        content = (body.content or "").strip()
        client_eid = (getattr(body, "client_event_id", None) or "").strip() or None

        if client_eid:
            try:
                existing_eid = db.execute(
                    select(RealtimeEvent.id)
                    .where(
                        RealtimeEvent.org_slug == org,
                        RealtimeEvent.session_id == rs.id,
                        RealtimeEvent.client_event_id == client_eid,
                    )
                    .limit(1)
                ).scalar_one_or_none()
                if existing_eid:
                    return {"ok": True, "deduped": True}
            except Exception:
                pass

        ev = RealtimeEvent(
            id=new_id(),
            org_slug=org,
            session_id=rs.id,
            thread_id=rs.thread_id,
            speaker_type=speaker_type,
            speaker_id=speaker_id,
            agent_id=agent_id,
            agent_name=agent_name,
            event_type=body.event_type,
            transcript_raw=content,
            transcript_punct=None,
            created_at=ts,
            client_event_id=client_eid,
            meta=json.dumps(body.meta or {}, ensure_ascii=False) if body.meta is not None else None,
        )
        db.add(ev)

        if body.is_final and content:
            if speaker_type == "user":
                client_mid = f"rt-{client_eid}" if client_eid else None
                already_message = None
                if client_mid:
                    try:
                        already_message = db.execute(
                            select(Message.id)
                            .where(
                                Message.org_slug == org,
                                Message.thread_id == rs.thread_id,
                                Message.role == "user",
                                Message.client_message_id == client_mid,
                            )
                            .limit(1)
                        ).scalar_one_or_none()
                    except Exception:
                        already_message = None

                if not already_message:
                    m = Message(
                        id=new_id(),
                        org_slug=org,
                        thread_id=rs.thread_id,
                        user_id=rs.user_id,
                        user_name=rs.user_name,
                        role="user",
                        content=_sanitize_assistant_text(content),
                        client_message_id=client_mid,
                        created_at=ts,
                    )
                    db.add(m)
            else:
                m = Message(
                    id=new_id(),
                    org_slug=org,
                    thread_id=rs.thread_id,
                    user_id=None,
                    user_name=None,
                    role="assistant",
                    content=_sanitize_assistant_text(content),
                    agent_id=agent_id,
                    agent_name=agent_name,
                    created_at=ts,
                )
                db.add(m)

        _audit_realtime_safe(db, org, uid, action="realtime.event", meta={"session_id": rs.id, "thread_id": rs.thread_id, "event_type": body.event_type, "role": body.role, "is_final": bool(body.is_final)})

        db.commit()
        try:
            if body.is_final and (body.event_type or "").strip() == "transcript.final":
                background_tasks.add_task(punctuate_realtime_events, org, [ev.id])
        except Exception:
            pass

        try:
            if (
                body.is_final
                and (body.event_type or "").strip() == "transcript.final"
                and speaker_type == "user"
                and content
            ):
                _run_realtime_multi_agent_turn(
                    db,
                    org=org,
                    rs=rs,
                    user=user,
                    message=content,
                )
        except Exception:
            logger.exception(
                "REALTIME_MULTI_AGENT_TURN_FAILED session_id=%s thread_id=%s",
                rs.id,
                rs.thread_id,
            )
        return {"ok": True}


    @router.post("/api/realtime/events:batch")
    def realtime_events_batch(
        body: RealtimeEventsBatchReq,
        background_tasks: BackgroundTasks,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Persist a batch of realtime events for auditability.
        This is the preferred path for WebRTC clients to avoid per-event HTTP overhead.
        Final realtime transcripts stay in realtime_events and MUST NOT pollute the text chat timeline.
        """
        org = _resolve_org(user, x_org_slug)
        uid = user.get("sub")

        rs = db.execute(select(RealtimeSession).where(RealtimeSession.id == body.session_id, RealtimeSession.org_slug == org)).scalar_one_or_none()
        if not rs:
            raise HTTPException(status_code=404, detail="Realtime session not found")

        if user.get("role") != "admin":
            _require_thread_member(db, org, rs.thread_id, uid)

        now = int(now_ts())
        ev_rows: List[RealtimeEvent] = []
        message_rows: List[Message] = []
        punct_ids: List[str] = []
        multi_agent_inputs: List[str] = []
        ao19d_telemetry_counts: Dict[str, int] = {}
        ao19d_critical_seen: List[str] = []

        for item in body.events:
            ts = int(item.created_at or now)
            event_type_raw = str(item.event_type or "").strip()
            if event_type_raw.startswith("telemetry."):
                telemetry_name = _ao19d_realtime_event_name(event_type_raw)
                ao19d_telemetry_counts[telemetry_name] = ao19d_telemetry_counts.get(telemetry_name, 0) + 1
                if event_type_raw in AO19D_REALTIME_TELEMETRY_CRITICAL_EVENTS:
                    ao19d_critical_seen.append(telemetry_name)
                    telemetry_meta = _ao19d_safe_meta(getattr(item, "meta", None))
                    logger.info(
                        "AO19D_REALTIME_TELEMETRY session_id=%s thread_id=%s event=%s dc_state=%s pc_state=%s phase=%s",
                        body.session_id,
                        getattr(rs, "thread_id", None),
                        telemetry_name,
                        telemetry_meta.get("dc_state"),
                        telemetry_meta.get("pc_state"),
                        telemetry_meta.get("phase"),
                    )
            speaker_type = (item.role or "user").strip() or "user"
            speaker_id = rs.user_id if speaker_type == "user" else rs.agent_id
            agent_id = rs.agent_id if speaker_type != "user" else None
            agent_name = rs.agent_name if speaker_type != "user" else None

            client_eid = (getattr(item, "client_event_id", None) or "").strip() or None
            if client_eid:
                try:
                    existing_eid = db.execute(
                        select(RealtimeEvent.id)
                        .where(
                            RealtimeEvent.org_slug == org,
                            RealtimeEvent.session_id == rs.id,
                            RealtimeEvent.client_event_id == client_eid,
                        )
                        .limit(1)
                    ).scalar_one_or_none()
                    if existing_eid:
                        continue
                except Exception:
                    pass

            content = (item.content or "").strip()
            eid = new_id()
            ev_rows.append(
                RealtimeEvent(
                    id=eid,
                    org_slug=org,
                    session_id=rs.id,
                    thread_id=rs.thread_id,
                    speaker_type=speaker_type,
                    speaker_id=speaker_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                    event_type=item.event_type,
                    transcript_raw=content,
                    transcript_punct=None,
                    created_at=ts,
                    client_event_id=client_eid,
                    meta=json.dumps(item.meta or {}, ensure_ascii=False) if item.meta is not None else None,
                )
            )

            try:
                event_type = (item.event_type or "").strip()
                if item.is_final and event_type == "transcript.final":
                    punct_ids.append(eid)

                if item.is_final and content and event_type in ("transcript.final", "response.final"):
                    message_created_at = ts if isinstance(ts, int) and ts > 0 else int(now_ts())

                    if speaker_type == "user":
                        client_mid = f"rt-{client_eid}" if client_eid else None
                        already_message = None
                        if client_mid:
                            try:
                                already_message = db.execute(
                                    select(Message.id)
                                    .where(
                                        Message.org_slug == org,
                                        Message.thread_id == rs.thread_id,
                                        Message.role == "user",
                                        Message.client_message_id == client_mid,
                                    )
                                    .limit(1)
                                ).scalar_one_or_none()
                            except Exception:
                                already_message = None

                        if not already_message:
                            message_rows.append(
                                Message(
                                    id=new_id(),
                                    org_slug=org,
                                    thread_id=rs.thread_id,
                                    user_id=rs.user_id,
                                    user_name=rs.user_name,
                                    role="user",
                                    content=_sanitize_assistant_text(content),
                                    client_message_id=client_mid,
                                    created_at=message_created_at,
                                )
                            )
                        if event_type == "transcript.final":
                            multi_agent_inputs.append(content)
                    else:
                        message_rows.append(
                            Message(
                                id=new_id(),
                                org_slug=org,
                                thread_id=rs.thread_id,
                                user_id=None,
                                user_name=None,
                                role="assistant",
                                content=_sanitize_assistant_text(content),
                                agent_id=agent_id,
                                agent_name=agent_name,
                                created_at=message_created_at,
                            )
                        )
            except Exception:
                pass

        if ev_rows:
            db.add_all(ev_rows)
        if message_rows:
            db.add_all(message_rows)

        db.commit()
        try:
            if punct_ids:
                background_tasks.add_task(punctuate_realtime_events, org, punct_ids)
        except Exception:
            pass

        for content in multi_agent_inputs:
            try:
                _run_realtime_multi_agent_turn(
                    db,
                    org=org,
                    rs=rs,
                    user=user,
                    message=content,
                )
            except Exception:
                logger.exception(
                    "REALTIME_MULTI_AGENT_TURN_FAILED session_id=%s thread_id=%s",
                    rs.id,
                    rs.thread_id,
                )

        if ao19d_telemetry_counts:
            try:
                logger.info(
                    "AO19D_REALTIME_TELEMETRY_BATCH session_id=%s thread_id=%s total=%s critical=%s counts=%s",
                    rs.id,
                    rs.thread_id,
                    sum(ao19d_telemetry_counts.values()),
                    ",".join(ao19d_critical_seen[-12:]),
                    json.dumps(ao19d_telemetry_counts, ensure_ascii=False, sort_keys=True),
                )
            except Exception:
                pass

        return {
            "inserted_events": len(ev_rows),
            "inserted_messages": len(message_rows),
            "ao19d_telemetry": {
                "enabled": True,
                "total": sum(ao19d_telemetry_counts.values()),
                "critical_seen": ao19d_critical_seen[-20:],
                "counts": ao19d_telemetry_counts,
            },
        }


    @router.post("/api/realtime/end")
    def realtime_end(
        body: RealtimeEndReq,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        org = _resolve_org(user, x_org_slug)
        uid = user.get("sub")

        rs = db.execute(select(RealtimeSession).where(RealtimeSession.id == body.session_id, RealtimeSession.org_slug == org)).scalar_one_or_none()
        if not rs:
            raise HTTPException(status_code=404, detail="Realtime session not found")

        if user.get("role") != "admin":
            _require_thread_member(db, org, rs.thread_id, uid)

        rs.ended_at = int(body.ended_at or now_ts())
        # merge meta
        try:
            cur = json.loads(rs.meta) if rs.meta else {}
        except Exception:
            cur = {}
        if body.meta:
            cur.update(body.meta)
        rs.meta = json.dumps(cur)

        _audit_realtime_safe(db, org, uid, action="realtime.session.end", meta={"session_id": rs.id, "thread_id": rs.thread_id})

        db.commit()
        return {"ok": True}


    @router.get("/api/realtime/sessions/{session_id}")
    def realtime_get_session(
        session_id: str,
        finals_only: bool = True,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Fetch a realtime session and its persisted events.
        - finals_only=True returns only *.final events (recommended for UI/audit).
        Best-effort, never depends on audit helpers.
        """
        org = _resolve_org(user, x_org_slug)
        uid = user.get("sub")

        rs = db.execute(select(RealtimeSession).where(RealtimeSession.id == session_id, RealtimeSession.org_slug == org)).scalar_one_or_none()
        if not rs:
            raise HTTPException(status_code=404, detail="Realtime session not found")

        if user.get("role") != "admin":
            _require_thread_member(db, org, rs.thread_id, uid)

        q = select(RealtimeEvent).where(RealtimeEvent.org_slug == org, RealtimeEvent.session_id == session_id)
        if finals_only:
            q = q.where(RealtimeEvent.event_type.like("%.final"))
        q = q.order_by(RealtimeEvent.created_at.asc())
        evs = db.execute(q).scalars().all()

        def _ev_to_dict(ev: RealtimeEvent) -> dict:
            speaker_type = getattr(ev, "speaker_type", None)
            transcript_raw = getattr(ev, "transcript_raw", None)
            legacy_role = getattr(ev, "role", None)
            legacy_content = getattr(ev, "content", None)
            return {
                "id": ev.id,
                "session_id": ev.session_id,
                "thread_id": ev.thread_id,
                "speaker_type": speaker_type or legacy_role,
                "speaker_id": getattr(ev, "speaker_id", None),
                "role": speaker_type or legacy_role,
                "agent_id": getattr(ev, "agent_id", None),
                "agent_name": getattr(ev, "agent_name", None),
                "event_type": getattr(ev, "event_type", None),
                "transcript_raw": transcript_raw or legacy_content,
                "content": transcript_raw or legacy_content,
                "transcript_punct": getattr(ev, "transcript_punct", None),
                "created_at": getattr(ev, "created_at", None),
                "is_final": bool(str(getattr(ev, "event_type", "")).endswith(".final")),
                "client_event_id": getattr(ev, "client_event_id", None),
                "meta": getattr(ev, "meta", None),
            }

        try:
            meta = json.loads(rs.meta) if rs.meta else {}
        except Exception:
            meta = {}

        # Simple status flags for UI polling
        punct_total = 0
        punct_ready = 0
        out_events = []
        for ev in evs:
            d = _ev_to_dict(ev)
            ev_text = (getattr(ev, "transcript_raw", None) or getattr(ev, "content", None) or "").strip()
            if finals_only and (ev.event_type or "").endswith(".final") and ev_text:
                punct_total += 1
                if (getattr(ev, "transcript_punct", None) or ev_text).strip():
                    punct_ready += 1
            out_events.append(d)

        live_assistant_messages = []
        try:
            msgs = db.execute(
                select(Message)
                .where(
                    Message.org_slug == org,
                    Message.thread_id == rs.thread_id,
                    Message.role == "assistant",
                    Message.created_at >= int(rs.started_at or 0),
                )
                .order_by(Message.created_at.asc())
            ).scalars().all()
            agent_ids = list({getattr(m, "agent_id", None) for m in msgs if getattr(m, "agent_id", None)})
            agent_rows = db.execute(
                select(Agent).where(Agent.org_slug == org, Agent.id.in_(agent_ids))
            ).scalars().all() if agent_ids else []
            agent_by_id = {a.id: a for a in agent_rows}
            live_assistant_messages = [
                {
                    "id": m.id,
                    "agent_id": getattr(m, "agent_id", None),
                    "agent_name": getattr(m, "agent_name", None),
                    "voice_id": resolve_agent_voice(agent_by_id.get(getattr(m, "agent_id", None))),
                    "content": getattr(m, "content", None),
                    "created_at": getattr(m, "created_at", None),
                }
                for m in msgs
            ]
        except Exception:
            logger.exception("REALTIME_LIVE_MESSAGES_LOAD_FAILED session_id=%s", session_id)

        return {
            "session": {
                "id": rs.id,
                "thread_id": rs.thread_id,
                "agent_id": rs.agent_id,
                "agent_name": rs.agent_name,
                "user_id": rs.user_id,
                "user_name": rs.user_name,
                "model": rs.model,
                "voice": rs.voice,
                "started_at": rs.started_at,
                "ended_at": rs.ended_at,
                "meta": meta,
            },
            "events": out_events,
            "live_assistant_messages": live_assistant_messages,
            "punct": {"total": punct_total, "ready": punct_ready, "done": (punct_total > 0 and punct_ready == punct_total)},
        }


    return router
