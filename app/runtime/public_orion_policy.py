from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

from .orion_technical_squad import render_specialist_roster
from .platform_self_improvement import (
    render_platform_improvement_diagnosis,
    render_priority_plan,
    render_specialist_assignment,
)
from .runtime_feature_flags import (
    get_governed_self_improvement_mode,
    is_orion_technical_squad_enabled,
    is_platform_self_improvement_enabled,
    is_public_orion_policy_enabled,
)


ORION_POLICY_VERSION = "PUBLIC_ORION_POLICY_V3_FEATURE_FLAGS_TECH_SQUAD"


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
        or visible.startswith("orion")
        or target.startswith("orion")
        or route_requested.startswith("orion")
        or route_resolved.startswith("orion")
        or (mode == "single" and (target.startswith("orion") or visible.startswith("orion")))
    )


def _should_skip_to_existing_orion_capabilities(message: Any) -> bool:
    text = _norm(message)

    memory_markers = (
        "palavra-chave",
        "palavra chave",
        "meu nome",
        "minha empresa",
        "o que pedi para guardar",
        "guardar nesta conversa",
        "nesta conversa",
    )
    if any(k in text for k in memory_markers):
        return True

    github_markers = (
        "github",
        "repositorio",
        "repositório",
        "repo ",
        " repo",
        "branch",
        "commit",
        "pull request",
        " pr ",
        "status do repositorio",
        "status do repositório",
        "codigo no github",
        "código no github",
    )
    if any(k in text for k in github_markers):
        return True

    audit_markers = (
        "auditoria",
        "audite",
        "readonly",
        "read only",
        "logs",
        "log ",
        "terminal guard",
        "stacktrace",
        "trace_id",
        "deploy",
        "patch",
        "produção",
        "producao",
        "incidente",
        "war room",
    )
    if any(k in text for k in audit_markers):
        return True

    return False


def _classify_orion_intent(message: Any) -> str:
    text = _norm(message)

    if any(k in text for k in (
        "precisa melhorar tecnicamente",
        "melhorar tecnicamente",
        "o que a plataforma precisa melhorar",
        "diagnostico de melhorias",
        "diagnóstico de melhorias",
        "auto reconhecer",
        "auto reconhecer melhorias",
        "autoavaliacao",
        "autoavaliação",
        "pontos tecnicos mais frageis",
        "pontos técnicos mais frágeis",
        "fragilidades tecnicas",
        "fragilidades técnicas",
    )):
        return "platform_improvement_diagnosis"

    if any(k in text for k in (
        "plano de melhoria",
        "por prioridade",
        "prioridades tecnicas",
        "prioridades técnicas",
        "p0",
        "p1",
        "p2",
        "ordem segura",
        "roadmap tecnico",
        "roadmap técnico",
    )):
        return "platform_priority_plan"

    if any(k in text for k in (
        "especialistas tecnicos",
        "especialistas técnicos",
        "quais especialistas",
        "squad tecnico",
        "squad técnico",
        "quem deveria atuar",
        "equipe tecnica",
        "equipe técnica",
    )):
        return "technical_specialist_assignment"

    if any(k in text for k in ("explique tecnicamente", "o que e o orkio", "o que é o orkio", "orkio os", "arquitetura da plataforma")):
        return "technical_platform_explanation"

    if any(k in text for k in ("agentes", "multiagente", "multi agente", "orquestracao", "orquestração", "squad")):
        return "agent_orchestration_architecture"

    if any(k in text for k in ("backend", "frontend", "runtime", "sse", "stream", "api", "banco", "database", "auth", "voz")):
        return "technical_architecture"

    if any(k in text for k in ("seguranca", "segurança", "governanca", "governança", "lgpd", "permissao", "permissão")):
        return "governance_security"

    return "technical_general"


def _answer_platform_explanation() -> str:
    return """Orion — visão técnica do ORKIO OS

O ORKIO OS pode ser entendido como uma camada operacional de inteligência aplicada: ele recebe contexto, identifica intenção, preserva histórico, escolhe o agente adequado e transforma uma conversa em direção executiva, técnica ou operacional.

1. Camada de experiência
O usuário conversa com uma interface única, mas a plataforma pode organizar a resposta por agentes, contexto, histórico e objetivo.

2. Camada de orquestração
O sistema interpreta destino, @mention, intenção e tipo de tarefa para decidir se deve responder como conversa normal, leitura executiva, diagnóstico técnico ou capacidade controlada.

3. Camada de agentes
Orkio atua como host/CEO da experiência; Chris organiza estratégia, negócios e crescimento; Orion estrutura diagnóstico técnico, governança, arquitetura e auditoria readonly.

4. Camada de capacidades
Funcionalidades como GitHub readonly, auditorias, memória, arquivos, runtime e execução governada devem operar separadas da conversa comum, com rastreabilidade e sem escrita indevida.

5. Princípio técnico
A plataforma deve evoluir para um kernel de roteamento claro: quem responde, por que responde, com qual capacidade e qual evidência foi usada."""


def _answer_agent_orchestration() -> str:
    return """Orion — arquitetura de orquestração técnica

A orquestração ideal do ORKIO deve separar identidade, intenção e capacidade.

1. Identidade
Quem foi chamado: Orkio, Chris, Orion ou Team.

2. Intenção
O pedido é conversa normal, leitura executiva, auditoria readonly, GitHub readonly, plano técnico ou execução governada?

3. Capacidade
A resposta precisa apenas de raciocínio contextual ou precisa acionar uma capability específica?

4. Squad técnico do Orion
- Orion Backend: API, rotas, contratos e persistência.
- Orion Frontend: UI, stream, estado e renderização.
- Orion Runtime: roteamento, intent engine, guards e fallback.
- Orion DevOps/SRE: deploy, logs, saúde e observabilidade.
- Orion Security: permissões, tokens, LGPD e superfície de risco.
- Orion Data/DB: schema, migrations, memória e contexto.
- Orion QA: matriz de regressão, testes e critérios de pronto.

Nota de governança:
Nesta resposta, eu organizei a análise pelos eixos do squad técnico. Isso não significa que subagentes foram executados de forma real; a ativação operacional deve permanecer controlada e auditável."""


def _answer_technical_architecture() -> str:
    return """Orion — leitura técnica de arquitetura

A plataforma precisa evoluir com uma separação mais clara entre console, roteamento, políticas de agente, capacidades e stream.

1. Frontend
Deve exibir a verdade final enviada pelo backend, renderizar mensagens com segurança e não inferir agente de forma independente quando o backend já definiu o speaker.

2. Backend
Deve deixar de concentrar políticas no main.py. O padrão correto é mover comportamento de agente para módulos como public_orkio_policy.py, public_chris_policy.py e public_orion_policy.py.

3. Runtime
O runtime deve decidir apenas quando precisa executar capacidade real. Conversa normal não deve cair em GitHub, auditoria, terminal guard ou ação governada.

4. Stream/SSE
O stream precisa encerrar com evento final claro, sem objeto bruto no frontend e sem mascarar erro real como fallback genérico.

5. Próximo passo técnico
Consolidar os módulos de política dos agentes e, depois, extrair routing_contract.py, capability_policy.py e stream_outcome.py para reduzir risco operacional."""


def _answer_governance_security() -> str:
    return """Orion — governança e segurança

A governança técnica do ORKIO deve proteger três coisas: identidade do agente, capacidade executada e confiança do usuário.

1. Identidade
O agente exibido na UI precisa ser o mesmo decidido pelo backend.

2. Capacidade
GitHub, auditoria, patches, deploys e qualquer ação sensível devem ser separados de conversa comum.

3. Escrita
Nenhuma escrita, branch, commit, PR, migration ou deploy deve ocorrer sem aprovação explícita e trilha governada.

4. Observabilidade
Logs normais devem ser informativos; erros reais devem ser separados de checkpoints operacionais.

5. Segurança de produto
Usuário público não deve ver token, stacktrace, terminal guard, objeto bruto, logs internos ou detalhes sensíveis."""


def _answer_general() -> str:
    return """Orion — diagnóstico técnico inicial

Minha leitura técnica é que o ORKIO deve evoluir como uma plataforma modular de agentes, com separação clara entre experiência pública, políticas de agente, roteamento, capacidades e execução governada.

O princípio central é simples:
- conversa comum deve continuar conversa;
- leitura executiva deve ir para Chris;
- experiência pública e acolhimento devem ficar com Orkio;
- auditoria técnica, arquitetura, GitHub readonly e governança devem ficar sob Orion;
- execução real deve permanecer controlada, auditável e reversível.

O próximo ganho operacional vem de reduzir o main.py e consolidar módulos externos por agente e por capacidade."""


def build_public_orion_policy_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_public_orion_policy_enabled():
        return {"handled": False, "reason": "public_orion_policy_disabled"}

    if not _target_is_orion(
        message=message,
        visible_agent=visible_agent,
        target_agent_slug=target_agent_slug,
        dest_mode=dest_mode,
        route_plan=route_plan,
    ):
        return {"handled": False, "reason": "not_orion_target"}

    if _should_skip_to_existing_orion_capabilities(message):
        return {"handled": False, "reason": "skip_existing_orion_capability"}

    intent = _classify_orion_intent(message)

    if intent in {"platform_improvement_diagnosis", "platform_priority_plan"} and not is_platform_self_improvement_enabled():
        intent = "technical_general"

    if intent == "technical_specialist_assignment" and not is_orion_technical_squad_enabled():
        intent = "technical_general"

    answers = {
        "platform_improvement_diagnosis": render_platform_improvement_diagnosis,
        "platform_priority_plan": render_priority_plan,
        "technical_specialist_assignment": render_specialist_assignment,
        "technical_platform_explanation": _answer_platform_explanation,
        "agent_orchestration_architecture": _answer_agent_orchestration,
        "technical_architecture": _answer_technical_architecture,
        "governance_security": _answer_governance_security,
        "technical_general": _answer_general,
    }

    answer = answers.get(intent, _answer_general)()

    return {
        "handled": True,
        "agent_name": "Orion",
        "agent_id": None,
        "answer": answer,
        "reason": f"public_orion_{intent}",
        "policy_version": ORION_POLICY_VERSION,
        "intent": intent,
        "write_executed": False,
    }


def build_public_orion_stream_payload(
    decision: Dict[str, Any],
    *,
    persisted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    persisted = persisted if isinstance(persisted, dict) else {}
    final_text = str(decision.get("answer") or "").strip()

    return {
        **persisted,
        "ok": True,
        "answer": final_text,
        "message": final_text,
        "final_text": final_text,
        "content": final_text,
        "text": final_text,
        "agent_id": decision.get("agent_id"),
        "agent_name": decision.get("agent_name") or "Orion",
        "final_speaker": "Orion",
        "visible_agent": "Orion",
        "service": "public_orion_policy",
        "provider": "platform",
        "status": "done",
        "runtime_hints": {
            "routing": {
                "routing_source": "public_orion_policy_module",
                "route_applied": True,
                "execution_lifecycle": "completed",
                "route_family": "public_technical_architecture",
                "route_reason": decision.get("reason") or "",
                "policy_version": decision.get("policy_version") or ORION_POLICY_VERSION,
                "governed_self_improvement_mode": get_governed_self_improvement_mode(),
                "platform_self_improvement_enabled": is_platform_self_improvement_enabled(),
                "orion_technical_squad_enabled": is_orion_technical_squad_enabled(),
                "write_executed": False,
                "proposal_created": False,
                "branch_created": False,
                "pr_created": False,
            }
        },
    }
