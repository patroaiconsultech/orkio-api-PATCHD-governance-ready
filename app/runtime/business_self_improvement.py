from __future__ import annotations

from typing import Any, Dict, List

from .chris_business_squad import render_business_specialist_roster


BUSINESS_SELF_IMPROVEMENT_VERSION = "AO53_BUSINESS_SELF_IMPROVEMENT_V1"


BUSINESS_IMPROVEMENT_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "BIZ-P0-001",
        "priority": "P0",
        "layer": "business_plan",
        "title": "Transformar o Business Plan em objeto central da plataforma",
        "symptom": "A visão estratégica existe, mas ainda fica espalhada em conversas, arquivos e respostas dos agentes.",
        "validated_fact": "O Business Plan Vivo foi identificado como módulo central para a PatroAI Consultech.",
        "probable_root_cause": "O plano ainda não tem tela, estado, versão, rotina de revisão e experiência própria dentro da plataforma.",
        "minimum_action": "Criar página estática premium de Business Plan Vivo com sumário executivo, verticais, modelo de receita, ESG, integrações, sucessão, roadmap e versão investidor.",
        "premium_action": "Transformar a página em módulo editável com versões, comentários, geração assistida, exportação PDF/DOCX e modos interno/cliente/investidor.",
        "success_metric": "Usuário consegue entender a tese da PatroAI em menos de 5 minutos e identificar próximos passos.",
        "owner_specialists": ["Chris Business Plan", "Chris Investor", "Chris Customer Success"],
    },
    {
        "id": "BIZ-P0-002",
        "priority": "P0",
        "layer": "positioning",
        "title": "Consolidar narrativa premium da metodologia PatroAI/ORKIO",
        "symptom": "A metodologia é forte, mas precisa ser descrita de forma defensável, proprietária e comercialmente clara.",
        "validated_fact": "A formulação segura é metodologia proprietária, consultiva e altamente diferenciada, sem afirmar exclusividade absoluta sem pesquisa formal.",
        "probable_root_cause": "Diferenciais técnicos, consultivos e estratégicos ainda não estão condensados em mensagem única de mercado.",
        "minimum_action": "Criar bloco de posicionamento: Business Plan vivo + agentes personalizados + execução tecnológica + governança + acompanhamento consultivo premium.",
        "premium_action": "Criar narrativa por público: empreendedor, empresa consolidada, investidor, parceiro e vertical setorial.",
        "success_metric": "A proposta de valor pode ser explicada em uma frase, um parágrafo e uma página.",
        "owner_specialists": ["Chris Marketing", "Chris Investor", "Chris Growth"],
    },
    {
        "id": "BIZ-P1-003",
        "priority": "P1",
        "layer": "revenue_model",
        "title": "Estruturar pacotes comerciais e modelo de receita",
        "symptom": "A plataforma pode monetizar por setup, assinatura, agentes, projetos, integrações e participação, mas precisa de empacotamento claro.",
        "validated_fact": "O modelo de receita proposto inclui SaaS, setup, consultoria, agentes personalizados, royalties, participação em startups e integrações.",
        "probable_root_cause": "A oferta ainda está mais rica conceitualmente do que empacotada comercialmente.",
        "minimum_action": "Criar três pacotes: Diagnóstico Executivo, Implantação Inicial e Plataforma/Agentes Premium.",
        "premium_action": "Criar pricing calculator por complexidade, número de agentes, integrações, acompanhamento e nível de governança.",
        "success_metric": "Lead entende rapidamente o que comprar, por onde começar e o que acontece depois.",
        "owner_specialists": ["Chris Pricing", "Chris Sales", "Chris CFO"],
    },
    {
        "id": "BIZ-P1-004",
        "priority": "P1",
        "layer": "go_to_market",
        "title": "Definir go-to-market consultivo",
        "symptom": "A plataforma tem potencial de venda consultiva, mas precisa de funil, qualificação, script e prova de valor.",
        "validated_fact": "A oferta mais forte é diagnóstico executivo + escopo de agentes + implantação acompanhada.",
        "probable_root_cause": "Sem playbook, a venda depende demais da explicação do fundador.",
        "minimum_action": "Criar funil: dor → diagnóstico → escopo → proposta → implantação → acompanhamento.",
        "premium_action": "Criar agentes de CRM, follow-up, proposta, qualificação e customer success integrados ao funil.",
        "success_metric": "Cada oportunidade tem estágio, próxima ação, valor estimado e critério de avanço.",
        "owner_specialists": ["Chris Sales", "Chris Growth", "Chris Customer Success"],
    },
    {
        "id": "BIZ-P1-005",
        "priority": "P1",
        "layer": "verticals",
        "title": "Organizar verticais PatroAI como portfólio vivo",
        "symptom": "Orkio, Arquitech, Fintegra Capital e Business Plan Vivo aparecem como ideias fortes, mas precisam virar portfólio compreensível.",
        "validated_fact": "As verticais iniciais já foram nomeadas e descritas conceitualmente.",
        "probable_root_cause": "Ainda falta estrutura visual e estratégica de holding/portfólio.",
        "minimum_action": "Criar seção de verticais com problema, público, solução, monetização e status.",
        "premium_action": "Criar dashboard de portfólio com maturidade, roadmap, próximos marcos e necessidades por vertical.",
        "success_metric": "Investidor ou parceiro entende a lógica da holding e a relação entre as verticais.",
        "owner_specialists": ["Chris Business Plan", "Chris Investor", "Chris Operations"],
    },
    {
        "id": "BIZ-P2-006",
        "priority": "P2",
        "layer": "esg_succession",
        "title": "Transformar ESG, sucessão e continuidade em seção estratégica",
        "symptom": "ESG e sucessão são diferenciais relevantes, mas ainda podem parecer discurso se não virarem critérios de decisão.",
        "validated_fact": "A proposta ESG inclui redução de desperdício, preservação de conhecimento, transparência, governança e continuidade.",
        "probable_root_cause": "O impacto ainda não está conectado a indicadores, exemplos e casos de uso.",
        "minimum_action": "Criar seção ESG & Continuidade no Business Plan Vivo.",
        "premium_action": "Criar indicadores de impacto por projeto: retrabalho reduzido, conhecimento preservado, processos documentados e decisões rastreáveis.",
        "success_metric": "Cliente entende como IA, governança e continuidade geram valor além de produtividade.",
        "owner_specialists": ["Chris Operations", "Chris Investor", "Chris Customer Success"],
    },
    {
        "id": "BIZ-P2-007",
        "priority": "P2",
        "layer": "customer_success",
        "title": "Criar metodologia de implantação e acompanhamento",
        "symptom": "A promessa de equipe consultiva premium precisa virar processo visível de sucesso do cliente.",
        "validated_fact": "A estratégia atual inclui implantação acompanhada, governança e foco no sucesso do projeto.",
        "probable_root_cause": "A experiência pós-venda ainda não está formalizada em etapas, rituais e indicadores.",
        "minimum_action": "Criar jornada de implantação: descoberta, escopo, agentes, piloto, indicadores, evolução.",
        "premium_action": "Criar dashboard de sucesso por cliente com milestones, agentes implantados, ROI e próximos passos.",
        "success_metric": "Cliente sabe o que será implantado, quando, por quem e como o sucesso será medido.",
        "owner_specialists": ["Chris Customer Success", "Chris Operations", "Chris CFO"],
    },
]


def render_business_improvement_diagnosis() -> str:
    lines = [
        "Chris — diagnóstico de evolução de negócio",
        "",
        "A PatroAI/ORKIO já tem uma base narrativa forte: Business Plan vivo, agentes personalizados, execução tecnológica, governança e equipe consultiva premium. O próximo passo é transformar isso em produto, oferta e processo comercial repetível.",
        "",
        "Mapa por prioridade:",
        "",
    ]

    for item in BUSINESS_IMPROVEMENT_ITEMS:
        lines.append(f"{item['priority']} — {item['title']}")
        lines.append(f"- Camada: {item['layer']}")
        lines.append(f"- Sintoma: {item['symptom']}")
        lines.append(f"- Causa provável: {item['probable_root_cause']}")
        lines.append(f"- Ação mínima: {item['minimum_action']}")
        lines.append(f"- Especialistas: {', '.join(item['owner_specialists'])}")
        lines.append("")

    lines.extend([
        "Veredito executivo:",
        "- Verde: a tese está clara e já pode virar experiência premium dentro da plataforma.",
        "- Amarelo: a oferta precisa ser empacotada para venda consultiva.",
        "- Vermelho: não deixar Business Plan, verticais e proposta de valor espalhados apenas em conversas.",
        "",
        "Próximo passo correto:",
        "Criar primeiro o módulo Business Plan Vivo como página premium, depois evoluir para edição, versionamento, exportação e modos de leitura.",
    ])

    return "\n".join(lines).strip()


def render_business_priority_plan() -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in BUSINESS_IMPROVEMENT_ITEMS:
        grouped.setdefault(item["priority"], []).append(item)

    lines = [
        "Chris — plano de evolução de negócio por prioridade",
        "",
        "Critério: transformar a visão estratégica em produto vendável, implantável e acompanhável. Nada aqui implica proposta comercial automática ou compromisso sem validação humana.",
        "",
    ]

    for priority in ["P0", "P1", "P2"]:
        items = grouped.get(priority, [])
        if not items:
            continue

        title = {
            "P0": "P0 — consolidar narrativa e objeto central",
            "P1": "P1 — empacotar oferta e acelerar venda consultiva",
            "P2": "P2 — aprofundar diferenciais e sucesso do cliente",
        }.get(priority, priority)

        lines.append(title)
        for item in items:
            lines.append("")
            lines.append(f"{item['id']} — {item['title']}")
            lines.append(f"- Camada: {item['layer']}")
            lines.append(f"- Ação mínima: {item['minimum_action']}")
            lines.append(f"- Evolução premium: {item['premium_action']}")
            lines.append(f"- Métrica de sucesso: {item['success_metric']}")
            lines.append(f"- Especialistas: {', '.join(item['owner_specialists'])}")
        lines.append("")

    lines.extend([
        "Ordem segura recomendada:",
        "1. Página Business Plan Vivo estática premium.",
        "2. Estrutura de verticais da holding.",
        "3. Pacotes comerciais e pricing inicial.",
        "4. Funil consultivo e playbook de vendas.",
        "5. Módulo editável com versões e exportação.",
        "6. Dashboard de sucesso e acompanhamento por cliente.",
    ])

    return "\n".join(lines).strip()


def render_business_plan_vivo_brief() -> str:
    return """Chris — Business Plan Vivo da PatroAI Consultech

Eu trataria o Business Plan Vivo como o primeiro módulo executivo premium dentro da plataforma, porque ele transforma a tese da PatroAI em objeto visível, navegável e evolutivo.

Estrutura recomendada para a página V1:

1. Resumo Executivo
A PatroAI Consultech como holding de tecnologia, IA e estruturação de negócios digitais.

2. Estrutura da Holding
Como Orkio, Arquitech, Fintegra Capital e Business Plan Vivo se conectam.

3. Verticais
Problema, público, solução, monetização e status de cada vertical.

4. Modelo de Receita
SaaS, setup, consultoria, agentes personalizados, integrações, royalties, participação e projetos sob medida.

5. ESG & Impacto
Eficiência, redução de desperdício, preservação de conhecimento, governança e continuidade.

6. Integrações & Dados
Aproveitamento de sistemas existentes, dados internos, automações e inteligência operacional.

7. Sucessão & Continuidade
Preservação de processos, conhecimento tácito, documentação e rotina de gestão.

8. Roadmap
Marcos de produto, validação, implantação, verticais, equipe e go-to-market.

9. Versão para Investidores
Tese, mercado, modelo, tração, riscos controláveis, milestones e necessidade de capital.

Patch mínimo:
Criar uma página estática premium primeiro.

Patch premium:
Transformar depois em módulo editável com versões, comentários, geração assistida, exportação PDF/DOCX e modos interno/cliente/investidor."""


def render_business_specialist_assignment() -> str:
    return render_business_specialist_roster()
