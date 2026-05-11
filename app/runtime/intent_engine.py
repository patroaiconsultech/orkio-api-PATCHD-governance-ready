# EFATA 777 V7 COMPLETE
# Consolidated package for governed capability answers + analytical readonly + registry alignment + realtime self-heal hardening.

from __future__ import annotations

from typing import Any, Dict, Optional
import json
import re

from app.config.runtime import RUNTIME_FLAGS
from app.services.governance_service import evaluate_governance_action
from app.runtime.capability_registry import is_team_roster_question_text, is_presence_status_question_text, is_war_room_readonly_architecture_plan_text, is_readonly_implementation_plan_text, get_full_agent_roster


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, terms: list[str]) -> bool:
    txt = _normalize(text)
    return any(_normalize(term) in txt for term in terms if term)


def _extract_embedded_runtime_payload(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    candidates: list[str] = []
    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        candidate = raw[first:last + 1].strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _continuous_audit_effective_text(text: str) -> str:
    payload = _extract_embedded_runtime_payload(text or "")
    nested = payload.get("message") if isinstance(payload, dict) else None
    return str(nested or text or "")


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
    raw = _normalize(str(cleaned or "").replace("@", " "))
    raw = raw.replace("/", "_").replace("-", "_").replace(" ", "_")
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        return ""
    aliases = {
        "ux_frontend": "ux_frontend",
        "ux_front": "ux_frontend",
        "ux": "ux_frontend",
        "frontend": "ux_frontend",
        "front_end": "ux_frontend",
        "frontend_ux": "ux_frontend",
        "ui_ux": "ux_frontend",
        "uiux": "ux_frontend",
        "uxui": "ux_frontend",
        "ux_front_end": "ux_frontend",
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


def _context_list(context: Dict[str, Any], key: str) -> list[str]:
    value = context.get(key)
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return _dedupe_preserve([str(item or "") for item in items if str(item or "").strip()])


def _payload_target_agent_from_context(context: Dict[str, Any]) -> str:
    for key in ("target_agent_from_payload", "target_agent_frozen", "target_agent_slug"):
        target = _canonical_dispatch_actor(context.get(key) or "")
        if target:
            return target
    visible = _canonical_dispatch_actor(context.get("visible_agent") or "")
    return visible


def _payload_target_agents_from_context(context: Dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("target_agents_from_payload", "target_agents_frozen", "requested_agent_names"):
        candidates.extend(_context_list(context, key))
    single = _payload_target_agent_from_context(context)
    if single:
        candidates.insert(0, single)
    host_tokens = {"team", "time", "equipe", "board", "conselho", "orion", "orkio", "chris"}
    return [x for x in _dedupe_preserve(candidates) if x not in host_tokens]


def _payload_dest_mode(context: Dict[str, Any]) -> str:
    raw = str(context.get("dest_mode") or "").strip().lower()
    return raw if raw in {"team", "single", "multi"} else ""


def _payload_operational_dispatch_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    return _contains_any(txt, [
        "peça",
        "peca",
        "acione",
        "orquestre",
        "orquestrar",
        "solicite",
        "pergunte",
        "mande",
        "façam",
        "facam",
        "faça",
        "faca",
        "análise",
        "analise",
        "auditoria",
        "audit",
        "status",
        "estás online",
        "estas online",
        "online",
    ])


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


def _looks_like_explicit_approval_or_execution_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    return _contains_any(txt, [
        "aprovar",
        "aprove",
        "approve",
        "approval",
        "execute",
        "executar",
        "execução",
        "execucao",
        "can_approve",
        "can_execute",
        "action_taken",
        "prossiga somente se houver proposal válida",
        "prossiga somente se houver proposal valida",
    ])


def _looks_like_team_technical_audit_request(text: str) -> bool:
    """Detecta pedidos de auditoria/análise técnica read-only do code/runtime."""
    txt = _normalize(text)
    if not txt:
        return False

    has_team = bool(re.search(r"@team\b|\bteam\b|\bequipe\b|\bsquad\b|\bespecialistas\b|\bwar room\b", txt, flags=re.IGNORECASE))
    has_explicit_specialists = sum(
        1
        for handle in ("@orion", "@auditor", "@cto", "@ux_frontend", "@ux/frontend")
        if handle in txt
    ) >= 2

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
        "análise arquitetural",
        "analise arquitetural",
        "análise detalhada",
        "analise detalhada",
        "recomendação consolidada",
        "recomendacao consolidada",
        "melhorias priorizadas",
    ])

    has_technical_scope = _contains_any(txt, [
        "code",
        "codebase",
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
        "chat stream",
        "sse",
        "github bridge",
    ])

    read_only = (
        _contains_any(txt, ["read-only", "read only", "somente leitura", "sem escrever", "não escrever", "nao escrever", "não executar", "nao executar"])
        or not _contains_any(txt, ["aplicar patch", "criar branch", "abrir pr", "merge", "deploy", "escrever arquivo"])
    )

    return bool((has_team or has_explicit_specialists) and has_audit and has_technical_scope and read_only)


def _looks_like_final_readonly_analysis_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False

    has_analysis = _contains_any(txt, [
        "análise detalhada",
        "analise detalhada",
        "análise arquitetural",
        "analise arquitetural",
        "auditoria técnica",
        "auditoria tecnica",
        "auditoria externa",
        "diagnóstico técnico",
        "diagnostico tecnico",
        "diagnóstico",
        "diagnostico",
        "parecer técnico",
        "parecer tecnico",
        "auditoria externa técnica",
        "auditoria externa tecnica",
        "resposta técnica",
        "resposta tecnica",
        "melhorias priorizadas",
        "recomendações priorizadas",
        "recomendacoes priorizadas",
        "recomendação consolidada",
        "recomendacao consolidada",
        "análise final",
        "analise final",
        "análise técnica final",
        "analise tecnica final",
        "análise técnica",
        "analise tecnica",
    ])
    has_code_scope = _contains_any(txt, [
        "code",
        "codebase",
        "código",
        "codigo",
        "runtime",
        "backend",
        "frontend",
        "console",
        "chat stream",
        "sse",
        "intent",
        "governança",
        "governanca",
        "github bridge",
        "ux",
        "orkio",
        "plataforma",
        "sistema",
        "arquitetura",
        "técnica",
        "tecnica",
        "técnico",
        "tecnico",
        "análise técnica",
        "analise tecnica",
    ])
    read_only = _contains_any(txt, [
        "read-only",
        "read only",
        "modo read-only",
        "modo read only",
        "somente leitura",
        "não executar",
        "nao executar",
        "não abrir pr",
        "nao abrir pr",
        "não escrever",
        "nao escrever",
    ])
    wants_final_output = _contains_any(txt, [
        "entregue apenas a análise final",
        "entregar apenas a análise final",
        "entregue apenas analise final",
        "não retorne trace",
        "nao retorne trace",
        "não resolva squad",
        "nao resolva squad",
        "apenas a análise final",
        "apenas a analise final",
    ])

    # Aceita prompts mais curtos de auditoria externa/diagnóstico técnico da plataforma,
    # desde que estejam claramente em modo read-only e peçam uma saída final analítica.
    return bool(has_analysis and has_code_scope and read_only and wants_final_output)


def _looks_like_governance_capability_question(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False

    asks_question = ("?" in str(text or "")) or _contains_any(txt, [
        "temos a capacidade",
        "tem capacidade",
        "podemos",
        "é possível",
        "e possivel",
        "eh possivel",
    ])
    asks_write_domain = _contains_any(txt, [
        "aplicar melhorias no code",
        "aplicar melhorias no código",
        "aplicar melhorias no codigo",
        "aplicar melhorias no codebase",
        "melhorias no code",
        "melhorias no código",
        "melhorias no codigo",
        "alterar o código",
        "alterar o codigo",
        "patch no code",
        "abrir pr",
        "pull request",
        "criar branch",
        "commit",
        "merge",
        "deploy",
    ])
    asks_governance = _contains_any(txt, [
        "aprovação",
        "aprovacao",
        "autorização",
        "autorizacao",
        "approval",
        "authorized",
        "sob minha aprovação",
        "sob minha aprovacao",
        "sob minha autorização",
        "sob minha autorizacao",
        "com minha aprovação",
        "com minha aprovacao",
        "mediante minha aprovação",
        "mediante minha aprovacao",
        "após evidenciar as necessidades",
        "apos evidenciar as necessidades",
        "depois de evidenciar as necessidades",
        "depois de evidenciar",
        "evidenciar as necessidades",
    ])
    return bool(asks_question and asks_write_domain and asks_governance)


def _looks_like_team_roster_question(text: str) -> bool:
    """
    EFATA777_FINAL_AUDITOR_ADJUSTMENT:
    Delegates roster detection to the canonical registry helper so intent_engine.py
    and main.py cannot drift apart.
    """
    return bool(is_team_roster_question_text(text))


def _looks_like_presence_status_question(text: str) -> bool:
    """
    EFATA777_ORION_PRESENCE_AND_SQUAD_PARSE_HOTFIX:
    Presence/status questions must not fall into platform_self_audit just because
    they mention @Orion.
    """
    return bool(is_presence_status_question_text(text))


def _extract_direct_agent_target(text: str) -> str:
    raw = str(text or "")
    txt = _normalize(raw)
    if not txt:
        return ""

    explicit_roster_only = _contains_any(txt, [
        "quem está no time",
        "quem esta no time",
        "quais agentes",
        "quantos agentes",
        "lista de agentes",
        "team roster",
        "roster",
    ])
    if explicit_roster_only:
        return ""

    host_tokens = {"team", "time", "equipe", "board", "conselho", "orion", "orkio", "chris"}

    known_targets = _dedupe_preserve([
        item
        for item in _extract_known_roster_agents_from_text(raw)
        if item and item not in host_tokens
    ])
    if len(known_targets) == 1:
        return known_targets[0]

    raw_handles = re.findall(
        r"@([A-Za-z0-9_\-/]+(?:\s+[A-Za-z0-9_\-/]+){0,2})(?=(?:\s*[,.:;!?])|(?:\s+@)|$)",
        raw,
        flags=re.IGNORECASE,
    )

    handle_targets = _dedupe_preserve([
        _canonical_dispatch_actor(item)
        for item in raw_handles
        if _canonical_dispatch_actor(item) and _canonical_dispatch_actor(item) not in host_tokens
    ])

    if len(handle_targets) == 1:
        return handle_targets[0]

    preferred = _dedupe_preserve(known_targets + handle_targets)
    if len(preferred) == 1:
        return preferred[0]

    return ""


def _looks_like_orchestrator_dispatch_readonly_request(text: str) -> bool:
    raw = str(text or "")
    txt = _normalize(raw)
    if not txt:
        return False
    if _looks_like_team_roster_question(raw):
        return False
    if _extract_direct_agent_target(raw):
        return False

    has_dispatch_verb = _contains_any(txt, [
        "peça",
        "peca",
        "acione",
        "orquestre",
        "orquestre os agentes",
        "orquestre os especialistas",
        "solicite",
        "pergunte",
        "mande",
        "teste se eles respondem",
        "teste se tu tens acesso",
        "teste se eles conseguem receber",
    ])
    requested = _extract_requested_specialists_from_text(raw)
    known = _extract_known_roster_agents_from_text(raw)
    mentions_team = bool(re.search(r"@team\b|\bteam\b|\bequipe\b|\bsquad\b", raw, flags=re.IGNORECASE))
    mentions_orchestrator = bool(re.search(r"@orion\b|@orkio\b|\borion\b|\borkio\b", raw, flags=re.IGNORECASE))
    distinct_agents = _dedupe_preserve(list(requested or []) + list(known or []))

    return bool(has_dispatch_verb and (mentions_team or mentions_orchestrator or len(distinct_agents) >= 2))


def _build_direct_agent_message_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
    target_agent: str,
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name="direct_agent_message",
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "direct_agent_message",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": "direct_agent_message",
        "template_id": "direct_agent_message_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "direct_agent_message",
        "force_dispatch": False,
        "dispatch_attempted": False,
        "dispatch_executed": False,
        "dispatch_receipt_id": None,
        "fallback_used": False,
        "fallback_reason": "",
        "block_roster_fallback": True,
        "target_agent": target_agent,
        "target_agent_frozen": target_agent,
        "requested_specialists": [target_agent],
        "expected_specialist_reports": [],
    }
    return {
        "intent": "direct_agent_message",
        "confidence": 0.995,
        "recommended_agents": [target_agent],
        "advisor_agents": [target_agent],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": target_agent,
        "target_agent_frozen": target_agent,
        "block_roster_fallback": True,
        "delivery_contract": "direct_agent_message_v1",
        "template_id": "direct_agent_message_v1",
        "structured_output": False,
        "first_win_goal": "route_direct_agent_message",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": "direct_agent_message",
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def _build_orchestrator_dispatch_readonly_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name="orchestrator_dispatch_readonly",
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    requested = _payload_target_agents_from_context(context) or _extract_requested_specialists_from_text(effective_user_input or raw_user_input or "")
    runtime_op = {
        "kind": "orchestrator_dispatch_readonly",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": "orchestrator_dispatch_readonly",
        "template_id": "orchestrator_dispatch_readonly_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "orchestrator_dispatch_readonly",
        "force_dispatch": False,
        "dispatch_attempted": False,
        "dispatch_executed": False,
        "dispatch_receipt_id": None,
        "fallback_used": False,
        "fallback_reason": "",
        "block_roster_fallback": True,
        "target_agent": "orion",
        "target_agents_frozen": list(requested or []),
        "requested_specialists": list(requested or []),
        "expected_specialist_reports": list(requested or []),
    }
    return {
        "intent": "orchestrator_dispatch_readonly",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": _dedupe_preserve(["orion"] + list(requested or [])),
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "target_agents_frozen": list(requested or []),
        "block_roster_fallback": True,
        "delivery_contract": "orchestrator_dispatch_readonly_v1",
        "template_id": "orchestrator_dispatch_readonly_v1",
        "structured_output": True,
        "first_win_goal": "route_orchestrator_dispatch_readonly",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": "orchestrator_dispatch_readonly",
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def _looks_like_war_room_readonly_architecture_plan(text: str) -> bool:
    """
    EFATA777_WAR_ROOM_READONLY_PLAN_INTENT_PATCH:
    Plano técnico/arquitetural read-only para receipts/lineage/accountability.
    Deve ter precedência sobre self-audit, runtime capability e autorização operacional.
    """
    return bool(is_war_room_readonly_architecture_plan_text(text))


def _looks_like_readonly_implementation_plan(text: str) -> bool:
    """
    EFATA777_READONLY_IMPLEMENTATION_PLAN_INTENT_PATCH:
    Plano técnico de implementação/patch em modo read-only.
    Deve ter precedência sobre governança operacional, self-audit e runtime.
    """
    return bool(is_readonly_implementation_plan_text(text))


def _looks_like_squad_resolution_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    markers = [
        "resolva exatamente este squad",
        "resolver este squad",
        "resolver squad",
        "squad resolvido",
        "resolve exactly this squad",
        "resolve this squad",
    ]
    return _contains_any(txt, markers) or bool(re.search(r"(?im)^\s*squad\s*:", str(text or "")))


def _looks_like_squad_resolution_trace_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False
    trace_fields = [
        "requested_specialists_raw",
        "requested_specialists_normalized",
        "selected_specialists_before_policy",
        "selected_specialists_after_policy",
        "abort_reason",
    ]
    if all(field in txt for field in trace_fields[-3:]):
        return True
    return (
        "retorne apenas" in txt
        and any(field in txt for field in trace_fields)
    )


def _extract_known_roster_agents_from_text(text: str) -> list[str]:
    """
    Extracts only canonical agent ids from free text.
    Prevents tokens like "backend_engineer._modo_read_only._não_execute_dispatch"
    from becoming specialist ids.
    """
    raw = str(text or "").lower().replace("@", " ")
    normalized = re.sub(r"[^a-z0-9_]+", "_", raw)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    padded = f"_{normalized}_"
    out: list[str] = []
    seen: set[str] = set()
    for agent in list(get_full_agent_roster() or []):
        slug = str(agent or "").strip().lower()
        if not slug:
            continue
        token = f"_{slug}_"
        if token in padded and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


def _extract_requested_specialists_from_text(text: str) -> list[str]:
    hard_constraints = _extract_hard_constraints(text or "")
    required = _dedupe_preserve(list(hard_constraints.get("specialists_required") or []))
    if required:
        return required

    known_agents = _extract_known_roster_agents_from_text(text or "")
    if known_agents and _looks_like_squad_resolution_request(text or ""):
        return _dedupe_preserve(known_agents)

    lines = [str(line or "").strip() for line in str(text or "").splitlines()]
    collected: list[str] = []
    capture = False
    for line in lines:
        lowered = _normalize(line)
        if not capture and (
            "resolva exatamente este squad" in lowered
            or "resolver este squad" in lowered
            or "resolver squad" in lowered
            or "resolve exactly this squad" in lowered
            or lowered.startswith("squad:")
        ):
            capture = True
            if ":" in line:
                inline = line.split(":", 1)[1].strip()
                if inline:
                    parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", inline)]
                    collected.extend([p for p in parts if p])
            continue
        if not capture:
            continue
        if not line:
            if collected:
                break
            continue
        if lowered.startswith(("responda apenas", "retorne apenas", "não execute dispatch", "nao execute dispatch", "modo read-only", "modo read only", "agente visível final", "agente visivel final")):
            if collected:
                break
            continue
        parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", line)]
        cleaned_parts = [p for p in parts if p]
        if cleaned_parts:
            collected.extend(cleaned_parts)
            continue
        if collected:
            break

    return _dedupe_preserve(collected)


def _build_squad_readonly_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
    trace_mode: bool,
) -> Dict[str, Any]:
    hard_constraints = _extract_hard_constraints(effective_user_input or raw_user_input or "")
    required_signer = str(hard_constraints.get("required_signer") or "").strip().lower() or "orion"
    specialists_required = list(hard_constraints.get("specialists_required") or [])
    specialists_forbidden = list(hard_constraints.get("specialists_forbidden") or [])
    selected_specialists_count_must_be = hard_constraints.get("selected_specialists_count_must_be")
    requested_specialists = _extract_requested_specialists_from_text(effective_user_input or raw_user_input or "") or specialists_required

    capability_name = "squad_resolution_trace_readonly" if trace_mode else "squad_resolve_readonly"
    template_id = "squad_resolution_trace_readonly_template_v1" if trace_mode else "squad_resolve_readonly_template_v1"
    delivery_contract = "squad_resolution_trace_readonly_v1" if trace_mode else "squad_resolve_readonly_v1"

    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=capability_name,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )

    recommended_agents = _dedupe_preserve([required_signer])
    advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])

    runtime_op = {
        "kind": capability_name,
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": capability_name,
        "template_id": template_id,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "visible_signer_expected": required_signer,
        "visible_only_agent": required_signer,
        "excluded_agents": _dedupe_preserve(_excluded_agents(effective_user_input or raw_user_input or "") + specialists_forbidden),
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "incremental_dispatch_followup": False,
        "hard_constraints_present": bool(hard_constraints.get("has_hard_constraints")),
        "required_signer": required_signer,
        "specialists_required": specialists_required,
        "specialists_forbidden": specialists_forbidden,
        "selected_specialists_count_must_be": selected_specialists_count_must_be,
        "requested_specialists": list(requested_specialists),
        "execution_mode": "read_only_squad_trace" if trace_mode else "read_only_squad_resolution",
        "followup_mode": None,
        "followup_subtype": None,
        "use_dispatch_context_only": False,
        "suppress_receipt_body": False,
        "derivation_basis": [],
        "expected_specialist_reports": list(requested_specialists),
        "force_dispatch": False,
        "squad_resolution_request": not trace_mode,
        "squad_resolution_trace_request": trace_mode,
        "continuous_audit_supported": False,
        "requested_job_id": None,
        "use_latest_continuous_audit_job": False,
    }

    return {
        "intent": capability_name,
        "confidence": 0.995,
        "recommended_agents": recommended_agents,
        "advisor_agents": advisor_agents,
        "runtime_operation": runtime_op,
        "requires_runtime_execution": True,
        "target_agent": required_signer,
        "delivery_contract": delivery_contract,
        "template_id": template_id,
        "structured_output": True,
        "first_win_goal": "execute_orion_runtime",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": capability_name,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": list(requested_specialists),
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": hard_constraints,
        "requested_job_id": None,
    }


def _extract_continuous_audit_job_id(text: str) -> str:
    payload = _extract_embedded_runtime_payload(text or "")
    if isinstance(payload, dict):
        for key in ("job_id", "audit_job_id", "continuous_audit_job_id", "requested_job_id"):
            value = payload.get(key)
            if value not in (None, "", "null"):
                return str(value).strip().lower()
        nested_message = payload.get("message")
        if nested_message:
            nested_found = _extract_continuous_audit_job_id(str(nested_message))
            if nested_found:
                return nested_found
    raw = _continuous_audit_effective_text(text or "")
    if not raw:
        return ""
    patterns = [
        r"(?im)^\s*job_id\s*[:=]\s*([a-f0-9-]{8,})\s*$",
        r"\bjob[_ -]?id\s*[:=]?\s*([a-f0-9-]{8,})\b",
        r"/api/admin/audit-jobs/([a-f0-9-]{8,})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip().lower()
    return ""


def _looks_like_continuous_audit_status_request(text: str) -> bool:
    payload = _extract_embedded_runtime_payload(text or "")
    effective_text = _continuous_audit_effective_text(text or "")
    txt = _normalize(effective_text)
    if not txt:
        return False
    explicit_job_id = _extract_continuous_audit_job_id(text)
    explicit_mode = _normalize(str((payload or {}).get("mode") or (payload or {}).get("operation") or (payload or {}).get("kind") or (payload or {}).get("intent") or ""))
    if explicit_mode in {"continuous_audit_job_status", "read_status", "status"}:
        return True
    status_markers = [
        "consultar status",
        "forneça o status",
        "forneca o status",
        "status do continuous audit",
        "status do continuous audit job",
        "status do job",
        "status da auditoria contínua",
        "status da auditoria continua",
        "job existente",
        "job persistido mais recente",
        "usar somente o job_id",
        "não criar novo job",
        "nao criar novo job",
        "proibido criar novo job",
        "mais recente",
    ]
    create_markers = [
        "iniciar auditoria contínua",
        "iniciar auditoria continua",
        "iniciar continuous audit",
        "criar novo job",
        "iniciar job",
        "start continuous audit",
        "execute continuous audit",
    ]
    asks_status = _contains_any(txt, status_markers) or bool(explicit_job_id)
    asks_create = _contains_any(txt, create_markers)
    return bool(asks_status and not asks_create)


def _looks_like_continuous_audit_request(text: str) -> bool:
    payload = _extract_embedded_runtime_payload(text or "")
    effective_text = _continuous_audit_effective_text(text or "")
    txt = _normalize(effective_text)
    if not txt or _looks_like_continuous_audit_status_request(text):
        return False
    explicit_mode = _normalize(str((payload or {}).get("mode") or (payload or {}).get("operation") or (payload or {}).get("kind") or (payload or {}).get("intent") or ""))
    if explicit_mode in {"continuous_audit_job", "create_continuous_audit_job", "start_continuous_audit"}:
        return True
    markers = [
        "auditoria contínua",
        "auditoria continua",
        "continuous audit",
        "continuous_audit",
        "job persistido",
        "job_id",
        "progresso rastreável",
        "progresso rastreavel",
        "execução contínua",
        "execucao continua",
        "audit job",
        "auditoria rastreável",
        "auditoria rastreavel",
    ]
    return _contains_any(txt, markers)

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


def _looks_like_pwa_console_repair_request(text: str) -> bool:
    txt = _normalize(text)
    if not txt:
        return False

    scope_markers = [
        "pwa",
        "app console",
        "console",
        "threads",
        "thread",
        "agentes",
        "agents",
        "sidebar",
        "frontend",
        "ux",
        "seleção de threads",
        "selecao de threads",
        "seleção de agentes",
        "selecao de agentes",
    ]
    repair_markers = [
        "corrigir",
        "corrija",
        "correção",
        "correcao",
        "consertar",
        "conserte",
        "restaurar",
        "restaure",
        "ajustar",
        "ajuste",
        "executar correção",
        "executar correcao",
        "aplicar correção",
        "aplicar correcao",
        "aplicar patch",
        "aplique o patch",
        "fix",
        "repair",
        "deixar de abortar",
        "voltar a aparecer",
        "reaparecer",
    ]
    return _contains_any(txt, scope_markers) and _contains_any(txt, repair_markers)


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
    if _looks_like_squad_resolution_request(text) or _looks_like_squad_resolution_trace_request(text):
        return "read"
    if _looks_like_continuous_audit_status_request(text):
        return "read"
    if _looks_like_privileged_admin_read(txt):
        return "read"
    if _looks_like_pwa_console_repair_request(text):
        return "write_branch"
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
    if _looks_like_continuous_audit_request(txt):
        return "diagnose"
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
    if _looks_like_squad_resolution_trace_request(text):
        return "squad_resolution_trace_readonly"
    if _looks_like_squad_resolution_request(text):
        return "squad_resolve_readonly"
    if _looks_like_continuous_audit_status_request(text):
        return "continuous_audit_job_status"
    if _looks_like_platform_improvement_review_request(txt):
        return "controlled_self_evolution_propose_only"
    if _looks_like_continuous_audit_request(txt):
        return "continuous_audit_job"
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


def _build_governance_capability_answer_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=None,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "template_id": "governance_capability_answer_template_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": True,
        "execution_mode": "governance_capability_answer",
        "force_dispatch": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": True,
        "requested_specialists": [],
        "expected_specialist_reports": [],
        "requires_explicit_approval_for_write": True,
    }
    return {
        "intent": "governance_capability_answer",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": ["orion"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "delivery_contract": "governance_capability_answer_v1",
        "template_id": "governance_capability_answer_template_v1",
        "structured_output": True,
        "first_win_goal": "deliver_governance_capability_answer",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": True,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": True,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": [],
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def _build_presence_status_answer_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=None,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "template_id": "presence_status_answer_template_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "presence_status_answer",
        "force_dispatch": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": True,
        "requested_specialists": [],
        "expected_specialist_reports": [],
        "requires_explicit_approval_for_write": True,
    }
    return {
        "intent": "presence_status_answer",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": ["orion"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "delivery_contract": "presence_status_answer_v1",
        "template_id": "presence_status_answer_template_v1",
        "structured_output": True,
        "first_win_goal": "deliver_presence_status_answer",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": True,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": [],
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def _build_team_roster_answer_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=None,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "template_id": "team_roster_answer_template_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "team_roster_answer",
        "force_dispatch": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": True,
        "requested_specialists": [],
        "expected_specialist_reports": [],
        "requires_explicit_approval_for_write": True,
    }
    return {
        "intent": "team_roster_answer",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": ["orion"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "delivery_contract": "team_roster_answer_v1",
        "template_id": "team_roster_answer_template_v1",
        "structured_output": True,
        "first_win_goal": "deliver_team_roster_answer",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": True,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": [],
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }




def _build_readonly_implementation_plan_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=None,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "template_id": "readonly_implementation_plan_template_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "readonly_implementation_plan",
        "force_dispatch": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": False,
        "war_room_readonly_architecture_plan": False,
        "readonly_implementation_plan": True,
        "requested_specialists": [],
        "expected_specialist_reports": [],
        "requires_explicit_approval_for_write": True,
    }
    return {
        "intent": "readonly_implementation_plan",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": ["orion", "cto", "auditor", "backend_engineer", "devops_sre", "qa_release_engineer"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "delivery_contract": "readonly_implementation_plan_v1",
        "template_id": "readonly_implementation_plan_template_v1",
        "structured_output": True,
        "first_win_goal": "deliver_readonly_implementation_plan",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": False,
        "war_room_readonly_architecture_plan": False,
        "readonly_implementation_plan": True,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": [],
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def _build_war_room_readonly_architecture_plan_payload(
    *,
    raw_user_input: str,
    effective_user_input: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    governance_decision = evaluate_governance_action(
        action_scope="read",
        capability_name=None,
        target_scope="platform",
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )
    runtime_op = {
        "kind": "",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "template_id": "war_room_readonly_architecture_plan_template_v1",
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "execution_mode": "war_room_readonly_architecture_plan",
        "force_dispatch": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": False,
        "war_room_readonly_architecture_plan": True,
        "requested_specialists": [],
        "expected_specialist_reports": [],
        "requires_explicit_approval_for_write": True,
    }
    return {
        "intent": "war_room_readonly_architecture_plan",
        "confidence": 0.995,
        "recommended_agents": ["orion"],
        "advisor_agents": ["orion", "cto", "auditor", "devops_sre", "security_guardian"],
        "runtime_operation": runtime_op,
        "requires_runtime_execution": False,
        "target_agent": "orion",
        "delivery_contract": "war_room_readonly_architecture_plan_v1",
        "template_id": "war_room_readonly_architecture_plan_template_v1",
        "structured_output": True,
        "first_win_goal": "deliver_war_room_readonly_architecture_plan",
        "action_scope": "read",
        "target_scope": "platform",
        "capability_name": None,
        "governance_decision": governance_decision,
        "allowed": bool(governance_decision.get("allowed")),
        "requires_human_authorization": False,
        "admin_access_mode": "standard",
        "requires_write_approval": False,
        "team_technical_audit": False,
        "platform_improvement_review": False,
        "continuous_audit_request": False,
        "continuous_audit_status_request": False,
        "final_readonly_analysis_request": False,
        "governance_capability_question": False,
        "team_roster_question": False,
        "presence_status_question": False,
        "war_room_readonly_architecture_plan": True,
        "incremental_dispatch_followup": False,
        "expected_specialist_reports": [],
        "has_completed_dispatch_context": bool(_has_completed_dispatch_context(context)),
        "hard_constraints": _extract_hard_constraints(effective_user_input or raw_user_input or ""),
        "requested_job_id": None,
    }


def build_intent_package(
    user_input: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    raw_user_input = user_input or ""
    effective_user_input = _continuous_audit_effective_text(raw_user_input)
    text = _normalize(effective_user_input)
    context = dict(context or {})
    context["message"] = effective_user_input
    context["raw_message"] = raw_user_input

    # EFATA777_DESTINATION_CONTRACT_V1:
    # Explicit frontend destination contract has precedence over textual roster
    # detection. This prevents @Team/@UX ambiguity from winning over target freeze.
    payload_target = _payload_target_agent_from_context(context)
    payload_targets = _payload_target_agents_from_context(context)
    payload_mode = _payload_dest_mode(context)
    payload_has_destination = bool(context.get("destination_contract_used") or payload_target or payload_targets or payload_mode)

    if payload_target:
        return _build_direct_agent_message_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
            target_agent=payload_target,
        )

    if payload_has_destination and payload_mode in {"multi", "team"} and (
        len(payload_targets) >= 1 or _payload_operational_dispatch_request(effective_user_input or raw_user_input or "")
    ):
        return _build_orchestrator_dispatch_readonly_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    session_is_admin_master = bool(context.get("session_is_admin_master"))
    session_write_approval_authority = bool(context.get("session_write_approval_authority"))
    session_admin_console_access = bool(context.get("session_admin_console_access"))
    if session_write_approval_authority and _looks_like_explicit_approval_or_execution_request(effective_user_input or raw_user_input or ""):
        context["explicit_authorization"] = True
        context["authorization_present"] = True

    final_readonly_analysis_request = _looks_like_final_readonly_analysis_request(effective_user_input or raw_user_input or "")

    if (not final_readonly_analysis_request) and _looks_like_readonly_implementation_plan(effective_user_input or raw_user_input or ""):
        return _build_readonly_implementation_plan_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    if (not final_readonly_analysis_request) and _looks_like_war_room_readonly_architecture_plan(effective_user_input or raw_user_input or ""):
        return _build_war_room_readonly_architecture_plan_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    direct_agent_target = _extract_direct_agent_target(effective_user_input or raw_user_input or "")
    if direct_agent_target:
        return _build_direct_agent_message_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
            target_agent=direct_agent_target,
        )

    if _looks_like_orchestrator_dispatch_readonly_request(effective_user_input or raw_user_input or ""):
        return _build_orchestrator_dispatch_readonly_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    if (not final_readonly_analysis_request) and _looks_like_presence_status_question(effective_user_input or raw_user_input or ""):
        return _build_presence_status_answer_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    if (not final_readonly_analysis_request) and _looks_like_team_roster_question(effective_user_input or raw_user_input or ""):
        return _build_team_roster_answer_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    if _looks_like_governance_capability_question(effective_user_input or raw_user_input or ""):
        return _build_governance_capability_answer_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
        )

    if (not final_readonly_analysis_request) and _looks_like_squad_resolution_trace_request(effective_user_input or raw_user_input or ""):
        return _build_squad_readonly_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
            trace_mode=True,
        )

    if (not final_readonly_analysis_request) and _looks_like_squad_resolution_request(effective_user_input or raw_user_input or ""):
        return _build_squad_readonly_payload(
            raw_user_input=raw_user_input,
            effective_user_input=effective_user_input,
            context=context,
            trace_mode=False,
        )

    has_completed_dispatch_context = _has_completed_dispatch_context(context)
    incremental_dispatch_followup = (
        has_completed_dispatch_context
        and _looks_like_incremental_dispatch_followup_request(effective_user_input or raw_user_input or "")
    )
    pwa_console_repair_request = (
        False if incremental_dispatch_followup
        else _looks_like_pwa_console_repair_request(effective_user_input or raw_user_input or "")
    )

    platform_improvement_review = (
        False if (incremental_dispatch_followup or pwa_console_repair_request)
        else _looks_like_platform_improvement_review_request(effective_user_input or raw_user_input or "")
    )
    continuous_audit_status_request = (
        False if incremental_dispatch_followup
        else _looks_like_continuous_audit_status_request(raw_user_input or effective_user_input or "")
    )
    continuous_audit_request = (
        False if (incremental_dispatch_followup or continuous_audit_status_request)
        else _looks_like_continuous_audit_request(raw_user_input or effective_user_input or "")
    )
    requested_job_id = _extract_continuous_audit_job_id(raw_user_input or effective_user_input or "") or None
    final_readonly_analysis_request = bool(final_readonly_analysis_request)
    squad_resolution_trace_request = (
        False if final_readonly_analysis_request else _looks_like_squad_resolution_trace_request(effective_user_input or raw_user_input or "")
    )
    squad_resolution_request = (
        False if (final_readonly_analysis_request or squad_resolution_trace_request) else _looks_like_squad_resolution_request(effective_user_input or raw_user_input or "")
    )
    requested_squad_specialists = _extract_requested_specialists_from_text(effective_user_input or raw_user_input or "")

    action_scope = _infer_action_scope(text)
    target_scope = _infer_target_scope(text)
    capability_name = _infer_capability(action_scope, text)

    if final_readonly_analysis_request:
        intent = "analytical_final_readonly"
        capability_name = None
        action_scope = "read"
        target_scope = "platform"
    elif squad_resolution_trace_request:
        intent = "squad_resolution_trace_readonly"
        capability_name = "squad_resolution_trace_readonly"
        action_scope = "read"
        target_scope = "platform"
    elif squad_resolution_request:
        intent = "squad_resolve_readonly"
        capability_name = "squad_resolve_readonly"
        action_scope = "read"
        target_scope = "platform"
    elif pwa_console_repair_request:
        intent = "pwa_console_repair"
        capability_name = "github_repo_write"
        action_scope = "write_branch"
        target_scope = "frontend"
    elif incremental_dispatch_followup:
        intent = "dispatch_incremental_followup"
        capability_name = "platform_self_audit"
        action_scope = "diagnose"
        target_scope = "platform"
    elif continuous_audit_status_request or capability_name == "continuous_audit_job_status":
        intent = "continuous_audit_job_status"
        capability_name = "continuous_audit_job_status"
        action_scope = "read"
        target_scope = "platform"
    elif continuous_audit_request or capability_name == "continuous_audit_job":
        intent = "continuous_audit_job"
        capability_name = "continuous_audit_job"
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
    hard_constraints = _extract_hard_constraints(effective_user_input or raw_user_input or "")
    required_signer = str(hard_constraints.get("required_signer") or "").strip().lower()
    specialists_required = list(hard_constraints.get("specialists_required") or [])
    specialists_forbidden = list(hard_constraints.get("specialists_forbidden") or [])
    selected_specialists_count_must_be = hard_constraints.get("selected_specialists_count_must_be")
    multi_specialist_constraint = len(specialists_required) > 1
    orion_only = _looks_like_orion_only_request(effective_user_input or raw_user_input or "")
    if multi_specialist_constraint:
        orion_only = False
    elif required_signer == "orion":
        orion_only = True
    team_technical_audit = _looks_like_team_technical_audit_request(effective_user_input or raw_user_input or "")
    excluded_agents = _dedupe_preserve(_excluded_agents(effective_user_input or raw_user_input or "") + specialists_forbidden)

    if final_readonly_analysis_request:
        squad_resolution_trace_request = False
        squad_resolution_request = False
        platform_improvement_review = False
        continuous_audit_request = False
        continuous_audit_status_request = False
        incremental_dispatch_followup = False
        team_technical_audit = False
        orion_only = False
    elif squad_resolution_trace_request or squad_resolution_request:
        team_technical_audit = False
        platform_improvement_review = False
        continuous_audit_request = False
        continuous_audit_status_request = False
        incremental_dispatch_followup = False
        orion_only = True
    elif incremental_dispatch_followup:
        team_technical_audit = False
        platform_improvement_review = False
        continuous_audit_request = False
        continuous_audit_status_request = False
        orion_only = True
    elif continuous_audit_status_request:
        capability_name = "continuous_audit_job_status"
        intent = "continuous_audit_job_status"
        platform_improvement_review = False
        continuous_audit_request = False
        team_technical_audit = False
    elif continuous_audit_request:
        capability_name = "continuous_audit_job"
        intent = "continuous_audit_job"
        platform_improvement_review = False
    elif pwa_console_repair_request:
        capability_name = "github_repo_write"
        intent = "pwa_console_repair"
        platform_improvement_review = False
        continuous_audit_request = False
        continuous_audit_status_request = False
        team_technical_audit = False
        orion_only = True
    elif team_technical_audit or (
        orion_only
        and not _looks_like_explicit_approval_or_execution_request(effective_user_input or raw_user_input or "")
        and (capability_name == "platform_self_audit" or action_scope == "diagnose")
    ):
        capability_name = capability_name or "platform_self_audit"
        intent = "platform_self_audit"
        platform_improvement_review = False

    runtime_kind = (
        ""
        if final_readonly_analysis_request
        else (
            "squad_resolution_trace_readonly"
            if squad_resolution_trace_request
            else (
                "squad_resolve_readonly"
                if squad_resolution_request
                else (
                    "dispatch_incremental_followup"
                    if incremental_dispatch_followup
                    else (
                        "continuous_audit_job_status"
                        if continuous_audit_status_request
                        else (
                            "continuous_audit_job"
                            if continuous_audit_request
                            else (
                                "controlled_self_evolution_propose_only"
                                if platform_improvement_review
                                else (intent if intent != "general_guidance" else "")
                            )
                        )
                    )
                )
            )
        )
    )

    governance_decision = evaluate_governance_action(
        action_scope=action_scope,
        capability_name=capability_name,
        target_scope=target_scope,
        context=context,
        safe_mode=bool(context.get("safe_mode", False)),
    )

    template_id = None

    if final_readonly_analysis_request:
        recommended_agents = _dedupe_preserve(["orion"])
        advisor_agents = _dedupe_preserve(["orion", "auditor", "cto", "ux_frontend", "metatron"])
        target_agent = "orion"
        delivery_contract = "analytical_final_readonly_v1"
        template_id = "analytical_final_readonly_template_v1"
        structured_output = True
        expected_specialist_reports = []
        visible_signer_expected = "orion"
    elif squad_resolution_trace_request:
        recommended_agents = _dedupe_preserve([required_signer or "orion"])
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "squad_resolution_trace_readonly_v1"
        template_id = "squad_resolution_trace_readonly_template_v1"
        structured_output = True
        expected_specialist_reports = list(requested_squad_specialists or specialists_required or [])
        visible_signer_expected = required_signer or "orion"
    elif squad_resolution_request:
        recommended_agents = _dedupe_preserve([required_signer or "orion"])
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "squad_resolve_readonly_v1"
        template_id = "squad_resolve_readonly_template_v1"
        structured_output = True
        expected_specialist_reports = list(requested_squad_specialists or specialists_required or [])
        visible_signer_expected = required_signer or "orion"
    elif pwa_console_repair_request:
        recommended_agents = _apply_dispatch_constraints(
            ["orion", "cto", "ux_frontend"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or "orion",
            count_must_be=None,
        )
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "pwa_console_repair_v1"
        template_id = "pwa_console_repair_template_v1"
        structured_output = True
        expected_specialist_reports = list(recommended_agents or ["orion", "cto", "ux_frontend"])
        visible_signer_expected = required_signer or "orion"
    elif incremental_dispatch_followup:
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
    elif continuous_audit_status_request:
        recommended_agents = _dedupe_preserve([required_signer or "orion"])
        advisor_agents = _dedupe_preserve(recommended_agents + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "continuous_audit_job_status_v1"
        structured_output = True
        expected_specialist_reports = []
        visible_signer_expected = required_signer or "orion"
    elif continuous_audit_request:
        recommended_agents = _apply_dispatch_constraints(
            ["orion", "auditor", "cto", "ux_frontend"],
            required=specialists_required,
            forbidden=specialists_forbidden,
            required_signer=required_signer or "orion",
            count_must_be=selected_specialists_count_must_be or 4,
        )
        advisor_agents = _dedupe_preserve((recommended_agents or ["orion", "auditor", "cto", "ux_frontend"]) + ["metatron"])
        target_agent = required_signer or "orion"
        delivery_contract = "continuous_audit_job_v1"
        structured_output = True
        expected_specialist_reports = list(recommended_agents or ["orion", "auditor", "cto", "ux_frontend"])
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
        "template_id": template_id,
        "admin_access_mode": admin_access_mode,
        "requires_write_approval": requires_write_approval,
        "visible_signer_expected": visible_signer_expected,
        "visible_only_agent": required_signer or visible_signer_expected,
        "excluded_agents": excluded_agents,
        "team_technical_audit": bool(team_technical_audit),
        "platform_improvement_review": bool(platform_improvement_review),
        "continuous_audit_request": bool(continuous_audit_request),
        "continuous_audit_status_request": bool(continuous_audit_status_request),
        "final_readonly_analysis_request": bool(final_readonly_analysis_request),
        "best_effort_analysis_required": bool(final_readonly_analysis_request),
        "grounded_analysis_required": bool(final_readonly_analysis_request),
        "disallow_generic_architecture_advice": bool(final_readonly_analysis_request),
        "incremental_dispatch_followup": bool(incremental_dispatch_followup),
        "hard_constraints_present": bool(hard_constraints.get("has_hard_constraints")),
        "required_signer": required_signer or None,
        "specialists_required": specialists_required,
        "specialists_forbidden": specialists_forbidden,
        "selected_specialists_count_must_be": selected_specialists_count_must_be,
        "requested_specialists": list(requested_squad_specialists or specialists_required or recommended_agents),
        "execution_mode": (
            "analytical_final_readonly"
            if final_readonly_analysis_request
            else (
                "incremental_analysis"
                if incremental_dispatch_followup
                else (
                    "read_status"
                    if continuous_audit_status_request
                    else (
                        "read_only_continuous"
                        if continuous_audit_request
                        else (
                            "read_only_squad_trace"
                            if squad_resolution_trace_request
                            else (
                                "read_only_squad_resolution"
                                if squad_resolution_request
                                else (
                                    "execute_repair"
                                    if pwa_console_repair_request
                                    else (
                                        "propose_only_dispatch"
                                        if platform_improvement_review
                                        else ("read_only_dispatch" if team_technical_audit else None)
                                    )
                                )
                            )
                        )
                    )
                )
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
        "force_dispatch": bool(continuous_audit_request or platform_improvement_review or incremental_dispatch_followup),
        "pwa_console_repair_request": bool(pwa_console_repair_request),
        "squad_resolution_request": bool(squad_resolution_request),
        "squad_resolution_trace_request": bool(squad_resolution_trace_request),
        "continuous_audit_supported": bool(continuous_audit_request or continuous_audit_status_request),
        "requested_job_id": requested_job_id,
        "use_latest_continuous_audit_job": bool(continuous_audit_status_request and not requested_job_id),
        "session_admin_console_access": bool(session_admin_console_access),
        "session_is_admin_master": bool(session_is_admin_master),
        "session_write_approval_authority": bool(session_write_approval_authority),
        "required_authority_for_execution": ("master_admin" if requires_write_approval else "standard"),
    }

    payload = {
        "intent": intent,
        "confidence": (
            0.99
            if (
                final_readonly_analysis_request
                or pwa_console_repair_request
                or platform_improvement_review
                or continuous_audit_request
                or continuous_audit_status_request
            )
            else (0.99 if incremental_dispatch_followup else (0.98 if runtime_op.get("kind") else 0.62))
        ),
        "recommended_agents": recommended_agents,
        "advisor_agents": advisor_agents,
        "runtime_operation": runtime_op,
        "requires_runtime_execution": bool(runtime_op.get("kind")),
        "target_agent": target_agent,
        "delivery_contract": delivery_contract,
        "template_id": template_id,
        "structured_output": structured_output,
        "first_win_goal": (
            "deliver_final_analysis"
            if final_readonly_analysis_request
            else ("execute_orion_runtime" if runtime_op.get("kind") else "clarify_next_step")
        ),
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
        "continuous_audit_request": bool(continuous_audit_request),
        "continuous_audit_status_request": bool(continuous_audit_status_request),
        "final_readonly_analysis_request": bool(final_readonly_analysis_request),
        "best_effort_analysis_required": bool(final_readonly_analysis_request),
        "grounded_analysis_required": bool(final_readonly_analysis_request),
        "incremental_dispatch_followup": bool(incremental_dispatch_followup),
        "expected_specialist_reports": expected_specialist_reports,
        "has_completed_dispatch_context": bool(has_completed_dispatch_context),
        "hard_constraints": hard_constraints,
        "requested_job_id": requested_job_id,
        "session_admin_console_access": bool(session_admin_console_access),
        "session_is_admin_master": bool(session_is_admin_master),
        "session_write_approval_authority": bool(session_write_approval_authority),
        "required_authority_for_execution": ("master_admin" if requires_write_approval else "standard"),
    }
    payload.update(_runtime_self_audit_override(intent))
    return payload

# ============================================================
# EFATA777 — additive helpers for natural-language agent citation
# Added without replacing canonical build_intent_package implementation.
# These helpers are inert unless explicitly wired by the runtime layer.
# ============================================================

def _suggest_specialists_for_context(user_text: str) -> list[str]:
    text = (user_text or "").lower()
    suggested = []

    if any(term in text for term in ["ux", "interface", "console", "experiência", "frontend", "layout"]):
        suggested.append("ux_frontend")
    if any(term in text for term in ["api", "backend", "persist", "persistência", "banco", "integração"]):
        suggested.append("backend_engineer")
    if any(term in text for term in ["qa", "teste", "regress", "validação"]):
        suggested.append("qa_release_engineer")

    seen = set()
    out = []
    for item in suggested:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _agent_reasons_for_context(user_text: str, agents: list[str]) -> dict[str, str]:
    reasons = {}
    for agent in agents:
        if agent == "ux_frontend":
            reasons[agent] = "revisar a experiência do App Console"
        elif agent == "backend_engineer":
            reasons[agent] = "avaliar impactos em APIs, persistência e integrações"
        elif agent == "qa_release_engineer":
            reasons[agent] = "validar riscos de regressão e cobertura de testes"
    return reasons
