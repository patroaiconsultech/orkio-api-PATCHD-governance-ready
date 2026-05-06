# EFATA 777 V7 COMPLETE
# Consolidated package for governed capability answers + analytical readonly + registry alignment + realtime self-heal hardening.

from __future__ import annotations

from typing import Any, Dict, List, Optional


CAPABILITY_EXECUTION_BINDINGS = {
    # Governed / informational runtime
    "governance_capability_answer": {
        "executor": "orion_internal.governance_capability_answer",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion"],
        "write": False,
        "purpose": "responder pergunta de governança/capacidade sem executar ações",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["platform", "backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "safe_evolution_control": {
        "executor": "orion_internal.governance_capability_answer",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion"],
        "write": False,
        "purpose": "explicar limites e regras de evolução governada",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["platform", "backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "db_schema_read": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
        "purpose": "inspecionar schema e derivações de banco em modo leitura",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["backend", "platform"],
        "governed": True,
    },
    "governed_patch_execution": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
        "purpose": "executar patch governado após autorização explícita",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "db_schema_fix_governed": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
        "purpose": "corrigir schema em fluxo governado",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "platform"],
        "governed": True,
    },

    # GitHub runtime
    "github_repo_read": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "github_repo_write": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },
    "github_branch_create": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },
    "github_file_create": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },
    "github_repo_fix": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },
    "github_pr_compare_status": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "github_pr_prepare": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },

    # Squad visibility / audit runtime
    "squad_agents_list": {
        "executor": "orion_internal.list_squad_agents",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion"],
        "write": False,
    },
    "platform_self_audit": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "platform_improvement_review": {
        "executor": "orion_internal.platform_improvement_review",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "repo_structure_scan": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "routes_scan": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "runtime_scan": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "security_scan": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor"],
        "write": False,
    },
    "safe_patch_plan": {
        "executor": "orion_internal.platform_self_audit",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor", "cto"],
        "write": False,
    },
    "controlled_self_evolution_propose_only": {
        "executor": "orion_internal.platform_self_evolution_plan",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor", "cto", "chris"],
        "write": False,
    },
    "premium_audit_backlog_generate": {
        "executor": "orion_internal.platform_self_evolution_plan",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor", "cto", "chris"],
        "write": False,
    },
    "premium_audit_patch_candidate_select": {
        "executor": "orion_internal.platform_self_evolution_plan",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion", "auditor", "cto", "chris"],
        "write": False,
    },
    "controlled_self_evolution_execute_proposal": {
        "executor": "orion_internal.github_execute",
        "mode": "runtime",
        "allowed_agents": ["orion"],
        "write": True,
    },

    "squad_resolve_readonly": {
        "executor": "orion_internal.resolve_squad_readonly",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion"],
        "write": False,
    },
    "squad_resolution_trace_readonly": {
        "executor": "orion_internal.squad_resolution_trace_readonly",
        "mode": "runtime",
        "allowed_agents": ["orkio", "orion"],
        "write": False,
    },
}


CAPABILITY_REGISTRY = {
    "orkio": {
        "role": "orchestrator",
        "capabilities": [
            "coordinate",
            "synthesize",
            "guide_next_step",
            "github_repo_read",
            "github_pr_compare_status",
            "squad_agents_list",
            "platform_self_audit",
            "platform_improvement_review",
            "repo_structure_scan",
            "routes_scan",
            "runtime_scan",
            "security_scan",
            "safe_patch_plan",
            "controlled_self_evolution_propose_only",
            "premium_audit_backlog_generate",
            "premium_audit_patch_candidate_select",
            "controlled_self_evolution_execute_proposal",
            "governance_capability_answer",
            "safe_evolution_control",
            "db_schema_read",
            "squad_resolve_readonly",
            "squad_resolution_trace_readonly",
        ],
        "triggers": [
            "default",
            "general",
            "unclear",
            "squad",
            "agentes",
            "auditar",
            "scan",
            "varredura",
            "melhorias",
            "review de melhorias",
            "improvement review",
            "quick wins",
            "plataforma",
            "governança",
            "governanca",
            "aprovação",
            "aprovacao",
            "capacidade de aplicar melhorias",
            "sob minha aprovação",
            "root causes",
            "risks",
            "next actions",
            "follow-up",
            "followup",
            "incremental",
            "dispatch followup",
            "resolva exatamente este squad",
            "resolver squad",
            "squad resolvido",
            "resolve exactly this squad",
            "requested_specialists_raw",
            "selected_specialists_before_policy",
            "selected_specialists_after_policy",
            "abort_reason",
        ],
        "dependencies": [],
        "priority": 100,
        "writes_memory": False,
    },

    "orion": {
        "role": "cto",
        "capabilities": [
            "technical_analysis",
            "github_repo_read",
            "github_pr_compare_status",
            "github_repo_fix",
            "github_branch_create",
            "github_file_create",
            "github_repo_write",
            "github_pr_prepare",
            "governed_patch_execution",
            "governance_capability_answer",
            "safe_evolution_control",
            "db_schema_read",
            "db_schema_fix_governed",
            "squad_agents_list",
            "platform_self_audit",
            "platform_improvement_review",
            "repo_structure_scan",
            "routes_scan",
            "runtime_scan",
            "security_scan",
            "safe_patch_plan",
            "controlled_self_evolution_propose_only",
            "premium_audit_backlog_generate",
            "premium_audit_patch_candidate_select",
            "squad_resolve_readonly",
            "squad_resolution_trace_readonly",
        ],
        "triggers": [
            "github",
            "repo",
            "code",
            "patch",
            "fix",
            "technical",
            "database",
            "banco",
            "schema",
            "drift",
            "migration",
            "migracao",
            "tabela",
            "coluna",
            "audit",
            "auditar",
            "scan",
            "platform",
            "plataforma",
            "melhorias",
            "review de melhorias",
            "improvement review",
            "quick wins",
            "squad",
            "frontend",
            "empty state premium",
            "governança",
            "governanca",
            "aprovação",
            "aprovacao",
            "capacidade operacional",
            "sob minha aprovação",
            "root causes",
            "risks",
            "next actions",
            "follow-up",
            "followup",
            "incremental",
            "dispatch followup",
            "resolva exatamente este squad",
            "resolver squad",
            "squad resolvido",
            "resolve exactly this squad",
            "requested_specialists_raw",
            "requested_specialists_normalized",
            "selected_specialists_before_policy",
            "selected_specialists_after_policy",
            "abort_reason",
        ],
        "dependencies": ["orkio"],
        "priority": 98,
        "writes_memory": False,
    },

    "auditor": {
        "role": "technical_auditor",
        "capabilities": [
            "platform_self_audit",
            "platform_improvement_review",
            "repo_structure_scan",
            "routes_scan",
            "runtime_scan",
            "security_scan",
            "safe_patch_plan",
            "controlled_self_evolution_propose_only",
            "premium_audit_backlog_generate",
            "premium_audit_patch_candidate_select",
            "github_repo_read",
            "github_pr_compare_status",
            "technical_analysis",
            "risk_guard",
            "governance_capability_answer",
            "db_schema_read",
        ],
        "triggers": [
            "auditor",
            "audit",
            "auditar",
            "varredura",
            "risco",
            "segurança",
            "security",
            "arquitetura",
            "diagnóstico",
            "classificação operacional",
            "classificacao operacional",
            "read only",
            "somente leitura",
            "governança",
            "governanca",
            "aprovação",
            "aprovacao",
            "intent_engine.py",
            "capability_registry.py",
            "review de melhorias",
            "improvement review",
            "quick wins",
            "root causes",
            "risks",
            "next actions",
            "follow-up",
            "followup",
            "incremental",
            "dispatch followup",
        ],
        "dependencies": ["orkio", "orion"],
        "priority": 97,
        "writes_memory": False,
    },

    "cto": {
        "role": "systems_architect",
        "capabilities": [
            "technical_analysis",
            "platform_improvement_review",
            "safe_patch_plan",
            "repo_structure_scan",
            "routes_scan",
            "runtime_scan",
            "db_schema_read",
            "controlled_self_evolution_propose_only",
            "premium_audit_backlog_generate",
            "premium_audit_patch_candidate_select",
        ],
        "triggers": [
            "cto",
            "arquitetura",
            "architecture",
            "patch plan",
            "plano técnico",
            "refino técnico",
            "root causes",
            "risks",
            "next actions",
            "follow-up",
            "followup",
            "incremental",
            "dispatch followup",
        ],
        "dependencies": ["orkio", "orion"],
        "priority": 96,
        "writes_memory": False,
    },

    "miguel": {
        "role": "guardian",
        "capabilities": ["risk_guard", "safety_boundary", "sensitive_review"],
        "triggers": ["sensitive", "compliance", "high_risk"],
        "dependencies": ["orkio"],
        "priority": 95,
        "writes_memory": False,
    },

    "uriel": {
        "role": "diagnostician",
        "capabilities": ["root_cause", "priority_diagnosis", "clarify_decision"],
        "triggers": ["overload", "priority", "decision", "blocker"],
        "dependencies": ["orkio"],
        "priority": 90,
        "writes_memory": False,
    },

    "rafael": {
        "role": "organizer",
        "capabilities": ["reframe", "small_steps", "practical_plan"],
        "triggers": ["execution", "plan", "next_step"],
        "dependencies": ["uriel"],
        "priority": 85,
        "writes_memory": False,
    },

    "gabriel": {
        "role": "translator",
        "capabilities": ["simplify", "translate_for_user", "clarify_message"],
        "triggers": ["communication", "explain", "summarize"],
        "dependencies": ["orkio"],
        "priority": 80,
        "writes_memory": False,
    },

    "chris": {
        "role": "commercial_strategist",
        "capabilities": [
            "controlled_self_evolution_propose_only",
            "premium_audit_backlog_generate",
            "premium_audit_patch_candidate_select",
            "github_repo_read",
            "github_pr_compare_status",
            "platform_self_audit",
            "platform_improvement_review",
            "repo_structure_scan",
            "routes_scan",
            "runtime_scan",
            "clarify_message",
            "summarize",
        ],
        "triggers": [
            "chris",
            "comercial",
            "negócio",
            "read repo",
            "ler repo",
            "resumir",
            "explicar",
        ],
        "dependencies": ["orkio"],
        "priority": 79,
        "writes_memory": False,
    },

    "metatron": {
        "role": "scribe",
        "capabilities": ["candidate_memory", "session_register", "continuity_signal"],
        "triggers": ["memory", "followup", "continuity"],
        "dependencies": ["orkio"],
        "priority": 75,
        "writes_memory": True,
    },

    "saint_germain": {
        "role": "refiner",
        "capabilities": ["incremental_refinement", "maturity", "process_improvement"],
        "triggers": ["refine", "improve", "transform"],
        "dependencies": ["orkio"],
        "priority": 70,
        "writes_memory": False,
    },
}


def get_capability_registry() -> Dict[str, Any]:
    return CAPABILITY_REGISTRY.copy()


def get_capability_executor(capability: str) -> Optional[Dict[str, Any]]:
    return CAPABILITY_EXECUTION_BINDINGS.get(capability)


def get_capability_allowed_agents(capability: str) -> List[str]:
    binding = CAPABILITY_EXECUTION_BINDINGS.get(capability) or {}
    agents = binding.get("allowed_agents") or []
    return [str(a).strip().lower() for a in agents if str(a).strip()]


def capability_is_write(capability: str) -> bool:
    binding = CAPABILITY_EXECUTION_BINDINGS.get(capability) or {}
    return bool(binding.get("write", False))


def agent_can_execute_capability(agent_name: str, capability: str) -> bool:
    normalized_agent = (agent_name or "").strip().lower()
    if not normalized_agent or not capability:
        return False

    meta = CAPABILITY_REGISTRY.get(normalized_agent) or {}
    declared_caps = {str(c).strip() for c in (meta.get("capabilities") or []) if str(c).strip()}
    if capability not in declared_caps:
        return False

    binding = CAPABILITY_EXECUTION_BINDINGS.get(capability)
    if not binding:
        return True

    allowed = get_capability_allowed_agents(capability)
    if not allowed:
        return True

    return normalized_agent in allowed


# === PATCH D / ORKIO GOVERNED CAPABILITIES ===
GOVERNED_CAPABILITY_PROFILES = {
    "platform_self_audit": {
        "purpose": "auditar plataforma em modo leitura",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["platform", "backend", "frontend"],
        "governed": True,
    },
    "platform_improvement_review": {
        "purpose": "propor melhorias priorizadas da plataforma em modo leitura",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["platform", "backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "github_repo_read": {
        "purpose": "ler repositório e comparar PRs",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "github_pr_compare_status": {
        "purpose": "comparar status de branch/PR",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "github_repo_write": {
        "purpose": "aplicar patch em branch governada",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "governed": True,
    },
    "github_pr_prepare": {
        "purpose": "abrir PR governada",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "governed": True,
    },
}


def get_all_declared_capabilities() -> List[str]:
    declared: set[str] = set()
    for meta in CAPABILITY_REGISTRY.values():
        for capability in (meta.get("capabilities") or []):
            value = str(capability or "").strip()
            if value:
                declared.add(value)
    return sorted(declared)


def get_capability_registry_issues() -> Dict[str, Any]:
    declared = set(get_all_declared_capabilities())
    bound = set(CAPABILITY_EXECUTION_BINDINGS.keys())
    governed = set(GOVERNED_CAPABILITY_PROFILES.keys())
    return {
        "declared_without_binding": sorted(declared - bound),
        "binding_without_declared": sorted(bound - declared),
        "governed_without_binding": sorted(governed - bound),
        "write_capabilities": sorted(
            capability
            for capability, binding in CAPABILITY_EXECUTION_BINDINGS.items()
            if bool(binding.get("write"))
        ),
    }



def get_governed_capability_profile(capability: str) -> Dict[str, Any]:
    return dict(GOVERNED_CAPABILITY_PROFILES.get(str(capability or "").strip(), {}))


def get_governed_capability_registry() -> Dict[str, Dict[str, Any]]:
    return {key: dict(value) for key, value in GOVERNED_CAPABILITY_PROFILES.items()}
