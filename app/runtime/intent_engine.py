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



def _strip_constraint_token(value: Any) -> str:
    raw = str(value or "").strip()
    prev = None
    while raw and raw != prev:
        prev = raw
        raw = re.sub(r"^\s*[-*•]+\s*", "", raw)
        raw = re.sub(r"^\s*\d+[.)]\s*", "", raw)
        raw = raw.strip()
    return raw


def _canonical_dispatch_actor(value: Any) -> str:
    cleaned = _strip_constraint_token(value)
    raw = _normalize(str(cleaned or "").replace("@", " ").replace("-", "_").replace(" ", "_"))
    if not raw:
        return ""
    aliases = {
        "ux/frontend": "ux_frontend",
        "ux_frontend": "ux_frontend",
        "ux_front": "ux_frontend",
        "ux": "ux_frontend",
        "frontend": "ux_frontend",
        "front_end": "ux_frontend",
        "orion_cto": "orion",
        "cto_runtime": "orion",
    }
    return aliases.get(raw, raw)

def _dedupe_preserve(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        slug = _canonical_dispatch_actor(item)
        if slug and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


def _extract_constraint_scalar(text: str, keys: list[str]) -> str:
    raw = text or ""
    for key in keys:
        pattern = rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*([^\n#]+?)\s*$"
        match = re.search(pattern, raw)
        if match:
            return _canonical_dispatch_actor(_strip_constraint_token(match.group(1)))
    return ""


def _extract_constraint_list(text: str, keys: list[str]) -> list[str]:
    raw = text or ""
    lines = raw.splitlines()
    collected: list[str] = []
    active = False
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        matched_key = None
        for key in keys:
            if lowered.startswith(f"{key.lower()}:"):
                matched_key = key
                break
        if matched_key is not None:
            active = True
            inline = _strip_constraint_token(stripped.split(":", 1)[1].strip())
            if inline:
                parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", inline)]
                collected.extend([p for p in parts if p])
            continue
        if not active:
            continue
        if not stripped:
            if collected:
                break
            continue
        if re.match(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", stripped):
            collected.append(_strip_constraint_token(stripped))
            continue
        if re.match(r"^[A-Za-z0-9_/@.-]+\s*[:=]", stripped):
            break
        if collected:
            break
    if collected:
        return _dedupe_preserve(collected)

    for key in keys:
        pattern = rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*([^\n#]+?)\s*$"
        match = re.search(pattern, raw)
        if match:
            parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", match.group(1))]
            return _dedupe_preserve([p for p in parts if p])
    return []

def _extract_constraint_count(text: str) -> Optional[int]:
    raw = text or ""
    patterns = [
        r"(?im)^\s*selected_specialists_count_must_be\s*[:=]\s*(\d+)\s*$",
        r"(?im)^\s*selected_specialists_count\s*[:=]\s*(\d+)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def _extract_hard_constraints(text: str) -> Dict[str, Any]:
    required_signer = _extract_constraint_scalar(text, ["required_signer", "signer_must_be", "signer_must"])
    specialists_required = _extract_constraint_list(text, ["specialists_required", "allowed_specialists_only"])
    specialists_forbidden = _extract_constraint_list(text, ["specialists_forbidden", "forbidden_specialists"])
    selected_count = _extract_constraint_count(text)
    if selected_count is None and specialists_required:
        selected_count = len(specialists_required)
    return {
        "required_signer": required_signer or None,
        "specialists_required": specialists_required,
        "specialists_forbidden": specialists_forbidden,
        "selected_specialists_count_must_be": selected_count,
        "has_hard_constraints": bool(required_signer or specialists_required or specialists_forbidden or selected_count is not None),
    }


def _apply_dispatch_constraints(default_agents: list[str], *, required: list[str], forbidden: list[str], required_signer: Optional[str] = None, count_must_be: Optional[int] = None) -> list[str]:
    base = _dedupe_preserve(default_agents)
    if required:
        base = _dedupe_preserve(required)
    if forbidden:
        forbidden_set = set(_dedupe_preserve(forbidden))
        base = [item for item in base if item not in forbidden_set]
    signer_slug = _canonical_dispatch_actor(required_signer or "")
    if signer_slug and signer_slug not in base and (not required or count_must_be is None or len(base) < int(count_must_be)):
        base = [signer_slug] + base
        base = _dedupe_preserve(base)
    if count_must_be is not None and count_must_be >= 0 and len(base) > int(count_must_be):
        base = base[: int(count_must_be)]
    return base

def _looks_like_orion_only_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    hard_constraints = _extract_hard_constraints(text or "")
    if len(list(hard_constraints.get("specialists_required") or [])) > 1:
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
    """Detecta @Team/equipe técnica pedindo auditoria read-only de code/runtime."""
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


def _looks_like_runtime_source_audit_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    patterns = [
        r"auditoria\s+de\s+fonte",
        r"runtime\s+source\s+audit",
        r"source\s+audit",
        r"diverg[êe]ncias?\s+entre\s+fontes",
        r"cat[aá]logo\s+p[úu]blico",
        r"cat[aá]logo\s+privilegiad",
        r"seed\s+oculto",
        r"ocultos?\s+e\s+internos?",
        r"agentes\s+com\s+hidden\s*=\s*true",
        r"agentes\s+com\s+internal\s*=\s*true",
        r"agentes\s+com\s+system\s*=\s*true",
        r"agentes\s+system",
        r"veredito\s+final",
        r"consist[êe]ncia\s+entre\s+fontes",
    ]
    return any(re.search(p, txt, flags=re.IGNORECASE) for p in patterns)


def _looks_like_platform_improvement_review_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    if _looks_like_runtime_source_audit_request(txt):
        return False

    explicit_review = _contains_any(txt, [
        "mesa de melhorias",
        "rodada de melhorias",
        "review de melhorias",
        "improvement review",
        "platform improvement review",
        "plataform improvement review",
        "melhorias da plataforma",
        "propostas de melhoria",
        "sugestões de melhoria",
        "sugestoes de melhoria",
        "quick wins",
        "melhorias estruturais",
        "ordem recomendada de implementação",
        "ordem recomendada de implementacao",
        "ordem de implementação",
        "ordem de implementacao",
    ])

    improvement_markers = _contains_any(txt, [
        "melhoria",
        "melhorias",
        "improvement",
        "quick wins",
        "estruturais",
        "priorizadas",
        "priorizados",
        "sugestões",
        "sugestoes",
        "propostas",
    ])

    platform_scope = _contains_any(txt, [
        "plataforma",
        "app console",
        "landing",
        "fluxo de entrada",
        "receipts",
        "specialist reports",
        "dispatch",
        "observabilidade",
        "logs",
        "governança",
        "governanca",
        "capabilities",
        "comandos",
        "chat/stream",
        "streaming",
        "performance percebida",
        "multiagente",
        "multi-tenant",
        "segurança",
        "seguranca",
        "ux",
        "frontend",
    ])

    excludes_write = not _contains_any(txt, [
        "aplicar patch",
        "criar branch",
        "abrir pr",
        "merge",
        "deploy",
        "escrever arquivo",
    ])

    return bool((explicit_review or (improvement_markers and platform_scope)) and excludes_write)


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


def _has_completed_dispatch_context(context: Optional[Dict[str, Any]]) -> bool:
    ctx = dict(context or {})
    if str(ctx.get("execution_depth") or "").strip().lower() == "dispatch":
        return True
    if int(ctx.get("selected_specialists_count") or 0) > 0:
        return True
    if int(ctx.get("dispatch_receipts_count") or 0) > 0:
        return True
    if int(ctx.get("specialist_reports_count") or 0) > 0:
        return True

    runtime_enrichment = ctx.get("runtime_enrichment")
    if isinstance(runtime_enrichment, dict):
        if str(runtime_enrichment.get("execution_depth") or "").strip().lower() == "dispatch":
            return True
        if int(runtime_enrichment.get("selected_specialists_count") or 0) > 0:
            return True
        if int(runtime_enrichment.get("dispatch_receipts_count") or 0) > 0:
            return True
        if int(runtime_enrichment.get("specialist_reports_count") or 0) > 0:
            return True

    return False


def _looks_like_incremental_dispatch_followup_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False

    followup_markers = [
        "root causes",
        "causas raiz",
        "risks",
        "riscos",
        "next actions",
        "próximas ações",
        "proximas ações",
        "proximas acoes",
        "próximos passos",
        "proximos passos",
        "aprofundamento",
        "incremental",
        "follow-up",
        "followup",
        "derivação do dispatch",
        "derivacao do dispatch",
        "derivado do dispatch",
        "derivam de",
        "derivado de specialist_reports",
        "derivado de technical_summary",
        "derivado de final_consolidation",
        "derivado de confirmed_evidence",
        "não repetir o recibo completo",
        "nao repetir o recibo completo",
        "não repetir specialist_reports",
        "nao repetir specialist_reports",
        "execution_depth=dispatch",
        "execution depth dispatch",
    ]
    return _contains_any(txt, followup_markers)


def _infer_action_scope(text: str) -> str:
    txt = _normalize(text)
    if _looks_like_privileged_admin_read(txt):
        return "read"
    if _looks_like_platform_improvement_review_request(txt):
        return "propose_patch"
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
    if _looks_like_platform_improvement_review_request(txt):
        return "controlled_self_evolution_propose_only"
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

    has_completed_dispatch_context = _has_completed_dispatch_context(context)
    incremental_dispatch_followup = (
        has_completed_dispatch_context
        and _looks_like_incremental_dispatch_followup_request(user_input or "")
    )

    platform_improvement_review = (
        False if incremental_dispatch_followup
        else _looks_like_platform_improvement_review_request(user_input or "")
    )

    action_scope = _infer_action_scope(text)
    target_scope = _infer_target_scope(text)
    capability_name = _infer_capability(action_scope, text)

    if incremental_dispatch_followup:
        intent = "dispatch_incremental_followup"
        capability_name = "platform_self_audit"
        action_scope = "diagnose"
        target_scope = "platform"
    elif platform_improvement_review:
        intent = "platform_improvement_review"
    elif capability_name == "platform_self_audit":
        intent = "platform_self_audit"
    elif action_scope == "diagnose":
        intent = "platform_audit"
    else:
        intent = "general_guidance"

    admin_access_mode = "read_privileged" if _looks_like_privileged_admin_read(text) and action_scope in {"read", "diagnose"} else "standard"
    requires_write_approval = action_scope in {"write_branch", "open_pr", "merge", "deploy"}
    hard_constraints = _extract_hard_constraints(user_input or "")
    required_signer = str(hard_constraints.get("required_signer") or "").strip().lower()
    specialists_required = list(hard_constraints.get("specialists_required") or [])
    specialists_forbidden = list(hard_constraints.get("specialists_forbidden") or [])
    selected_specialists_count_must_be = hard_constraints.get("selected_specialists_count_must_be")
    multi_specialist_constraint = len(specialists_required) > 1
    orion_only = _looks_like_orion_only_request(user_input or "")
    if multi_specialist_constraint:
        orion_only = False
    elif required_signer == "orion":
        orion_only = True
    team_technical_audit = _looks_like_team_technical_audit_request(user_input or "")
    excluded_agents = _dedupe_preserve(_excluded_agents(user_input or "") + specialists_forbidden)

    if incremental_dispatch_followup:
        team_technical_audit = False
        platform_improvement_review = False
        orion_only = True
    elif orion_only or team_technical_audit:
        capability_name = capability_name or "platform_self_audit"
        intent = "platform_self_audit"
        platform_improvement_review = False

    runtime_kind = (
        "dispatch_incremental_followup"
        if incremental_dispatch_followup
        else (
            "controlled_self_evolution_propose_only"
            if platform_improvement_review
            else (intent if intent != "general_guidance" else "")
        )
    )

    governance_decision = evaluate_governance_action(
        action_scope=action_scope,
        capability_name=capability_name,
        target_scope=target_scope,
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )

    if incremental_dispatch_followup:
        recommended_agents = _apply_dispatch_constraints(
            ["orion", "auditor", "cto"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or "orion",
            count_must_be=selected_specialists_count_must_be,
        )
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "orion_incremental_dispatch_followup_v1"
        structured_output = True
        expected_specialist_reports = list(recommended_agents or ["orion", "auditor", "cto"])
        visible_signer_expected = required_signer or "orion"
    elif platform_improvement_review:
        recommended_agents = _apply_dispatch_constraints(
            ["orkio", "orion", "auditor", "cto", "architect", "devops", "security", "ux_frontend"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or "orkio",
            count_must_be=selected_specialists_count_must_be,
        )
        advisor_agents = _dedupe_preserve((recommended_agents or ["orion", "auditor", "cto"]) + ["metatron"])
        target_agent = required_signer or (recommended_agents[0] if recommended_agents else "orkio")
        delivery_contract = "platform_improvement_review_v1"
        structured_output = True
        expected_specialist_reports = list(recommended_agents or ["orion", "auditor", "cto", "architect", "devops", "security", "ux_frontend"])
        visible_signer_expected = required_signer or target_agent
    elif team_technical_audit:
        recommended_agents = _apply_dispatch_constraints(
            ["orion", "auditor", "cto"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or "orion",
            count_must_be=selected_specialists_count_must_be,
        )
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "orion_team_technical_audit_v1"
        structured_output = True
        expected_specialist_reports = list(recommended_agents or ["orion", "auditor", "cto"])
        visible_signer_expected = required_signer or "orion"
    else:
        recommended_agents = _apply_dispatch_constraints(
            ["orion"] if (orion_only or capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"}) else ["orkio"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or ("orion" if orion_only else None),
            count_must_be=selected_specialists_count_must_be,
        )
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or ("orion" if (orion_only or capability_name in {"platform_self_audit", "github_repo_write", "github_pr_prepare"}) else "orkio")
        delivery_contract = "orkio_governed_runtime_v1"
        structured_output = False
        expected_specialist_reports = list(recommended_agents if specialists_required else [])
        visible_signer_expected = required_signer or ("orion" if orion_only else None)

    runtime_op = {
        "kind": runtime_kind,
        "action_scope": action_scope,
        "target_scope": target_scope,
        "capability_name": capability_name,
        "admin_access_mode": admin_access_mode,
        "requires_write_approval": requires_write_approval,
        "visible_signer_expected": visible_signer_expected,
        "visible_only_agent": required_signer or visible_signer_expected,
        "excluded_agents": excluded_agents,
        "team_technical_audit": bool(team_technical_audit),
        "platform_improvement_review": bool(platform_improvement_review),
        "incremental_dispatch_followup": bool(incremental_dispatch_followup),
        "hard_constraints_present": bool(hard_constraints.get("has_hard_constraints")),
        "required_signer": required_signer or None,
        "specialists_required": specialists_required,
        "specialists_forbidden": specialists_forbidden,
        "selected_specialists_count_must_be": selected_specialists_count_must_be,
        "requested_specialists": list(specialists_required or recommended_agents),
        "execution_mode": (
            "incremental_analysis"
            if incremental_dispatch_followup
            else (
                "propose_only_dispatch"
                if platform_improvement_review
                else ("read_only_dispatch" if team_technical_audit else None)
            )
        ),
        "followup_mode": "incremental_analysis" if incremental_dispatch_followup else None,
        "followup_subtype": "root_causes_risks_next_actions" if incremental_dispatch_followup else None,
        "use_dispatch_context_only": bool(incremental_dispatch_followup),
        "suppress_receipt_body": bool(incremental_dispatch_followup),
        "derivation_basis": (
            ["specialist_reports", "technical_summary", "final_consolidation", "confirmed_evidence"]
            if incremental_dispatch_followup
            else []
        ),
        "expected_specialist_reports": expected_specialist_reports,
        "force_dispatch": bool(platform_improvement_review or incremental_dispatch_followup),
    }

    payload = {
        "intent": intent,
        "confidence": (
            0.99 if platform_improvement_review
            else (0.99 if incremental_dispatch_followup else (0.98 if runtime_op.get("kind") else 0.62))
        ),
        "recommended_agents": recommended_agents,
        "advisor_agents": advisor_agents,
        "runtime_operation": runtime_op,
        "requires_runtime_execution": bool(runtime_op.get("kind")),
        "target_agent": target_agent,
        "delivery_contract": delivery_contract,
        "structured_output": structured_output,
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
        "platform_improvement_review": bool(platform_improvement_review),
        "incremental_dispatch_followup": bool(incremental_dispatch_followup),
        "expected_specialist_reports": expected_specialist_reports,
        "has_completed_dispatch_context": bool(has_completed_dispatch_context),
        "hard_constraints": hard_constraints,
    }
    payload.update(_runtime_self_audit_override(intent))
    return payload
