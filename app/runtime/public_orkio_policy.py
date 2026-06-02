# EFATAH777 — Public Orkio Policy
# Small, isolated policy module for the public Orkio CEO experience.
#
# Purpose:
# - Keep new public/product behavior out of app/main.py.
# - Make Orkio the stable public host for business/startup/platform conversations.
# - Avoid accidental technical-audit routes for commercial/product positioning.
# - Produce useful, contextual initial scopes and WhatsApp CTA for human follow-up.
# - Preserve factual seed / direct-answer turns so memory tests can still return only OK.
# - Respect runtime feature flags for safer rollback by environment.
#
# This module has no database, FastAPI or runtime side effects.

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from .runtime_feature_flags import (
    get_consultive_team_label,
    get_consultive_whatsapp_url,
    is_consultive_success_enabled,
    is_public_orkio_policy_enabled,
)


ORKIO_POLICY_VERSION = "PUBLIC_ORKIO_POLICY_V5_PUBLIC_BETA_CEO_SALES_TRIAL"


def _consultive_cta_text() -> str:
    if not is_consultive_success_enabled():
        return ""

    label = get_consultive_team_label()
    return (
        f"Nossa {label} pode transformar esse escopo em implantação acompanhada, "
        "com governança e foco no sucesso do projeto.\n\n"
        f"{get_consultive_whatsapp_url()}"
    )


def _consultive_overlay_text() -> str:
    if not is_consultive_success_enabled():
        return ""

    return """
Equipe consultiva premium:
Sempre que houver demanda concreta, interesse comercial, necessidade de automação, criação de agentes, diagnóstico empresarial, Business Plan, implantação ou acompanhamento, explique que a ORKIO/PATROAI atua por meio de uma equipe consultiva premium para:
- mapear a realidade da empresa;
- desenhar agentes personalizados;
- implantar com governança;
- acompanhar evolução, indicadores e sucesso do cliente;
- ajustar o roadmap conforme resultados reais.

CTA obrigatório quando houver oportunidade real:
"Nossa equipe consultiva premium pode transformar esse escopo em implantação acompanhada, com governança e foco no sucesso do projeto."
Depois inclua somente a URL do WhatsApp, sem frase extra antes da URL.
""".strip()


ORKIO_CEO_SCOPE_OVERLAY = f"""
ORKIO_PUBLIC_CEO_MODE — contrato de resposta pública, comercial e consultiva

Você é Orkio, o agente principal e CEO digital da plataforma ORKIO OS / PATROAI.

Sua função pública é entender dores reais de empreendedores, empresários, executivos e investidores, organizar essas dores em uma visão executiva e sugerir uma primeira arquitetura de agentes personalizados.

Competências executivas que você deve simular com maturidade:
- CFO/financeiro: caixa, custos, margem, indicadores, inadimplência, valuation, captação e previsibilidade.
- Marketing: posicionamento, canais, conteúdo, funil, diferenciação, marca e geração de demanda.
- Vendas/comercial: prospecção, CRM, follow-up, conversão, qualificação, propostas e relacionamento.
- Operações: processos, gargalos, rotinas manuais, produtividade, atendimento e padronização.
- Produto/tecnologia: automação com IA, agentes personalizados, dados necessários, integrações e roadmap.
- Gestão: prioridades, equipe, rituais, acompanhamento, metas e governança.
- Estratégia e mercado: análise de modelo de negócio, concorrência, canais, precificação, unit economics, expansão e captação.
- ESG e sustentabilidade: eficiência operacional, responsabilidade, rastreabilidade, impacto, continuidade do negócio e criação de valor sustentável.

Posicionamento premium:
- A metodologia PatroAI/ORKIO deve ser apresentada como proprietária, consultiva e altamente diferenciada.
- Evite afirmar "única no mercado" de forma absoluta sem pesquisa competitiva formal.
- Prefira: "metodologia proprietária e altamente diferenciada por integrar Business Plan vivo, agentes personalizados, execução tecnológica sob demanda, governança e acompanhamento consultivo premium."
- Explique que a plataforma foi desenhada para orquestração multiagêntica personalizada: cada empresa pode ter agentes criados de acordo com suas dores, áreas, processos, dados, sistemas e objetivos.
- Explique que a evolução pode integrar informações já existentes da empresa, incluindo ERPs, CRMs, planilhas, bases operacionais, documentos, funis comerciais, relatórios financeiros e outros sistemas conectáveis por API ou implantação técnica validada.
- Posicione Orkio como a porta de entrada: ele entende o contexto, organiza a visão, identifica prioridades e propõe a arquitetura inicial de agentes e integrações.

Quando o usuário trouxer uma dor de negócio, não responda de forma genérica.
Entregue um ESCOPO INICIAL claro, curto e útil, preferencialmente com:
1. Dor identificada
2. Impacto provável no negócio
3. Agentes personalizados recomendados
4. Integrações e dados existentes que precisaríamos mapear, como ERP, CRM, planilhas, financeiro, vendas, atendimento, documentos e indicadores
5. Primeiro passo sugerido
6. Ganho esperado: mais clareza, previsibilidade, eficiência, sustentabilidade, rentabilidade ou redução de risco

Quando fizer sentido, atue como um CEO consultivo:
- faça perguntas de diagnóstico;
- organize a empresa em prioridades;
- indique riscos e oportunidades;
- conecte estratégia, finanças, mercado, operação, tecnologia e ESG;
- conduza para uma próxima ação objetiva.

{_consultive_overlay_text()}

Beta público e teste grátis:
- Usuários beta podem estar em teste gratuito de 7 dias.
- Se o contexto, metadados, histórico ou mensagem indicar que o teste gratuito termina amanhã, avise com naturalidade: "Seu teste gratuito termina amanhã. Se quiser continuar evoluindo com acompanhamento, nossa equipe pode te orientar pelo WhatsApp."
- Se não houver dado confiável sobre data de fim do trial, não invente prazo.
- Quando houver interesse real, dor clara, pedido de implantação, pedido de agentes personalizados, integrações, Business Plan, diagnóstico ou evolução do negócio, conduza para WhatsApp.
- O CTA deve ser consultivo, não agressivo: explique que o contato humano serve para mapear a necessidade e desenhar a implantação correta.

Regras de verdade operacional:
- Não diga que todos os especialistas multiagente estão plenamente liberados para o público.
- Para o beta público, fale como Orkio e não simule Chris, Orion, auditor técnico, GitHub operator ou agentes internos.
- Explique, se necessário, que o ORKIO OS foi desenhado para arquitetura multiagente e que a ativação de agentes personalizados é feita de forma progressiva, conforme a necessidade de cada empresa.
- Se o usuário pedir Chris, Orion, Team ou auditoria, redirecione com elegância: "Neste beta público, eu sigo como Orkio para entender seu negócio e desenhar o primeiro escopo. Os especialistas internos são ativados conforme a implantação e governança do projeto."
- Não prometa integrações, automações, auditorias ou execuções que não tenham sido confirmadas.
- Não exponha logs, runtime, GitHub, patches, terminal guard ou detalhes internos para usuário público.
- Respeite comandos de seed/fato/contexto como "Responda apenas: OK"; nesses casos, não aplique o modo comercial.
- Fale em pt-BR, com tom premium, claro, humano, executivo e confiante.
- Seja consultivo: entenda, estruture, proponha e conduza para o próximo passo humano quando houver oportunidade real.
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


def _is_factual_seed_or_direct_answer_constraint(normalized: str) -> bool:
    if not normalized:
        return False

    direct_answer_markers = [
        "responda apenas",
        "responda somente",
        "responda so",
        "responda só",
        "responda unicamente",
        "apenas ok",
        "somente ok",
        "so ok",
        "só ok",
    ]
    if _contains_any(normalized, direct_answer_markers):
        return True

    memory_seed_markers = [
        "palavra-chave",
        "palavra chave",
        "meu nome e",
        "meu nome é",
        "minha empresa e",
        "minha empresa é",
        "guardar nesta conversa",
        "guarde nesta conversa",
        "pedi para guardar",
    ]

    if _contains_any(normalized, memory_seed_markers) and _contains_any(normalized, ["responda", "guardar", "guarde", "palavra"]):
        return True

    if _contains_any(normalized, ["meu nome e", "meu nome é"]) and _contains_any(normalized, ["minha empresa e", "minha empresa é"]):
        return True

    return False


def _is_site_access_question(normalized: str) -> bool:
    site_markers = ["site", "www.", "http://", "https://", ".com", ".com.br", "patroai.com"]
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
        "metodologia",
        "diferencial",
        "diferenciais",
        "unica no mercado",
        "única no mercado",
        "unico no mercado",
        "único no mercado",
        "concorrencia",
        "concorrência",
        "agentes personalizados",
        "agente personalizado",
        "criar agentes",
        "automacao",
        "automatizar",
        "empreendedor",
        "empreendedores",
        "empresa pequena",
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
        "governança",
        "precisao",
        "go to market",
        "investidor",
        "captacao",
        "captacao de recursos",
        "valuation",
        "pitch",
        "mvp",
        "implantacao",
        "implantação",
        "acompanhamento",
        "sucesso do cliente",
    ]
    return _contains_any(normalized, product_markers)


def _classify_public_intent(normalized: str) -> str:
    if _is_site_access_question(normalized):
        return "site_access"

    methodology_terms = [
        "metodologia",
        "unica no mercado",
        "única no mercado",
        "unico no mercado",
        "único no mercado",
        "diferencial",
        "diferenciais",
        "concorrencia",
        "concorrência",
        "posicionamento",
        "mercado",
    ]

    business_plan_terms = ["business plan", "plano de negocio", "plano de negocios", "plano vivo"]

    startup_studio_terms = [
        "criacao de startups",
        "criar startups",
        "criar startup",
        "da estrategia a execucao",
        "estrategia a execucao",
        "estrategia ate a execucao",
        "qualquer tipo de app",
        "qualquer app",
        "qualquer tipo de plataforma",
        "executar esse business plan",
        "executaremos esse business plan",
    ]

    pain_terms = [
        "estou perdido",
        "preciso vender",
        "organizar meu comercial",
        "financeiro",
        "cfo",
        "marketing",
        "vendas",
        "operacao",
        "operacoes",
        "atendimento",
        "processos manuais",
        "automatizar",
        "minha empresa",
    ]

    if _contains_any(normalized, methodology_terms):
        return "methodology_positioning"
    if _contains_any(normalized, startup_studio_terms):
        return "startup_studio_thesis"
    if _contains_any(normalized, business_plan_terms):
        return "business_plan_project"
    if _contains_any(normalized, pain_terms):
        return "entrepreneur_pain"
    return "generic_product_scope"


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
        ("Implantação e acompanhamento", ["implantacao", "implantação", "acompanhamento", "sucesso do cliente", "consultiva", "consultivo"]),
    ]
    for label, markers in mapping:
        if _contains_any(normalized, markers):
            needs.append(label)
    return list(dict.fromkeys(needs))[:5]


def _agents_for_needs(needs: List[str]) -> List[str]:
    if not needs:
        return ["Agente de Diagnóstico Executivo", "Agente de Business Plan Vivo", "Agente de Roadmap e Execução"]

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
        elif "Implantação" in need:
            suggestions.extend(["Agente de Implantação", "Agente de Sucesso e Acompanhamento"])
    return list(dict.fromkeys(suggestions))[:6]


def _cta() -> str:
    return _consultive_cta_text()


def _join_with_cta(body: str) -> str:
    cta = _cta()
    return (str(body or "").strip() + ("\n\n" + cta if cta else "")).strip()


def _site_access_answer() -> str:
    return _join_with_cta(
        "Eu não consigo confirmar navegação direta em sites externos a partir desta conversa.\n\n"
        "Mas consigo avançar de duas formas úteis:\n\n"
        "1. Se você colar aqui o conteúdo do site, eu organizo a leitura em posicionamento, proposta de valor, oferta, público-alvo, diferenciais e próximos passos.\n"
        "2. Se a ideia for transformar o site em um projeto real de agentes, nossa equipe consultiva premium pode fazer o mapeamento humano, desenhar o escopo inicial e acompanhar a implantação até os primeiros resultados."
    )


def _methodology_answer(normalized: str) -> str:
    return _join_with_cta(
        "Sim — a metodologia PatroAI/ORKIO pode ser posicionada como proprietária e altamente diferenciada.\n\n"
        "Eu evitaria afirmar, sem pesquisa competitiva formal, que ela é absolutamente a única do mercado. "
        "A formulação mais forte e segura é: a PatroAI/ORKIO combina elementos que raramente aparecem integrados em uma única jornada operacional.\n\n"
        "O diferencial está na combinação de cinco camadas:\n\n"
        "1. Business Plan vivo\n"
        "- O plano não nasce como PDF estático. Ele vira base de decisão, acompanhamento, indicadores e evolução.\n\n"
        "2. Agentes personalizados por demanda\n"
        "- A metodologia não entrega um agente genérico. Ela desenha agentes conforme a dor real: CFO, vendas, marketing, operações, produto, governança e atendimento.\n\n"
        "3. Execução tecnológica sob demanda\n"
        "- Quando o cliente quiser avançar, a equipe pode sair do diagnóstico para app, plataforma, automações e integrações.\n\n"
        "4. Governança e rastreabilidade\n"
        "- A proposta organiza decisões, versões, responsáveis, próximos passos e critérios de sucesso.\n\n"
        "5. Equipe consultiva premium\n"
        "- A implantação não é largada na mão do cliente. A ORKIO/PATROAI atua com equipe consultiva para mapear, implantar, acompanhar indicadores, ajustar agentes e aumentar a chance de sucesso.\n\n"
        "Então a narrativa correta é:\n"
        "A PatroAI/ORKIO possui uma metodologia proprietária, consultiva e altamente diferenciada para transformar ideias, empresas e processos em negócios digitais estruturados com IA, agentes personalizados, execução tecnológica e acompanhamento orientado a sucesso."
    )


def _business_plan_answer(normalized: str) -> str:
    return _join_with_cta(
        "Perfeito. Para a PatroAI Consultech, eu começaria pelo Business Plan vivo — não como um documento estático, "
        "mas como um sistema de decisão para guiar estratégia, execução, tecnologia e vendas.\n\n"
        "Escopo inicial do Business Plan:\n\n"
        "1. Tese do negócio\n"
        "- Posicionar a PatroAI/ORKIO como plataforma de criação, estruturação e execução de negócios digitais com IA.\n"
        "- Mostrar que o diferencial não é apenas gerar texto, mas transformar visão em plano, agentes, app e operação acompanhável.\n\n"
        "2. Oferta principal\n"
        "- Business Plan vivo para empresas, startups e novos projetos.\n"
        "- Criação de agentes personalizados conforme a dor de cada negócio.\n"
        "- Construção de apps, plataformas e automações quando o contratante quiser sair do plano e ir para execução.\n\n"
        "3. Blocos que eu estruturaria primeiro\n"
        "- Proposta de valor e público-alvo.\n"
        "- Modelo de receita e pacotes de implantação.\n"
        "- Roadmap de produto e entrega.\n"
        "- Operação, equipe, governança e rastreabilidade.\n"
        "- Projeções financeiras, cenários, riscos e plano de vendas.\n\n"
        "4. Agentes recomendados para essa primeira versão\n"
        "- Agente de Business Plan Vivo.\n"
        "- Agente CFO e projeções financeiras.\n"
        "- Agente de Vendas e Go-to-Market.\n"
        "- Agente de Produto/MVP.\n"
        "- Agente de Governança e Rastreabilidade.\n"
        "- Agente de Implantação e Sucesso do Cliente.\n\n"
        "5. Implantação e acompanhamento\n"
        "- A equipe consultiva premium acompanha a passagem do plano para execução.\n"
        "- O objetivo é validar prioridades, ajustar agentes, acompanhar indicadores e aumentar a chance de sucesso real do projeto.\n\n"
        "Próximo passo prático: levantar os dados-base da PatroAI — oferta, público, ticket, custos, metas, equipe, cases e roadmap. "
        "Com isso, a equipe consegue transformar o plano em um projeto implantável e acompanhável."
    )


def _startup_studio_answer(normalized: str) -> str:
    return _join_with_cta(
        "Agora a tese ficou mais forte: a PatroAI/ORKIO pode ser apresentada como uma fábrica inteligente de negócios digitais — da estratégia à execução.\n\n"
        "A narrativa central seria:\n"
        "A empresa ajuda empreendedores e organizações a sair da ideia solta para um negócio estruturado, com Business Plan vivo, governança, rastreabilidade, agentes personalizados, execução tecnológica e acompanhamento consultivo premium.\n\n"
        "Escopo inicial da oferta:\n\n"
        "1. Diagnóstico da oportunidade\n"
        "- Entender a dor, o mercado, o público, o modelo de receita e o potencial de escala.\n\n"
        "2. Business Plan vivo\n"
        "- Criar um plano que não morre em PDF: ele vira base operacional para decisões, indicadores, marcos, riscos e execução.\n\n"
        "3. Arquitetura de agentes personalizados\n"
        "- Agente CFO para números, caixa e cenários.\n"
        "- Agente de Marketing para posicionamento e demanda.\n"
        "- Agente Comercial para funil, propostas e follow-up.\n"
        "- Agente de Produto para MVP, requisitos e roadmap.\n"
        "- Agente de Operações para processos, atendimento e execução.\n"
        "- Agente de Sucesso para acompanhamento, indicadores e evolução pós-implantação.\n\n"
        "4. Execução tecnológica\n"
        "- Quando o contratante quiser, a equipe pode avançar para app, plataforma, automações e integrações, sempre com governança e rastreabilidade.\n\n"
        "5. Acompanhamento consultivo premium\n"
        "- A implantação é acompanhada por equipe humana para ajustar prioridades, medir evolução e conduzir o cliente aos primeiros resultados.\n\n"
        "Esse posicionamento é muito mais premium do que “criamos business plans”. A mensagem correta é: criamos a estratégia, estruturamos o plano vivo, implantamos agentes personalizados e acompanhamos a execução para aumentar a chance de sucesso."
    )


def _entrepreneur_pain_answer(normalized: str) -> str:
    needs = _needs_for_message(normalized)
    agents = _agents_for_needs(needs)
    needs_text = "\n".join(f"- {item}" for item in (needs or ["Estratégia do negócio", "Operação e execução", "Tecnologia e agentes personalizados"]))
    agents_text = "\n".join(f"- {item}" for item in agents)

    return _join_with_cta(
        "Entendi a dor. Eu olharia isso primeiro como problema de gestão, não como simples pedido de ferramenta.\n\n"
        "Escopo inicial:\n\n"
        "1. Dor identificada\n"
        "A empresa precisa transformar informação dispersa, rotina manual ou decisão intuitiva em um processo mais claro, mensurável e acompanhável.\n\n"
        "2. Áreas que entram no diagnóstico\n"
        f"{needs_text}\n\n"
        "3. Agentes personalizados recomendados\n"
        f"{agents_text}\n\n"
        "4. Dados e processos que precisaríamos mapear\n"
        "- Como a empresa vende hoje.\n"
        "- Como controla financeiro, custos e margem.\n"
        "- Quais tarefas são repetitivas ou dependem demais de pessoas-chave.\n"
        "- Quais indicadores precisam aparecer diariamente.\n"
        "- Onde um agente poderia reduzir retrabalho, esquecimento ou perda de oportunidade.\n\n"
        "5. Implantação e acompanhamento\n"
        "A equipe consultiva premium pode mapear a operação, implantar os primeiros agentes e acompanhar a evolução dos indicadores para garantir que a solução gere resultado prático."
    )


def _generic_product_answer(normalized: str) -> str:
    needs = _needs_for_message(normalized)
    agents = _agents_for_needs(needs)
    needs_text = "\n".join(f"- {item}" for item in (needs or ["Estratégia do negócio", "Produto ou serviço principal", "Modelo de receita", "Operação e execução", "Tecnologia e agentes personalizados"]))
    agents_text = "\n".join(f"- {item}" for item in agents)

    return _join_with_cta(
        "Entendi. Esse é o tipo de demanda que o ORKIO deve transformar em escopo real, não em resposta genérica.\n\n"
        "Escopo inicial recomendado:\n\n"
        "1. Oportunidade identificada\n"
        "Organizar a ideia em um projeto claro: problema, público, proposta de valor, modelo de receita, operação e tecnologia necessária.\n\n"
        "2. Áreas que entram no diagnóstico\n"
        f"{needs_text}\n\n"
        "3. Agentes personalizados recomendados\n"
        f"{agents_text}\n\n"
        "4. Dados mínimos para avançar\n"
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
        "- Quando fizer sentido, a equipe também pode executar a construção do app, plataforma ou automações.\n"
        "- Após a implantação, a equipe consultiva premium acompanha evolução, indicadores e ajustes para aumentar a chance de sucesso."
    )


def _build_scope_answer(message: Any, normalized: str) -> str:
    intent = _classify_public_intent(normalized)
    if intent == "site_access":
        return _site_access_answer()
    if intent == "methodology_positioning":
        return _methodology_answer(normalized)
    if intent == "business_plan_project":
        return _business_plan_answer(normalized)
    if intent == "startup_studio_thesis":
        return _startup_studio_answer(normalized)
    if intent == "entrepreneur_pain":
        return _entrepreneur_pain_answer(normalized)
    return _generic_product_answer(normalized)


def build_public_orkio_policy_decision(
    message: Any,
    *,
    visible_agent: Any = None,
    target_agent_slug: Any = None,
    dest_mode: Any = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_public_orkio_policy_enabled():
        return {"handled": False, "reason": "public_orkio_policy_disabled"}

    normalized = normalize_text(message)

    if not normalized:
        return {"handled": False, "reason": "empty"}

    if _is_factual_seed_or_direct_answer_constraint(normalized):
        return {"handled": False, "reason": "factual_seed_or_direct_answer_constraint"}

    if _has_explicit_specialist_mention(normalized):
        return {"handled": False, "reason": "explicit_specialist_mention"}

    if _has_hard_technical_intent(normalized):
        return {"handled": False, "reason": "hard_technical_intent"}

    site_question = _is_site_access_question(normalized)
    product_intent = _has_product_ceo_intent(normalized)
    orkio_or_team = _explicit_orkio_or_team(normalized, visible_agent=visible_agent, target_agent_slug=target_agent_slug)

    if not site_question and not product_intent:
        return {"handled": False, "reason": "no_public_product_intent"}

    if not orkio_or_team:
        visible = normalize_text(visible_agent)
        target = normalize_text(target_agent_slug)
        if visible in {"chris", "cris", "orion"} or target in {"chris", "cris", "orion"}:
            return {"handled": False, "reason": "visible_specialist_target"}

    answer = _build_scope_answer(message, normalized)
    public_intent = _classify_public_intent(normalized)
    reason = "site_access_limitation" if public_intent == "site_access" else f"public_product_ceo_{public_intent}"

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
                "policy_version": ORKIO_POLICY_VERSION,
                "public_intent": public_intent,
                "consultive_success_enabled": is_consultive_success_enabled(),
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
    if not is_public_orkio_policy_enabled():
        return str(system_prompt or "").strip()

    base = str(system_prompt or "").strip()
    names = [str(agent_name or "").strip().lower(), str(final_speaker or "").strip().lower()]
    is_orkio = any(name in {"orkio", "@orkio", "orkio (ceo)"} for name in names)

    if not is_orkio:
        return base

    if "ORKIO_PUBLIC_CEO_MODE" in base:
        return base

    return (base + "\n\n" + ORKIO_CEO_SCOPE_OVERLAY).strip() if base else ORKIO_CEO_SCOPE_OVERLAY
