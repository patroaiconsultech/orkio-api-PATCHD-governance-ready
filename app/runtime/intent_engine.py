# app/runtime/intent_engine.py — EFATA777_ORION_NATURAL_LANGUAGE_AGENT_CITATION_HOTFIX

# Objetivo:
# - distinguir agentes planejados vs agentes realmente consultados
# - preencher agent_reasons por domínio
# - não marcar internal_collaboration_used=true sem recibo real

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
    text = (user_text or "").lower()
    reasons = {}
    for agent in agents:
        if agent == "ux_frontend":
            reasons[agent] = "revisar a experiência do App Console"
        elif agent == "backend_engineer":
            reasons[agent] = "avaliar impactos em APIs, persistência e integrações"
        elif agent == "qa_release_engineer":
            reasons[agent] = "validar riscos de regressão e cobertura de testes"
    return reasons


# No momento de montar o runtime_context:
#
# suggested_agents = _suggest_specialists_for_context(user_text)
# runtime_context["planned_agents"] = suggested_agents
# runtime_context["planned_agent_reasons"] = _agent_reasons_for_context(user_text, suggested_agents)
#
# Após dispatch real:
#
# if dispatch_receipt_id and isinstance(actual_consulted_agents, list) and actual_consulted_agents:
#     runtime_context["internal_collaboration_used"] = True
#     runtime_context["consulted_agents"] = actual_consulted_agents
#     runtime_context["agent_reasons"] = {
#         agent: runtime_context["planned_agent_reasons"].get(agent, "")
#         for agent in actual_consulted_agents
#     }
#     runtime_context["evidence_level"] = "verified_internal_dispatch"
# else:
#     runtime_context["internal_collaboration_used"] = False
#     runtime_context["consulted_agents"] = []
#     runtime_context["agent_reasons"] = {}
#     runtime_context["dispatch_receipt_id"] = "N/A"
#     runtime_context["evidence_level"] = "none"
#
# Regra crítica:
# - planned_agents nunca deve ser exibido ao usuário como se fosse consulted_agents
# - only actual_consulted_agents can populate consulted_agents
