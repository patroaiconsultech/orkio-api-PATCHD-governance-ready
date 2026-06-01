# EFATAH777 — Public Orkio Policy
# Small, isolated policy module for the public Orkio CEO experience.
#
# Purpose:
# - Keep new public/product behavior out of app/main.py.
# - Make Orkio the stable public host for business/startup/platform conversations.
# - Avoid accidental technical-audit routes for commercial/product positioning.
# - Produce a useful initial scope and WhatsApp CTA for human follow-up.
#
# This module has no database, FastAPI or runtime side effects.

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


ORKIO_TEAM_WHATSAPP_NUMBER = "+5551989697605"
ORKIO_TEAM_WHATSAPP_URL = (
    "https://wa.me/5551989697605"
    "?text=Ol%C3%A1%2C%20quero%20conversar%20com%20a%20equipe%20ORKIO%2FPATROAI%20"
    "sobre%20agentes%20personalizados%20para%20minha%20empresa."
)


ORKIO_CEO_SCOPE_OVERLAY = f"""
ORKIO_PUBLIC_CEO_MODE — contrato de resposta pública e comercial

Você é Orkio, o agente principal e CEO digital da plataforma ORKIO OS / PATROAI.
Sua função pública é entender dores reais de empreendedores, empresários, executivos e investidores,
organizar essas dores em uma visão executiva e sugerir uma primeira arquitetura de agentes personalizados.

Competências executivas que você deve simular com maturidade:
- CFO/financeiro: caixa, custos, margem, indicadores, inadimplência, valuation, captação e previsibilidade.
- Marketing: posicionamento, canais, conteúdo, funil, diferenciação, marca e geração de demanda.
- Vendas/comercial: prospecção, CRM, follow-up, conversão, qualificação, propostas e relacionamento.
- Operações: processos, gargalos, rotinas manuais, produtividade, atendimento e padronização.
- Produto/tecnologia: automação com IA, agentes personalizados, dados necessários, integrações e roadmap.
- Gestão: prioridades, equipe, rituais, acompanhamento, metas e governança.

Quando o usuário trouxer uma dor de negócio, não responda de forma genérica.
Entregue um ESCOPO INICIAL claro, curto e útil, preferencialmente com:
1. Dor identificada
2. Impacto provável no negócio
3. Agentes personalizados recomendados
4. Dados/processos que precisaríamos mapear
5. Primeiro passo sugerido

Sempre que houver demanda concreta, interesse comercial, necessidade de automação, criação de agentes,
diagnóstico empresarial ou pedido de implantação, indique contato humano com a equipe ORKIO/PATROAI.

CTA obrigatório quando houver oportunidade real:
"Para transformar esse escopo em um projeto sob medida, fale com nossa equipe pelo WhatsApp:
{ORKIO_TEAM_WHATSAPP_URL}"

Regras de verdade operacional:
- Não diga que todos os especialistas multiagente estão plenamente liberados para o público.
- Explique, se necessário, que o ORKIO OS foi desenhado para arquitetura multiagente e que a ativação de agentes
  personalizados é feita de forma progressiva, conforme a necessidade de cada empresa.
- Não prometa integrações, automações, auditorias ou execuções que não tenham sido confirmadas.
- Não exponha logs, runtime, GitHub, patches, terminal guard ou detalhes internos para usuário público.
- Fale em pt-BR, com tom premium, claro, humano, executivo e confiante.
- Seja consultivo: entenda, estruture e conduza para o próximo passo.
""".strip()


def normalize_text(value: Any) -> str:
    raw = str(value or "")
    try:
        raw = unicodedata.normalize("NFD", raw)
        raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    except Exception:
        pass
    raw = raw.lower()
    raw = re.sub(r"[^a-z0-9@:/.\-_\s]+", " ", raw, flags=re.I)
    return re.sub(r"\s+", " ", raw).strip()


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _has_explicit_specialist_mention(normalized: str) -> bool:
    return bool(re.search(r"(^|\s)@(chris|cris|orion)\b", normalized))


def _explicit_orkio_or_team(normalized: str, visible_agent: Any = None, target_agent_slug: Any = None) -> bool:
    visible = normalize_text(visible_agent)
    target = normalize_text(target_agent_slug)
    if re.search(r"(^|\s)@(orkio|team)\b", normalized):
        return True
    if visible in {"orkio", "team", "@orkio", "@team"}:
        return True
    if target in {"orkio", "team", "@orkio", "@team"}:
        return True
    return False


def _is_site_access_question(normalized: str) -> bool:
    site_markers = [
        "site",
        "www.",
        "http://",
        "https://",
        ".com",
        ".com.br",
        "patroai.com",
    ]
    access_markers = [
        "acessar",
        "acesse",
        "tente acessar",
        "conseguiu acessar",
        "voce conseguiu",
        "vc conseguiu",
        "entrar no site",
        "ler o site",
        "consultar o site",
    ]
    return _contains_any(normalized, site_markers) and _contains_any(normalized, access_markers)


def _has_hard_technical_intent(normalized: str) -> bool:
    """
    Hard technical intent means the request should stay with engineering/audit routes.
    Business words like governanca/rastreabilidade/execucao are intentionally NOT enough
    to make a message technical here.
    """
    hard_markers = [
        "app/main.py",
        "main.py",
        "stacktrace",
        "traceback",
        "logs",
        "log do deploy",
        "runtime",
        "sse",
        "stream",
        "terminal guard",
        "ao46c",
        "ao20",
        "patch",
        "diff",
        "rollback",
        "commit",
        "branch",
        "pull request",
        "pr ",
        "github",
        "git ",
        "endpoint",
        "api ",
        "webhook",
        "deploy",
        "build",
        "erro tecnico",
        "falha tecnica",
        "auditoria tecnica",
        "auditar codigo",
        "router",
        "orquestracao real",
        "multiagente distribuido",
    ]
    return _contains_any(normalized, hard_markers)


def _has_product_ceo_intent(normalized: str) -> bool:
    product_markers = [
        "business plan",
        "plano de negocio",
        "plano de negocios",
        "startup",
        "startups",
        "criacao de startup",
        "criacao de startups",
        "criar startup",
        "criar startups",
        "estrategia a execucao",
        "estrategia ate a execucao",
        "execucao do business plan",
        "business plan vivo",
        "plano vivo",
        "app",
        "aplicativo",
        "plataforma",
        "saas",
        "agentes personalizados",
        "agente personalizado",
        "criar agentes",
        "automacao",
        "automatizar",
        "empreendedor",
        "empreendedores",
        "empresa pequena",
        "minha empresa",
        "financeiro",
        "cfo",
        "vendas",
        "comercial",
        "marketing",
        "operacao",
        "operacoes",
        "atendimento",
        "processos",
        "processos manuais",
        "rastreabilidade",
        "governanca",
        "precisao",
        "governança",
        "go to market",
        "investidor",
        "captacao",
        "captacao de recursos",
        "valuation",
        "pitch",
        "mvp",
    ]
    return _contains_any(normalized, product_markers)


def _needs_for_message(normalized: str) -> List[str]:
    needs: List[str] = []
    mapping = [
        ("CFO/financeiro", ["financeiro", "cfo", "caixa", "custos", "margem", "indicadores", "inadimplencia", "valuation", "captacao"]),
        ("Marketing e posicionamento", ["marketing", "marca", "conteudo", "posicionamento", "demanda", "go to market"]),
        ("Vendas/comercial", ["vendas", "comercial", "crm", "follow up", "prospeccao", "prospecção", "converter", "funil"]),
        ("Operações/processos", ["operacao", "operacoes", "processos", "manual", "gargalo", "produtividade", "atendimento"]),
        ("Produto e tecnologia", ["app", "aplicativo", "plataforma", "saas", "mvp", "tecnologia", "automacao", "automatizar"]),
        ("Estratégia e execução", ["startup", "business plan", "plano de negocio", "estrategia", "execucao", "roadmap"]),
        ("Governança e rastreabilidade", ["governanca", "governança", "rastreabilidade", "precisao", "compliance"]),
    ]
    for label, markers in mapping:
        if _contains_any(normalized, markers):
            needs.append(label)
    return list(dict.fromkeys(needs))[:5]


def _agents_for_needs(needs: List[str]) -> List[str]:
    if not needs:
        return [
            "Agente de Diagnóstico Executivo",
            "Agente de Business Plan Vivo",
            "Agente de Roadmap e Execução",
        ]

    suggestions: List[str] = []
    for need in needs:
        if "CFO" in need:
            suggestions.extend(["Agente CFO", "Agente de Indicadores Financeiros"])
        elif "Marketing" in need:
            suggestions.extend(["Agente de Marketing Estratégico", "Agente de Conteúdo e Posicionamento"])
        elif "Vendas" in need:
            suggestions.extend(["Agente Comercial/CRM", "Agente de Follow-up e Propostas"])
        elif "Operações" in need:
            suggestions.extend(["Agente de Processos", "Agente de Atendimento e Operações"])
        elif "Produto" in need:
            suggestions.extend(["Agente de Produto/MVP", "Agente de Arquitetura de Plataforma"])
        elif "Estratégia" in need:
            suggestions.extend(["Agente de Business Plan Vivo", "Agente de Execução e Milestones"])
        elif "Governança" in need:
            suggestions.extend(["Agente de Governança", "Agente de Rastreabilidade e Decisões"])
    return list(dict.fromkeys(suggestions))[:6]


def _site_access_answer() -> str:
    return (
        "Eu não consigo confirmar navegação direta em sites externos a partir desta conversa.\n\n"
        "Mas consigo avançar de duas formas úteis:\n\n"
        "1. Se você colar aqui o conteúdo do site, eu organizo a leitura em posicionamento, proposta de valor, "
        "oferta, público-alvo, diferenciais e próximos passos.\n"
        "2. Se a ideia for transformar o site em um projeto real de agentes, nossa equipe pode fazer o mapeamento humano "
        "e converter isso em um escopo inicial de implantação.\n\n"
        "Para seguir pelo caminho prático, fale com a equipe ORKIO/PATROAI pelo WhatsApp:\n"
        f"{ORKIO_TEAM_WHATSAPP_URL}"
    )


def _build_scope_answer(message: Any, normalized: str) -> str:
    needs = _needs_for_message(normalized)
    agents = _agents_for_needs(needs)

    if needs:
        needs_text = "\n".join(f"- {item}" for item in needs)
    else:
        needs_text = (
            "- Estratégia do negócio\n"
            "- Produto ou serviço principal\n"
            "- Modelo de receita\n"
            "- Operação e execução\n"
            "- Tecnologia e agentes personalizados"
        )

    agents_text = "\n".join(f"- {item}" for item in agents)

    return (
        "Entendi. Esse é exatamente o tipo de problema que o ORKIO deve transformar em projeto real.\n\n"
        "A tese é forte: usar a plataforma para criar startups e negócios digitais da estratégia à execução, "
        "com Business Plan vivo, governança, rastreabilidade e agentes personalizados acompanhando a operação.\n\n"
        "Escopo inicial recomendado:\n\n"
        "1. Dor ou oportunidade identificada\n"
        "Mapear qual problema econômico, operacional ou comercial o negócio precisa resolver primeiro.\n\n"
        "2. Áreas que entram no diagnóstico\n"
        f"{needs_text}\n\n"
        "3. Agentes personalizados recomendados\n"
        f"{agents_text}\n\n"
        "4. Dados e processos que precisaríamos levantar\n"
        "- Produto ou serviço que será vendido.\n"
        "- Público-alvo e região de atuação.\n"
        "- Ticket médio, custos, margem e metas.\n"
        "- Canais de venda e relacionamento.\n"
        "- Processos manuais que podem virar agentes.\n"
        "- Indicadores que o operador do negócio precisa acompanhar.\n\n"
        "5. Como a ORKIO/PATROAI pode conduzir\n"
        "- Primeiro organizamos a estratégia e o Business Plan vivo.\n"
        "- Depois desenhamos os agentes necessários para executar e acompanhar o plano.\n"
        "- Em seguida estruturamos o roadmap de MVP, validação, operação e escala.\n"
        "- Quando fizer sentido, a equipe pode também executar a construção do app, plataforma ou automações.\n\n"
        "Para transformar esse escopo em um projeto sob medida, fale com nossa equipe pelo WhatsApp:\n"
        f"{ORKIO_TEAM_WHATSAPP_URL}"
    )


def build_public_orkio_policy_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Decide whether the public Orkio CEO policy should handle this turn.

    It intentionally handles only business/product/startup/site conversations where
    Orkio should be the stable public host. It refuses explicit @Chris/@Orion
    specialist calls and hard engineering/audit requests.
    """
    normalized = normalize_text(message)
    if not normalized:
        return {"handled": False, "reason": "empty"}

    if _has_explicit_specialist_mention(normalized):
        return {"handled": False, "reason": "explicit_specialist_mention"}

    # Hard engineering still belongs to the existing technical routes.
    if _has_hard_technical_intent(normalized):
        return {"handled": False, "reason": "hard_technical_intent"}

    site_question = _is_site_access_question(normalized)
    product_intent = _has_product_ceo_intent(normalized)
    orkio_or_team = _explicit_orkio_or_team(normalized, visible_agent=visible_agent, target_agent_slug=target_agent_slug)

    if not site_question and not product_intent:
        return {"handled": False, "reason": "no_public_product_intent"}

    # If it is product/business intent, Orkio can own it in Team/Orkio/no-explicit mode.
    # This prevents stale Chris/AO45A/AO20BC paths from taking over public positioning.
    if not orkio_or_team:
        # No visible explicit target is still acceptable for product/public requests,
        # because Orkio is the public host. But a non-Orkio explicit visible target is not.
        visible = normalize_text(visible_agent)
        target = normalize_text(target_agent_slug)
        if visible in {"chris", "cris", "orion"} or target in {"chris", "cris", "orion"}:
            return {"handled": False, "reason": "visible_specialist_target"}

    answer = _site_access_answer() if site_question else _build_scope_answer(message, normalized)
    reason = "site_access_limitation" if site_question else "public_product_ceo_scope"

    return {
        "handled": True,
        "reason": reason,
        "agent_id": "orkio",
        "agent_name": "Orkio",
        "final_speaker": "Orkio",
        "answer": answer,
        "routing_source": "public_orkio_policy_module",
        "runtime_hints": {
            "routing": {
                "routing_source": "public_orkio_policy_module",
                "route_applied": True,
                "execution_lifecycle": "completed",
                "final_speaker": "Orkio",
                "policy_module": "app.runtime.public_orkio_policy",
                "policy_reason": reason,
                "write_executed": False,
                "proposal_created": False,
                "dispatch_executed": False,
                "blocked_routes": [
                    "chris_business_plan_fastpath",
                    "chris_ao45a_context_continuation",
                    "ao20bc_technical_audit_for_business_positioning",
                ],
            }
        },
    }



def build_public_orkio_stream_payload(
    decision: Dict[str, Any],
    *,
    persisted: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the normalized payload expected by app/main.py SSE emitter.
    """
    data = dict(persisted or {})
    final_text = str(decision.get("answer") or "").strip()
    data.update({
        "ok": True,
        "answer": final_text,
        "message": final_text,
        "final_text": final_text,
        "content": final_text,
        "text": final_text,
        "agent_id": "orkio",
        "agent_name": "Orkio",
        "final_speaker": "Orkio",
        "service": "public_orkio_policy_module",
        "provider": "platform",
        "status": "done",
        "runtime_hints": decision.get("runtime_hints") or {
            "routing": {
                "routing_source": "public_orkio_policy_module",
                "route_applied": True,
                "execution_lifecycle": "completed",
                "final_speaker": "Orkio",
                "write_executed": False,
            }
        },
    })
    return data

def append_orkio_ceo_scope_overlay(
    system_prompt: Optional[str],
    *,
    agent_name: Any = None,
    final_speaker: Any = None,
) -> str:
    """
    Add Orkio public CEO instructions only when Orkio is the responding agent.
    """
    base = str(system_prompt or "").strip()
    names = [
        str(agent_name or "").strip().lower(),
        str(final_speaker or "").strip().lower(),
    ]
    is_orkio = any(name in {"orkio", "@orkio", "orkio (ceo)"} for name in names)
    if not is_orkio:
        return base
    if "ORKIO_PUBLIC_CEO_MODE" in base:
        return base
    return (base + "\n\n" + ORKIO_CEO_SCOPE_OVERLAY).strip() if base else ORKIO_CEO_SCOPE_OVERLAY
