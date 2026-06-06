from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional


ORION_POLICY_VERSION = "PUBLIC_ORION_POLICY_V4_INTERNAL_ONLY_AO64B"

_INTERNAL_ONLY_MESSAGE = (
    "Orion é um agente interno de auditoria técnica da plataforma. "
    "Para este ambiente, sigo com Orkio para manter a experiência segura e adequada."
)


def _strip_accents(value: Any) -> str:
    raw = str(value or "")
    normalized = unicodedata.normalize("NFD", raw)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _strip_accents(value).lower()).strip()


def _target_is_orion(
    *,
    message: Any,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> bool:
    text = _norm(message)
    visible = _norm(visible_agent)
    target = _norm(target_agent_slug)
    mode = _norm(dest_mode)
    route = route_plan if isinstance(route_plan, dict) else {}

    route_requested = _norm(route.get("requested_agent") or route.get("requested") or "")
    route_resolved = _norm(route.get("resolved_agent") or route.get("final_speaker") or "")

    return bool(
        "@orion" in text
        or text.startswith("orion")
        or " orion," in f" {text}"
        or visible.startswith("orion")
        or target.startswith("orion")
        or route_requested.startswith("orion")
        or route_resolved.startswith("orion")
        or (mode == "single" and (target.startswith("orion") or visible.startswith("orion")))
    )


def build_public_orion_policy_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    AO64B PATCH MINIMUM — Orion internal-only on public chat surface.

    Motivo:
    - Usuário AMCHAM/public conseguiu chamar Orion por texto.
    - Orion é agente interno de auditoria/governança.
    - A superfície pública deve responder com Orkio, não com Orion.

    Comportamento:
    - Se o target NÃO for Orion: não interfere.
    - Se o target for Orion: bloqueia execução pública e emite resposta segura como Orkio.
    - Não executa escrita, GitHub, deploy, auditoria técnica real ou capacidade sensível.
    """
    if not _target_is_orion(
        message=message,
        visible_agent=visible_agent,
        target_agent_slug=target_agent_slug,
        dest_mode=dest_mode,
        route_plan=route_plan,
    ):
        return {"handled": False, "reason": "not_orion_target"}

    return {
        "handled": True,
        "agent_name": "Orkio",
        "agent_id": None,
        "answer": _INTERNAL_ONLY_MESSAGE,
        "reason": "orion_internal_only_public_surface",
        "policy_version": ORION_POLICY_VERSION,
        "intent": "agent_access_denied",
        "blocked_agent": "Orion",
        "resolved_agent": "Orkio",
        "write_executed": False,
        "proposal_created": False,
        "branch_created": False,
        "pr_created": False,
    }


def build_public_orion_stream_payload(
    decision: Dict[str, Any],
    *,
    persisted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    persisted = persisted if isinstance(persisted, dict) else {}
    final_text = str(decision.get("answer") or _INTERNAL_ONLY_MESSAGE).strip()

    return {
        **persisted,
        "ok": True,
        "answer": final_text,
        "message": final_text,
        "final_text": final_text,
        "content": final_text,
        "text": final_text,
        "agent_id": decision.get("agent_id"),
        "agent_name": "Orkio",
        "final_speaker": "Orkio",
        "visible_agent": "Orkio",
        "service": "public_orion_policy",
        "provider": "platform",
        "status": "done",
        "blocked_agent": "Orion",
        "resolved_agent": "Orkio",
        "runtime_hints": {
            "routing": {
                "routing_source": "public_orion_policy_module",
                "route_applied": True,
                "execution_lifecycle": "completed",
                "route_family": "agent_access_policy",
                "route_reason": decision.get("reason") or "orion_internal_only_public_surface",
                "policy_version": decision.get("policy_version") or ORION_POLICY_VERSION,
                "access_decision": "denied_public_surface",
                "blocked_agent": "Orion",
                "resolved_agent": "Orkio",
                "write_executed": False,
                "proposal_created": False,
                "branch_created": False,
                "pr_created": False,
            }
        },
    }
