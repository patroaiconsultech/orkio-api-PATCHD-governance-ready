from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional


CHRIS_POLICY_VERSION = "PUBLIC_CHRIS_POLICY_V1_EXECUTIVE_PREMIUM"

_FORBIDDEN_NEGATIVE_FRAMES = (
    "não está madura",
    "nao esta madura",
    "não está pronta para uso sério",
    "nao esta pronta para uso serio",
    "não serve para uso sério",
    "nao serve para uso serio",
    "não apresentar a investidores",
    "nao apresentar a investidores",
    "não está pronta para investidores",
    "nao esta pronta para investidores",
)


def _strip_accents(value: Any) -> str:
    raw = str(value or "")
    normalized = unicodedata.normalize("NFD", raw)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _strip_accents(value).lower()).strip()


def _target_is_chris(
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
        "@chris" in text
        or visible.startswith("chris")
        or target.startswith("chris")
        or route_requested.startswith("chris")
        or route_resolved.startswith("chris")
        or (mode == "single" and (target.startswith("chris") or visible.startswith("chris")))
    )


def _classify_chris_intent(message: Any) -> str:
    text = _norm(message)

    if any(k in text for k in ("em uma frase", "uma frase", "resuma", "resumo executivo", "leitura executiva")):
        return "executive_one_sentence"

    if any(k in text for k in ("investidor", "investidores", "pitch", "captacao", "cap table", "valuation", "rodada", "seed", "series a")):
        return "investor_ready"

    if any(k in text for k in ("business plan", "plano de negocios", "plano de negócio", "dre", "fluxo de caixa", "projecao financeira", "projeções financeiras")):
        return "business_plan"

    if any(k in text for k in ("vendas", "comercial", "go-to-market", "go to market", "funil", "crm", "prospeccao", "prospecção", "follow-up", "marketing")):
        return "growth_sales"

    if any(k in text for k in ("financeiro", "cfo", "caixa", "margem", "custos", "receita", "payback", "tir", "vpl")):
        return "cfo"

    if any(k in text for k in ("agentes", "agente personalizado", "arquitetura de agentes", "orquestracao", "orquestração")):
        return "agent_architecture"

    return "executive_general"


def _whatsapp_cta() -> str:
    return (
        "Se quiser transformar essa leitura em um projeto real, a equipe ORKIO/PATROAI pode "
        "mapear o cenário, priorizar os agentes necessários e desenhar um escopo de implantação."
    )


def _sanitize_public_answer(answer: str) -> str:
    text = str(answer or "").strip()
    low = _norm(text)
    if any(frame in low for frame in _FORBIDDEN_NEGATIVE_FRAMES):
        return (
            "A PatroAI/ORKIO está se posicionando como uma plataforma premium para transformar ideias, "
            "empresas e oportunidades em negócios digitais estruturados, combinando Business Plan vivo, "
            "agentes personalizados, visão financeira, go-to-market e execução tecnológica sob demanda."
        )
    return text


def _answer_one_sentence() -> str:
    return (
        "A PatroAI/ORKIO está se posicionando como uma plataforma premium para transformar ideias e empresas "
        "em negócios digitais estruturados, combinando Business Plan vivo, agentes personalizados, estratégia "
        "executiva e execução tecnológica sob demanda."
    )


def _answer_investor_ready() -> str:
    return """Chris — leitura executiva para investidores

A tese da PatroAI/ORKIO é forte porque une três dimensões que investidores valorizam: mercado real, tecnologia proprietária e capacidade de execução.

1. Tese central
A plataforma pode ser posicionada como um sistema de criação e estruturação de negócios digitais: parte da estratégia, organiza um Business Plan vivo, recomenda agentes personalizados e permite avançar para execução tecnológica.

2. Diferencial competitivo
O valor não está apenas em responder perguntas, mas em transformar contexto empresarial em plano, governança, indicadores, escopo de agentes e roadmap de implantação.

3. Modelo de crescimento
A empresa pode monetizar por implantação, agentes personalizados, contratos recorrentes, automações, inteligência executiva e projetos sob medida.

4. Riscos a tratar com maturidade
Os principais pontos de atenção são foco comercial, prova de valor com casos reais, clareza de oferta, estabilidade da experiência e priorização dos segmentos iniciais.

5. Próximo passo executivo
Criar uma narrativa investidor-ready com mercado, produto, receita, roadmap, equipe, governança e três casos de uso demonstráveis.

""" + _whatsapp_cta()


def _answer_business_plan() -> str:
    return """Chris — estrutura executiva do Business Plan

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
Receitas, custos, margem, payback, cenários, valuation, necessidade de capital e milestones de tração.

7. Governança e execução
Ritmo de implantação, indicadores, responsabilidades, riscos e validação por ciclos.

""" + _whatsapp_cta()


def _answer_growth_sales() -> str:
    return """Chris — leitura comercial e go-to-market

O caminho mais forte é vender a PatroAI/ORKIO como uma plataforma de transformação prática: ela entende a dor, desenha o agente certo e ajuda a empresa a sair do diagnóstico para execução.

1. Posicionamento
Não vender “chatbot”. Vender inteligência executiva aplicada a processos, vendas, financeiro, atendimento e operação.

2. Oferta inicial
Diagnóstico, escopo de agentes personalizados, Business Plan vivo e roadmap de implantação.

3. Funil comercial
Atrair dores concretas, qualificar urgência, mapear impacto financeiro, propor agentes prioritários e conduzir para projeto-piloto.

4. Agentes recomendados
Agente comercial, agente de CRM, agente de follow-up, agente de proposta, agente de marketing e agente de indicadores.

5. Próximo passo
Criar três ofertas claras: diagnóstico executivo, implantação inicial e pacote premium de agentes sob medida.

""" + _whatsapp_cta()


def _answer_cfo() -> str:
    return """Chris — visão CFO executiva

A leitura financeira deve transformar a plataforma em uma decisão de investimento, não apenas em uma ferramenta de produtividade.

1. Pergunta central
Qual dor econômica o agente resolve e quanto isso vale para o cliente?

2. Indicadores prioritários
Receita, margem, custo operacional, tempo economizado, conversão comercial, inadimplência, retrabalho e previsibilidade de caixa.

3. Modelo de monetização
Setup de implantação, recorrência mensal, agentes adicionais, automações e projetos enterprise.

4. Agentes recomendados
Agente CFO, agente de projeções, agente de precificação, agente de DRE, agente de fluxo de caixa e agente de indicadores.

5. Próximo passo
Mapear uma planilha-base com receita, custos, metas e gargalos para transformar a dor em escopo financeiro mensurável.

""" + _whatsapp_cta()


def _answer_agent_architecture() -> str:
    return """Chris — arquitetura executiva de agentes

A orquestração da Chris deve ser apresentada como uma camada executiva: ela organiza o negócio por eixos de decisão e recomenda os especialistas certos para cada demanda.

Eixos sob a Chris:
- Chris CFO: caixa, margem, projeções, valuation e captação.
- Chris Growth: posicionamento, marketing, funil e aquisição.
- Chris Sales: comercial, CRM, propostas e follow-up.
- Chris Investor: pitch, tese, risco, tração e narrativa.
- Chris Business Plan: plano vivo, roadmap e indicadores.
- Chris Operations: processos, rotinas, atendimento e eficiência.

Nota de governança:
Nesta resposta, eu organizo a análise pelos eixos executivos da Chris. A ativação de agentes especializados pode ser desenhada conforme a demanda e implementada de forma controlada pela equipe ORKIO/PATROAI.

""" + _whatsapp_cta()


def _answer_general() -> str:
    return """Chris — leitura executiva

A PatroAI/ORKIO tem potencial para se posicionar como uma plataforma premium de criação, estruturação e execução de negócios digitais com IA.

1. Oportunidade
Empreendedores e empresas precisam transformar ideias soltas, processos manuais e decisões dispersas em planos executáveis.

2. Proposta de valor
A plataforma pode entregar Business Plan vivo, arquitetura de agentes personalizados, visão financeira, go-to-market e roadmap de execução.

3. Diferencial
O diferencial é combinar inteligência executiva com implantação prática: estratégia, agentes, governança e construção tecnológica sob demanda.

4. Próxima ação
Priorizar uma oferta clara, demonstrável e vendável: diagnóstico executivo + escopo de agentes + plano inicial de implantação.

""" + _whatsapp_cta()


def build_public_chris_policy_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a deterministic public Chris answer when Chris is explicitly targeted."""
    if not _target_is_chris(
        message=message,
        visible_agent=visible_agent,
        target_agent_slug=target_agent_slug,
        dest_mode=dest_mode,
        route_plan=route_plan,
    ):
        return {"handled": False, "reason": "not_chris_target"}

    intent = _classify_chris_intent(message)

    answers = {
        "executive_one_sentence": _answer_one_sentence,
        "investor_ready": _answer_investor_ready,
        "business_plan": _answer_business_plan,
        "growth_sales": _answer_growth_sales,
        "cfo": _answer_cfo,
        "agent_architecture": _answer_agent_architecture,
        "executive_general": _answer_general,
    }

    answer = _sanitize_public_answer(answers.get(intent, _answer_general)())

    return {
        "handled": True,
        "agent_name": "Chris",
        "agent_id": None,
        "answer": answer,
        "reason": f"public_chris_{intent}",
        "policy_version": CHRIS_POLICY_VERSION,
        "intent": intent,
        "write_executed": False,
    }


def build_public_chris_stream_payload(
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
        "agent_name": decision.get("agent_name") or "Chris",
        "final_speaker": "Chris",
        "visible_agent": "Chris",
        "service": "public_chris_policy",
        "provider": "platform",
        "status": "done",
        "runtime_hints": {
            "routing": {
                "routing_source": "public_chris_policy_module",
                "route_applied": True,
                "execution_lifecycle": "completed",
                "route_family": "public_executive_strategy",
                "route_reason": decision.get("reason") or "",
                "policy_version": decision.get("policy_version") or CHRIS_POLICY_VERSION,
                "write_executed": False,
                "proposal_created": False,
                "branch_created": False,
                "pr_created": False,
            }
        },
    }
