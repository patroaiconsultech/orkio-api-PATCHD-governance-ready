# app/main.py — EFATA777_ORION_NATURAL_LANGUAGE_AGENT_CITATION_HOTFIX

# Objetivo:
# - manter Orion como voz única
# - citar em linguagem natural apenas agentes realmente acionados
# - não citar agentes sugeridos / inferidos como se tivessem sido usados
# - preservar resposta estruturada quando o prompt exigir formato rígido

# Trecho de apoio sugerido em nível de módulo

def _normalize_consulted_agents(raw_agents):
    agents = []
    if isinstance(raw_agents, (list, tuple)):
        for item in raw_agents:
            if isinstance(item, str) and item.strip():
                agents.append(item.strip())
            elif isinstance(item, dict):
                agent_name = str(item.get("agent") or item.get("name") or "").strip()
                if agent_name:
                    agents.append(agent_name)
    seen = set()
    out = []
    for agent in agents:
        if agent not in seen:
            out.append(agent)
            seen.add(agent)
    return out


def _normalize_agent_reasons(raw):
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        agent = str(key or "").strip()
        if not agent:
            continue
        reason = str(value or "").strip()
        if reason:
            out[agent] = reason
    return out


def _has_verified_internal_dispatch(dispatch_receipt_id):
    value = str(dispatch_receipt_id or "").strip()
    return bool(value and value.upper() not in {"N/A", "NONE", "NULL"})


def _render_orion_consultation_sentence(*, consulted_agents, agent_reasons=None, internal_collaboration_used=False, dispatch_receipt_id=None):
    consulted_agents = _normalize_consulted_agents(consulted_agents)
    agent_reasons = _normalize_agent_reasons(agent_reasons)
    verified = bool(internal_collaboration_used) and _has_verified_internal_dispatch(dispatch_receipt_id)

    if not verified or not consulted_agents:
        return "Nesta resposta, não consultei agentes especializados de forma verificável. A análise foi consolidada apenas pelo Orion com base no contexto disponível."

    parts = []
    for agent in consulted_agents:
        reason = agent_reasons.get(agent)
        label = agent.replace("_", " ").strip()
        label = " ".join([p.capitalize() for p in label.split()])
        if reason:
            parts.append(f"o agente {label} para {reason}")
        else:
            parts.append(f"o agente {label}")

    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} e {parts[1]}"
    else:
        joined = ", ".join(parts[:-1]) + f", e {parts[-1]}"

    return f"Consultei {joined}. Com base nessas consultas, consolidei esta resposta em nome do Orion."


# No consolidator final do chat / payload:
# 1. preservar campos estruturados:
#    response_owner
#    internal_collaboration_used
#    consulted_agents
#    dispatch_receipt_id
#    evidence_level
# 2. adicionar language-natural summary APENAS se:
#    - a resposta não estiver em formato rígido imposto pelo usuário, OU
#    - houver campo específico consultation_summary
#
# Exemplo de acoplamento no payload final:
#
# consulted_agents = _normalize_consulted_agents(payload.get("consulted_agents"))
# dispatch_receipt_id = payload.get("dispatch_receipt_id")
# internal_collaboration_used = bool(payload.get("internal_collaboration_used"))
# agent_reasons = _normalize_agent_reasons(payload.get("agent_reasons"))
#
# payload["consultation_summary"] = _render_orion_consultation_sentence(
#     consulted_agents=consulted_agents,
#     agent_reasons=agent_reasons,
#     internal_collaboration_used=internal_collaboration_used,
#     dispatch_receipt_id=dispatch_receipt_id,
# )
#
# Regras:
# - se internal_collaboration_used == true mas dispatch_receipt_id ausente, converter evidence_level para "unverified" e NÃO afirmar consulta real.
# - se consulted_agents vier vazio, consultation_summary deve declarar ausência de consulta verificável.
# - Orion continua response_owner único.


# Quando houver prompt em linguagem natural e sem formato rígido, a resposta final pode incluir:
#
# "Consultei o agente UX Frontend para revisar a experiência do App Console,
#  o Backend Engineer para avaliar impactos nas APIs e persistência,
#  e o QA Release Engineer para validar riscos de regressão."
#
# Quando não houver recibo verificável:
#
# "Nesta resposta, não consultei agentes especializados de forma verificável.
#  A análise foi consolidada apenas pelo Orion com base no contexto disponível."
