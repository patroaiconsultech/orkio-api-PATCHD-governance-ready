from __future__ import annotations

from typing import Any, Dict, Optional
import re

from app.config.runtime import RUNTIME_FLAGS
from app.services.governance_service import evaluate_governance_action


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, terms: list[str]) -> bool:
    txt = _normalize(text)
    return any(_normalize(term) in txt for term in terms if term)

def _excluded_agents(text: str) -> list[str]:
    txt = _normalize(text)
    if not txt:
        return []
    patterns = {
        "chris": [
            r"(?:sem|exceto|without|exclude|bloquear)\s+chris",
            r"chris.*?(?:nao pode|não pode|nao deve|não deve|nao responder|não responder|nao assinar|não assinar|nao interceptar|não interceptar|nao substituir|não substituir)",
        ],
        "orion": [
            r"(?:sem|exceto|without|exclude|bloquear)\s+orion",
            r"orion.*?(?:nao pode|não pode|nao deve|não deve)",
        ],
    }
    out: list[str] = []
    for name, pats in patterns.items():
        if any(re.search(p, txt, flags=re.IGNORECASE) for p in pats):
            out.append(name)
    return out

def _looks_like_orion_only_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    if not re.search(r"@orion\b|\borion\b", txt, flags=re.IGNORECASE):
        return False
    if re.search(r"@team\b|\bteam\b|\bequipe\b|\bboard\b|\bconselho\b", txt, flags=re.IGNORECASE):
        return False
    excluded = set(_excluded_agents(text))
    if "chris" not in excluded and re.search(r"@chris\b|\bchris\b|\bcfo\b", txt, flags=re.IGNORECASE):
        return False
    return True


def _looks_like_team_technical_audit_request(text: str) -> bool:
    """Detecta @Team/equipe técnica pedindo auditoria read-only de code/runtime.

    Importante: isso NÃO deve virar Orion-only. Orion permanece signer/consolidador,
    mas o dispatch deve selecionar especialistas técnicos e gerar specialist_reports.
    """
    txt = _normalize(text)
    if not txt:
        return False

    has_team = bool(re.search(r"@team\b|\bteam\b|\bequipe\b|\bsquad\b|\bespecialistas\b|\bwar room\b", txt, flags=re.IGNORECASE))
    if not has_team:
        return False

    has_audit = _contains_any(txt, [
        "auditoria",
        "auditar",
        "audit",
        "diagnóstico",
        "diagnostico",
        "scan",
        "varredura",
        "análise técnica",
        "analise tecnica",
    ])

    has_technical_scope = _contains_any(txt, [
        "code",
        "código",
        "codigo",
        "runtime",
        "backend",
        "frontend",
        "repo",
        "repositório",
        "repositorio",
        "main.py",
        "intent_engine.py",
        "orion_internal.py",
        "governança",
        "governanca",
        "roteamento",
        "agentes",
        "ux",
        "console",
    ])

    read_only = (
        _contains_any(txt, ["read-only", "read only", "somente leitura", "sem escrever", "não escrever", "nao escrever"])
        or not _contains_any(txt, ["aplicar patch", "criar branch", "abrir pr", "merge", "deploy", "escrever arquivo"])
    )

    return bool(has_team and has_audit and has_technical_scope and read_only)


def _looks_like_privileged_admin_read(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    has_admin = _contains_any(txt, ["admin master", "como admin", "sou admin", "admin"])
    has_read = _contains_any(txt, [
        "analise o arquivo",
        "análise do arquivo",
        "analisar o arquivo",
        "leia o arquivo",
        "arquivo em anexo",
        "arquivo anexado",
        "anexo",
        "logs",
        "log",
        "me diga o que é a plataforma",
        "o que é a plataforma",
        "auditoria",
        "diagnóstico",
        "diagnostico",
        "war room",
        "read only",
        "somente leitura",
    ])
    has_write = _contains_any(txt, [
        "criar branch",
        "branch",
        "aplicar patch",
        "patch",
        "commit",
        "abrir pr",
        "open pr",
        "pull request",
        "merge",
        "deploy",
        "criar arquivo",
        "alterar arquivo",
        "write file",
        "create file",
        "update file",
        "escrever na main",
        "write to main",
    ])
    return bool((has_admin or has_read) and has_read and not has_write)


def _infer_action_scope(text: str) -> str:
    txt = _normalize(text)
    if _looks_like_privileged_admin_read(txt):
        return "read"
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
    if _contains_any(txt, ["audit", "auditoria", "scan", "diagnóstico", "diagnostico", "self audit", "war room"]):
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
    if _contains_any(txt, ["audit", "auditoria", "scan", "self audit", "runtime diagnostic", "war room"]):
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
    admin_access_mode = "read_privileged" if _looks_like_privileged_admin_read(text) and action_scope in {"read", "diagnose"} else "standard"
    requires_write_approval = action_scope in {"write_branch", "open_pr", "merge", "deploy"}
    orion_only = _looks_like_orion_only_request(user_input or "")
    team_technical_audit = _looks_like_team_technical_audit_request(user_input or "")
    excluded_agents = _excluded_agents(user_input or "")
    if orion_only or team_technical_audit:
        capability_name = capability_name or "platform_self_audit"
        intent = "platform_self_audit"

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
        "admin_access_mode": admin_access_mode,
        "requires_write_approval": requires_write_approval,
        "visible_signer_expected": "orion" if (orion_only or team_technical_audit) else None,
        "excluded_agents": excluded_agents,
        "team_technical_audit": bool(team_technical_audit),
        "execution_mode": "read_only_dispatch" if team_technical_audit else None,
        "expected_specialist_reports": ["orion", "auditor", "cto"] if team_technical_audit else [],
    }
    recommended_agents = (
        ["orion", "auditor", "cto"]
        if team_technical_audit
        else (["orion"] if (orion_only or capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"}) else ["orkio"])
    )
    payload = {
        "intent": intent,
        "confidence": 0.98 if runtime_op.get("kind") else 0.62,
        "recommended_agents": recommended_agents,
        "advisor_agents": ["orion", "auditor", "cto", "metatron"] if team_technical_audit else ["orion", "metatron"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": bool(runtime_op.get("kind")),
        "target_agent": "orion" if (orion_only or team_technical_audit or capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"}) else "orkio",
        "delivery_contract": "orion_team_technical_audit_v1" if team_technical_audit else "orkio_governed_runtime_v1",
        "structured_output": bool(team_technical_audit),
        "first_win_goal": "execute_orion_runtime" if runtime_op.get("kind") else "clarify_next_step",
        "action_scope": action_scope,
        "target_scope": target_scope,
        "capability_name": capability_name,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": bool(governance_decision.get("requires_human_authorization")) and requires_write_approval,
        "admin_access_mode": admin_access_mode,
        "requires_write_approval": requires_write_approval,
        "team_technical_audit": bool(team_technical_audit),
        "expected_specialist_reports": ["orion", "auditor", "cto"] if team_technical_audit else [],
    }
    payload.update(_runtime_self_audit_override(intent))
    return payload
