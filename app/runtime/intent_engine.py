from __future__ import annotations

from typing import Any, Dict, Optional

from app.config.runtime import RUNTIME_FLAGS
from app.services.governance_service import evaluate_governance_action


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, terms: list[str]) -> bool:
    txt = _normalize(text)
    return any(_normalize(term) in txt for term in terms if term)


def _infer_action_scope(text: str) -> str:
    txt = _normalize(text)
    if _contains_any(txt, ["merge", "mergear"]):
        return "merge"
    if _contains_any(txt, ["deploy", "publicar"]):
        return "deploy"
    if _contains_any(txt, ["pull request", "abrir pr", "open pr", "pr #", "pr "]):
        return "open_pr"
    if _contains_any(txt, ["write", "escrever", "criar arquivo", "alterar arquivo", "corrigir arquivo", "branch"]):
        return "write_branch"
    if _contains_any(txt, ["patch", "proposta de patch", "plano de patch"]):
        return "propose_patch"
    if _contains_any(txt, ["audit", "auditoria", "scan", "diagnóstico", "diagnostico", "self audit"]):
        return "diagnose"
    return "read"


def _infer_target_scope(text: str) -> str:
    txt = _normalize(text)
    has_frontend = _contains_any(txt, ["frontend", "web", "ui", "ux", "landing", "console"])
    has_backend = _contains_any(txt, ["backend", "api", "runtime", "main.py", "intent_engine.py"])
    if has_frontend and has_backend:
        return "cross_repo"
    if has_frontend:
        return "frontend"
    if has_backend:
        return "backend"
    return "platform"


def _infer_capability(action_scope: str, text: str) -> Optional[str]:
    txt = _normalize(text)
    if _contains_any(txt, ["audit", "auditoria", "scan", "self audit", "runtime diagnostic"]):
        return "platform_self_audit"
    if action_scope == "open_pr":
        return "github_pr_prepare"
    if action_scope == "write_branch":
        return "github_repo_write"
    if _contains_any(txt, ["compare", "status da pr", "pr status"]):
        return "github_pr_compare_status"
    if action_scope in {"read", "diagnose", "propose_patch"}:
        return "github_repo_read"
    return None


def _runtime_self_audit_override(intent: str):
    if intent != "platform_self_audit":
        return {}
    if not RUNTIME_FLAGS["capability_enabled"]:
        return {
            "event": "PLATFORM_SELF_AUDIT_READY",
            "mode": "consultative",
        }
    return {
        "event": "ORION_RUNTIME_DIAGNOSTIC_EXECUTED",
        "execution_depth": "dispatch",
        "status": "executed",
    }


def build_intent_package(
    user_input: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    text = _normalize(user_input)
    context = dict(context or {})
    context["message"] = user_input or ""

    action_scope = _infer_action_scope(text)
    target_scope = _infer_target_scope(text)
    capability_name = _infer_capability(action_scope, text)
    intent = "platform_self_audit" if capability_name == "platform_self_audit" else ("platform_audit" if action_scope == "diagnose" else "general_guidance")

    governance_decision = evaluate_governance_action(
        action_scope=action_scope,
        capability_name=capability_name,
        target_scope=target_scope,
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": intent if intent != "general_guidance" else "",
        "action_scope": action_scope,
        "target_scope": target_scope,
        "capability_name": capability_name,
    }
    payload = {
        "intent": intent,
        "confidence": 0.98 if runtime_op.get("kind") else 0.62,
        "recommended_agents": ["orion"] if capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"} else ["orkio"],
        "advisor_agents": ["orion", "metatron"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": bool(runtime_op.get("kind")),
        "target_agent": "orion" if capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"} else "orkio",
        "delivery_contract": "orkio_governed_runtime_v1",
        "structured_output": False,
        "first_win_goal": "execute_orion_runtime" if runtime_op.get("kind") else "clarify_next_step",
        "action_scope": action_scope,
        "target_scope": target_scope,
        "capability_name": capability_name,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": bool(governance_decision.get("requires_human_authorization")),
    }
    payload.update(_runtime_self_audit_override(intent))
    return payload
