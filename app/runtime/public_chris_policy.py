from __future__ import annotations
import re
import unicodedata
from typing import Any, Dict, Optional

from .business_self_improvement import (
    render_business_improvement_diagnosis,
    render_business_plan_vivo_brief,
    render_business_priority_plan,
    render_business_specialist_assignment,
)
from .runtime_feature_flags import (
    get_consultive_team_label,
    is_business_self_improvement_enabled,
    is_chris_business_squad_enabled,
    is_consultive_success_enabled,
    is_public_chris_policy_enabled,
)

CHRIS_POLICY_VERSION = "PUBLIC_CHRIS_POLICY_V4_BUSINESS_SQUAD_NO_CYCLE"

def _strip_accents(value: Any) -> str:
    raw = str(value or "")
    normalized = unicodedata.normalize("NFD", raw)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _strip_accents(value).lower()).strip()

def _target_is_chris(*, message: Any, visible_agent: Any = None, target_agent_slug: Any = None, dest_mode: Any = None, route_plan: Optional[Dict[str, Any]] = None) -> bool:
    text, visible, target, mode = _norm(message), _norm(visible_agent), _norm(target_agent_slug), _norm(dest_mode)
    route = route_plan if isinstance(route_plan, dict) else {}
    route_requested = _norm(route.get("requested_agent") or route.get("requested") or "")
    route_resolved = _norm(route.get("resolved_agent") or route.get("final_speaker") or "")
    return bool("@chris" in text or visible.startswith("chris") or target.startswith("chris") or route_requested.startswith("chris") or route_resolved.startswith("chris") or (mode == "single" and (target.startswith("chris") or visible.startswith("chris"))))

def _contains(text: str, values: tuple[str, ...]) -> bool:
    return any(v in text for v in values)

def _classify_chris_intent(message: Any) -> str:
    text = _norm(message)
    if _contains(text, ("o que o negocio precisa melhorar","o que o negócio precisa melhorar","melhorar comercialmente","melhorar como negocio","melhorar como negócio","diagnostico de negocio","diagnóstico de negócio","evolucao de negocio","evolução de negócio","oportunidades de negocio","oportunidades de negócio")):
        return "business_improvement_diagnosis"
    if _contains(text, ("plano de evolucao de negocio","plano de evolução de negócio","plano de evolucao","plano de evolução","prioridades de negocio","prioridades de negócio","plano por prioridade","roadmap de negocio","roadmap de negócio","por prioridade")):
        return "business_priority_plan"
    if _contains(text, ("especialistas da chris","equipe da chris","squad da chris","quais especialistas de negocio","quais especialistas de negócio","quais especialistas","quem deveria atuar no negocio","quem deveria atuar no negócio")):
        return "business_specialist_assignment"
    if _contains(text, ("business plan vivo","modulo business plan","módulo business plan","pagina business plan","página business plan","business plan dentro da plataforma")):
        return "business_plan_vivo"
    if _contains(text, ("em uma frase","uma frase","resuma","resumo executivo","leitura executiva")):
        return "executive_one_sentence"
    if _contains(text, ("investidor","investidores","pitch","captacao","valuation","rodada","seed","series a")):
        return "investor_ready"
    if _contains(text, ("business plan","plano de negocios","plano de negócio","dre","fluxo de caixa","projecao financeira","projeções financeiras")):
        return "business_plan"
    if _contains(text, ("vendas","comercial","go-to-market","go to market","funil","crm","prospeccao","prospecção","follow-up","marketing")):
        return "growth_sales"
    if _contains(text, ("financeiro","cfo","caixa","margem","custos","receita","payback","tir","vpl")):
        return "cfo"
    if _contains(text, ("agentes","agente personalizado","arquitetura de agentes","orquestracao","orquestração")):
        return "agent_architecture"
    return "executive_general"

def _whatsapp_cta() -> str:
    if not is_consultive_success_enabled():
        return ""
    return f"Se quiser transformar essa leitura em um projeto real, a {get_consultive_team_label()} pode mapear o cenário, priorizar os agentes necessários e desenhar um escopo de implantação."

def _with_cta(body: str) -> str:
    cta = _whatsapp_cta()
    return (str(body or "").strip() + ("\n\n" + cta if cta else "")).strip()

def _answer_one_sentence() -> str:
    return "A PatroAI/ORKIO está se posicionando como uma plataforma premium para transformar ideias e empresas em negócios digitais estruturados, combinando Business Plan vivo, agentes personalizados, estratégia executiva e execução tecnológica sob demanda."

def _answer_general() -> str:
    return _with_cta("""Chris — leitura executiva

A PatroAI/ORKIO tem potencial para se posicionar como uma plataforma premium de criação, estruturação e execução de negócios digitais com IA.

1. Oportunidade
Empreendedores e empresas precisam transformar ideias soltas, processos manuais e decisões dispersas em planos executáveis.

2. Proposta de valor
A plataforma pode entregar Business Plan vivo, arquitetura de agentes personalizados, visão financeira, go-to-market e roadmap de execução.

3. Diferencial
O diferencial é combinar inteligência executiva com implantação prática: estratégia, agentes, governança e construção tecnológica sob demanda.

4. Próxima ação
Priorizar uma oferta clara, demonstrável e vendável: diagnóstico executivo + escopo de agentes + plano inicial de implantação.""")

def _answer_business_plan() -> str:
    return _with_cta("""Chris — estrutura executiva do Business Plan

Eu organizaria o Business Plan da PatroAI/ORKIO em blocos de decisão, não como documento estático.

1. Sumário executivo
Tese, problema, oportunidade, solução, mercado, diferencial e próximos marcos.

2. Mercado e cliente-alvo
Segmentos prioritários, dores reais, urgência econômica, perfil decisor e tamanho da oportunidade.

3. Oferta e modelo de receita
Implantação, agentes personalizados, assinatura recorrente, projetos sob medida, automações e serviços executivos.

4. Go-to-market
Canais, funil, proposta de valor, vendas consultivas, parcerias e prova de autoridade.

5. Operação e tecnologia
Arquitetura da plataforma, criação de agentes, governança, rastreabilidade, dados necessários e roadmap de produto.

6. Financeiro
Receitas, custos, margem, payback, cenários, valuation, necessidade de capital e milestones de tração.""")

def _answer_investor_ready() -> str:
    return _with_cta("Chris — leitura executiva para investidores\n\nA tese da PatroAI/ORKIO é forte porque une mercado real, tecnologia proprietária e capacidade de execução. O próximo passo é consolidar narrativa, tração, riscos controláveis, modelo de receita e marcos de captação.")

def _answer_growth_sales() -> str:
    return _with_cta("Chris — leitura comercial e go-to-market\n\nO caminho mais forte é vender diagnóstico executivo, escopo de agentes personalizados, Business Plan vivo e implantação acompanhada, com funil consultivo e prova rápida de valor.")

def _answer_cfo() -> str:
    return _with_cta("Chris — visão CFO executiva\n\nA leitura financeira deve mostrar qual dor econômica o agente resolve, quanto isso vale para o cliente, qual modelo de receita captura valor e quais indicadores provam ROI.")

def _answer_agent_architecture() -> str:
    return _with_cta("Chris — arquitetura executiva de agentes\n\nA Chris organiza o negócio por eixos: CFO, Growth, Sales, Marketing, Investor, Business Plan, Operations, Customer Success, Pricing e Partnerships.")

def build_public_chris_policy_decision(message: Any, *, visible_agent: Any = None, target_agent_slug: Any = None, dest_mode: Any = None, route_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not is_public_chris_policy_enabled():
        return {"handled": False, "reason": "public_chris_policy_disabled"}
    if not _target_is_chris(message=message, visible_agent=visible_agent, target_agent_slug=target_agent_slug, dest_mode=dest_mode, route_plan=route_plan):
        return {"handled": False, "reason": "not_chris_target"}

    intent = _classify_chris_intent(message)
    if intent in {"business_improvement_diagnosis", "business_priority_plan", "business_plan_vivo"} and not is_business_self_improvement_enabled():
        intent = "executive_general"
    if intent == "business_specialist_assignment" and not is_chris_business_squad_enabled():
        intent = "executive_general"

    answers = {
        "business_improvement_diagnosis": render_business_improvement_diagnosis,
        "business_priority_plan": render_business_priority_plan,
        "business_specialist_assignment": render_business_specialist_assignment,
        "business_plan_vivo": render_business_plan_vivo_brief,
        "executive_one_sentence": _answer_one_sentence,
        "investor_ready": _answer_investor_ready,
        "business_plan": _answer_business_plan,
        "growth_sales": _answer_growth_sales,
        "cfo": _answer_cfo,
        "agent_architecture": _answer_agent_architecture,
        "executive_general": _answer_general,
    }
    answer = answers.get(intent, _answer_general)()
    return {"handled": True, "agent_name": "Chris", "agent_id": None, "answer": answer, "reason": f"public_chris_{intent}", "policy_version": CHRIS_POLICY_VERSION, "intent": intent, "write_executed": False}

def build_public_chris_stream_payload(decision: Dict[str, Any], *, persisted: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        "agent_name": decision.get("agent_name") or "Chris",
        "final_speaker": "Chris",
        "visible_agent": "Chris",
        "service": "public_chris_policy",
        "provider": "platform",
        "status": "done",
        "runtime_hints": {"routing": {"routing_source": "public_chris_policy_module", "route_applied": True, "execution_lifecycle": "completed", "route_family": "public_executive_strategy", "route_reason": decision.get("reason") or "", "policy_version": decision.get("policy_version") or CHRIS_POLICY_VERSION, "business_self_improvement_enabled": is_business_self_improvement_enabled(), "chris_business_squad_enabled": is_chris_business_squad_enabled(), "consultive_success_enabled": is_consultive_success_enabled(), "write_executed": False, "proposal_created": False, "branch_created": False, "pr_created": False}},
    }
