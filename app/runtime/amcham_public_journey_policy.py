# AO66A — AMCHAM_PUBLIC_JOURNEY_POLICY
# Destino real: app/runtime/amcham_public_journey_policy.py
# Modo: PATCH_PREMIUM / backend-runtime / public journey first

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, Optional

from .runtime_feature_flags import is_amcham_public_journey_enabled

AMCHAM_PUBLIC_JOURNEY_POLICY_VERSION = "AO66A_AMCHAM_PUBLIC_JOURNEY_POLICY_PREMIUM_V1"

FUTURE_UNLOCK_NOTICE = (
    "Com a evolução das conversas, o uso correto da ferramenta e a identificação de necessidades específicas, "
    "novas funcionalidades e agentes especializados poderão ser liberados futuramente para apoiar análises mais profundas."
)

AMCHAM_PUBLIC_JOURNEY_OVERLAY = f"""
AMCHAM_PUBLIC_JOURNEY_POLICY — contrato público de jornada

Você é Orkio, copiloto profissional da jornada AMCHAM/Efatà 777.

Função pública:
- Acolher usuários da comunidade AMCHAM e convidados Efatà 777.
- Entender objetivos, skills, desafios, ideias, projetos e próximos passos.
- Conduzir pelo chat com clareza, segurança e propósito.
- Fazer descoberta de intenção antes de recomendar qualquer capacidade avançada.

Regras principais:
- Não assuma que todo usuário quer criar um negócio.
- Não assuma que todo usuário quer agentes.
- Não ofereça especialistas imediatamente.
- Não cite agentes internos por nome.
- Não exponha bastidores, runtime, GitHub, patches, logs, branch, PR, deploy ou auditoria técnica.
- Não conduza direto para WhatsApp, implantação ou venda consultiva sem contexto suficiente.
- Mantenha Orkio como único agente visível na experiência pública.
- Quando houver ambiguidade, faça 2 ou 3 perguntas curtas.

Trilhas públicas:
1. Desenvolvimento profissional.
2. Mapeamento de skills.
3. Networking e comunidade AMCHAM.
4. Liderança e comunicação.
5. Inovação dentro da empresa.
6. Projetos de IA no trabalho.
7. Empreendedorismo e novos negócios.
8. Diagnóstico de empresa ou projeto.
9. Exploração livre da plataforma.

Mensagem de evolução:
{FUTURE_UNLOCK_NOTICE}
""".strip()


def _strip_accents(value: Any) -> str:
    raw = str(value or "")
    try:
        normalized = unicodedata.normalize("NFD", raw)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    except Exception:
        return raw


def normalize_text(value: Any) -> str:
    raw = _strip_accents(value).lower()
    raw = re.sub(r"[^a-z0-9@:/\.\-_\s]+", " ", raw, flags=re.I)
    return re.sub(r"\s+", " ", raw).strip()


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _explicit_orkio_or_public_context(
    normalized: str,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> bool:
    visible = normalize_text(visible_agent)
    target = normalize_text(target_agent_slug)
    route = route_plan if isinstance(route_plan, dict) else {}
    requested = normalize_text(route.get("requested_agent") or route.get("requested") or "")
    resolved = normalize_text(route.get("resolved_agent") or route.get("final_speaker") or "")

    if _contains_any(normalized, ["amcham", "efata", "efatah", "efata777", "efatah777", "patroai", "orkio"]):
        return True

    return any(
        item in {"orkio", "@orkio", "team", "@team"}
        for item in (visible, target, requested, resolved)
    )


def _is_direct_answer_constraint(normalized: str) -> bool:
    return _contains_any(
        normalized,
        ("responda apenas", "responda somente", "responda so", "responda só", "apenas ok", "somente ok"),
    )


def _is_internal_agent_or_specialist_request(normalized: str) -> bool:
    agent_terms = (
        "chris", "@chris", "cris", "@cris", "orion", "@orion", "warren",
        "cfo", "cto", "especialista financeiro", "especialista de tecnologia",
        "especialistas", "agente interno", "agentes internos", "equipe interna",
    )
    action_terms = (
        "chama", "chamar", "aciona", "acionar", "envolve", "envolver",
        "consultar", "falar com", "conversar com", "quais agentes", "que agentes",
        "existem na plataforma", "disponiveis", "disponíveis",
    )
    return _contains_any(normalized, agent_terms) and _contains_any(normalized, action_terms)


def _is_technical_governance_request(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "autoevolucao", "autoevolução", "auto evolucao", "auto evolução",
            "readonly", "write_executed", "branch_created", "pr_created",
            "deploy_executed", "approval_required", "patch", "git", "github",
            "runtime", "logs", "deploy", "branch", "pull request",
            "terminal guard", "auditoria tecnica", "auditoria técnica",
            "orquestracao tecnica", "orquestração técnica",
        ),
    )


def classify_amcham_public_journey(normalized: str) -> Optional[str]:
    if not normalized:
        return None

    if _is_internal_agent_or_specialist_request(normalized):
        return "internal_agent_or_specialist_request"
    if _is_technical_governance_request(normalized):
        return "technical_governance_public_block"

    if _contains_any(normalized, ("o que e a patroai", "o que é a patroai", "como a amcham pode testar", "amcham pode testar", "testar o orkio", "o que e o orkio", "o que é o orkio")):
        return "institutional_amcham"
    if _contains_any(normalized, ("nao sei o que testar", "não sei o que testar", "me conduza", "por onde comecar", "por onde começar", "o que posso fazer", "como usar")):
        return "platform_exploration"
    if _contains_any(normalized, ("desenvolver dentro da amcham", "me desenvolver", "desenvolvimento profissional", "evoluir profissionalmente", "carreira", "crescer profissionalmente")):
        return "professional_development"
    if _contains_any(normalized, ("mapear meus skills", "mapear skills", "minhas skills", "competencias", "competências", "habilidades", "pontos fortes", "lacunas")):
        return "skills_mapping"
    if _contains_any(normalized, ("networking", "rede de contatos", "conectar", "conexoes", "conexões", "comunidade")) and _contains_any(normalized, ("melhorar", "desenvolver", "networking", "conectar", "posicionamento")):
        return "networking"
    if _contains_any(normalized, ("lideranca", "liderança", "comunicacao", "comunicação", "influencia", "influência", "gestao de pessoas", "gestão de pessoas")):
        return "leadership"
    if _contains_any(normalized, ("inovacao dentro da empresa", "inovação dentro da empresa", "projeto de ia", "ia dentro da minha empresa", "inteligencia artificial na empresa", "inteligência artificial na empresa", "automacao na empresa", "automação na empresa")):
        return "internal_innovation"
    if _contains_any(normalized, ("criar um novo negocio", "criar um novo negócio", "novo negocio", "novo negócio", "empreender", "empreendedorismo", "abrir uma empresa", "criar empresa", "startup")):
        return "entrepreneurship"
    if _contains_any(normalized, ("diagnostico", "diagnóstico", "avaliar uma ideia", "avaliar projeto", "avaliar empresa", "riscos", "proximos passos", "próximos passos", "plano")):
        return "business_or_project_diagnostic"
    if _contains_any(normalized, ("amcham", "efata", "efatah", "efata777", "efatah777")):
        return "platform_exploration"

    return None


def _base_runtime_hints(reason: str, public_intent: str) -> Dict[str, Any]:
    return {
        "routing": {
            "routing_source": "amcham_public_journey_policy_module",
            "route_applied": True,
            "execution_lifecycle": "completed",
            "final_speaker": "Orkio",
            "visible_agent": "Orkio",
            "policy_module": "app.runtime.amcham_public_journey_policy",
            "policy_reason": reason,
            "policy_version": AMCHAM_PUBLIC_JOURNEY_POLICY_VERSION,
            "public_intent": public_intent,
            "route_family": "amcham_public_journey",
            "write_executed": False,
            "proposal_created": False,
            "dispatch_executed": False,
            "branch_created": False,
            "pr_created": False,
            "deploy_executed": False,
            "blocked_routes": [
                "public_chris_policy",
                "public_product_ceo_scope_before_intent_discovery",
                "internal_agent_access_public_surface",
                "technical_governance_public_surface",
            ],
        }
    }


def _answer_institutional_amcham() -> str:
    return (
        "A PATROAI Consultech é a empresa responsável pela tecnologia Orkio, uma plataforma de IA criada para "
        "organizar ideias, diagnósticos, planos, skills, projetos e próximos passos com segurança.\n\n"
        "Para a AMCHAM, o teste pode ser feito pelo chat por texto: você pode pedir ao Orkio para mapear skills, "
        "organizar uma meta profissional, estruturar networking, avaliar uma ideia, revisar um desafio de liderança, "
        "planejar um projeto de IA na empresa ou transformar uma oportunidade em próximos passos.\n\n"
        f"Neste beta público, o Orkio conduz a experiência principal. {FUTURE_UNLOCK_NOTICE}"
    )


def _answer_platform_exploration() -> str:
    return (
        "Claro. Posso te conduzir por uma trilha simples de teste.\n\n"
        "Escolha uma opção:\n"
        "1. Mapear meus skills e pontos de evolução.\n"
        "2. Organizar uma meta profissional dentro da AMCHAM.\n"
        "3. Melhorar networking e posicionamento.\n"
        "4. Estruturar um projeto de IA na minha empresa.\n"
        "5. Avaliar uma ideia ou novo negócio.\n"
        "6. Diagnosticar um problema atual e próximos passos.\n\n"
        "Se preferir, responda apenas com o número da trilha ou descreva seu objetivo em uma frase."
    )


def _answer_professional_development() -> str:
    return (
        "Ótimo. Para desenvolvimento profissional dentro da AMCHAM, eu começaria entendendo sua trilha atual.\n\n"
        "Me responda, em poucas palavras:\n"
        "1. Qual é seu papel hoje ou área de atuação?\n"
        "2. Qual skill você mais quer desenvolver nos próximos meses?\n"
        "3. Você quer evoluir carreira, liderança, networking, inovação ou geração de negócios?\n\n"
        "Com isso, eu organizo um plano simples de evolução com diagnóstico, foco e próximos passos."
    )


def _answer_skills_mapping() -> str:
    return (
        "Perfeito. Vamos mapear seus skills de forma prática.\n\n"
        "Me envie três informações:\n"
        "1. Sua área ou função atual.\n"
        "2. Três habilidades que você já considera fortes.\n"
        "3. Uma habilidade que você quer desenvolver.\n\n"
        "Depois eu organizo um mapa com forças, lacunas, oportunidades AMCHAM e próximos passos de evolução."
    )


def _answer_networking() -> str:
    return (
        "Networking dentro da AMCHAM pode ser tratado como estratégia, não apenas como contato.\n\n"
        "Para conduzir bem, preciso entender:\n"
        "1. Que tipo de pessoa ou empresa você quer se aproximar?\n"
        "2. Qual valor você pode oferecer nessa conexão?\n"
        "3. Seu objetivo é carreira, parcerias, vendas, aprendizado ou inovação?\n\n"
        "Com isso, eu posso montar uma abordagem de posicionamento e próximos passos."
    )


def _answer_leadership() -> str:
    return (
        "Podemos trabalhar sua evolução em liderança e comunicação com foco prático.\n\n"
        "Para começar:\n"
        "1. Você lidera pessoas hoje ou quer se preparar para liderar?\n"
        "2. Seu maior desafio é comunicação, influência, gestão de conflitos, tomada de decisão ou execução?\n"
        "3. Em que contexto isso aparece: empresa, comunidade, vendas, projetos ou carreira?\n\n"
        "A partir disso, eu organizo um plano objetivo de desenvolvimento."
    )


def _answer_internal_innovation() -> str:
    return (
        "Excelente. Para um projeto de IA dentro da empresa, o primeiro passo é entender a dor antes da tecnologia.\n\n"
        "Me diga:\n"
        "1. Qual área ou processo você quer melhorar?\n"
        "2. O problema principal é tempo, custo, qualidade, atendimento, vendas, dados ou retrabalho?\n"
        "3. Que resultado prático você espera em 30 a 90 dias?\n\n"
        "Depois eu estruturo um diagnóstico, riscos e próximos passos para um piloto seguro."
    )


def _answer_entrepreneurship() -> str:
    return (
        "Ótimo. Criar um novo negócio pode ser uma trilha empreendedora, mas antes de falar em agentes ou implantação, "
        "vamos entender a ideia.\n\n"
        "Me responda:\n"
        "1. Qual problema esse negócio resolve?\n"
        "2. Quem seria o público-alvo inicial?\n"
        "3. Você já tem uma oferta, produto ou apenas uma intenção?\n\n"
        "Com essas respostas, eu organizo diagnóstico, riscos, proposta de valor e próximos passos."
    )


def _answer_business_or_project_diagnostic() -> str:
    return (
        "Vamos organizar isso com clareza.\n\n"
        "Para montar um diagnóstico útil, preciso de três pontos:\n"
        "1. Qual é a ideia, projeto ou problema?\n"
        "2. Qual resultado você quer alcançar?\n"
        "3. Qual é o maior risco ou dúvida hoje?\n\n"
        "Depois eu devolvo em diagnóstico, riscos e próximos passos."
    )


def _answer_internal_agent_or_specialist_request() -> str:
    return (
        "Neste beta público, o Orkio conduz a experiência principal pelo chat por texto. "
        "Eu não aciono agentes internos ou especialistas por nome nesta etapa.\n\n"
        "Posso organizar sua necessidade diretamente por aqui em diagnóstico, contexto, riscos e próximos passos. "
        f"{FUTURE_UNLOCK_NOTICE}"
    )


def _answer_technical_governance_public_block() -> str:
    return (
        "Neste beta público, o Orkio conduz a experiência principal pelo chat por texto, sem expor fluxos técnicos internos.\n\n"
        "Posso transformar sua solicitação em uma análise simples de objetivo, riscos, impacto e próximos passos. "
        f"{FUTURE_UNLOCK_NOTICE}"
    )


def _answer_for_intent(public_intent: str) -> str:
    answers = {
        "institutional_amcham": _answer_institutional_amcham,
        "platform_exploration": _answer_platform_exploration,
        "professional_development": _answer_professional_development,
        "skills_mapping": _answer_skills_mapping,
        "networking": _answer_networking,
        "leadership": _answer_leadership,
        "internal_innovation": _answer_internal_innovation,
        "entrepreneurship": _answer_entrepreneurship,
        "business_or_project_diagnostic": _answer_business_or_project_diagnostic,
        "internal_agent_or_specialist_request": _answer_internal_agent_or_specialist_request,
        "technical_governance_public_block": _answer_technical_governance_public_block,
    }
    return answers.get(public_intent, _answer_platform_exploration)()


def build_amcham_public_journey_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_amcham_public_journey_enabled():
        return {"handled": False, "reason": "amcham_public_journey_disabled"}

    normalized = normalize_text(message)
    if not normalized:
        return {"handled": False, "reason": "empty"}

    if _is_direct_answer_constraint(normalized):
        return {"handled": False, "reason": "direct_answer_constraint"}

    public_intent = classify_amcham_public_journey(normalized)
    if not public_intent:
        return {"handled": False, "reason": "no_amcham_public_journey_intent"}

    if public_intent not in {
        "internal_agent_or_specialist_request",
        "technical_governance_public_block",
    } and not _explicit_orkio_or_public_context(
        normalized,
        visible_agent=visible_agent,
        target_agent_slug=target_agent_slug,
        route_plan=route_plan,
    ):
        return {"handled": False, "reason": "no_public_context"}

    reason = f"amcham_public_journey_{public_intent}"
    answer = _answer_for_intent(public_intent)

    return {
        "handled": True,
        "reason": reason,
        "agent_id": "orkio",
        "agent_name": "Orkio",
        "final_speaker": "Orkio",
        "visible_agent": "Orkio",
        "answer": answer,
        "service": "amcham_public_journey_policy",
        "provider": "platform",
        "status": "done",
        "policy_version": AMCHAM_PUBLIC_JOURNEY_POLICY_VERSION,
        "public_intent": public_intent,
        "write_executed": False,
        "proposal_created": False,
        "dispatch_executed": False,
        "branch_created": False,
        "pr_created": False,
        "deploy_executed": False,
        "runtime_hints": _base_runtime_hints(reason, public_intent),
    }


def build_amcham_public_journey_stream_payload(
    decision: Dict[str, Any],
    *,
    persisted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = dict(persisted or {})
    final_text = str(decision.get("answer") or "").strip()

    data.update(
        {
            "ok": True,
            "answer": final_text,
            "message": final_text,
            "final_text": final_text,
            "content": final_text,
            "text": final_text,
            "agent_id": "orkio",
            "agent_name": "Orkio",
            "final_speaker": "Orkio",
            "visible_agent": "Orkio",
            "service": "amcham_public_journey_policy",
            "provider": "platform",
            "status": "done",
            "runtime_hints": decision.get("runtime_hints") or _base_runtime_hints(
                str(decision.get("reason") or "amcham_public_journey"),
                str(decision.get("public_intent") or "platform_exploration"),
            ),
        }
    )

    return data
