from __future__ import annotations

from typing import Any, Dict, List


CHRIS_BUSINESS_SQUAD_VERSION = "AO52_CHRIS_BUSINESS_SQUAD_V1"


BUSINESS_SPECIALISTS: List[Dict[str, Any]] = [
    {
        "slug": "chris_business_plan",
        "name": "Chris Business Plan",
        "layer": "business_plan",
        "mission": "Transformar visão, tese, mercado, oferta, receita e execução em Business Plan vivo.",
        "signals": [
            "plano espalhado em conversas e documentos",
            "falta de sumário executivo claro",
            "dificuldade de explicar modelo de negócio",
            "ausência de versão para investidores",
        ],
        "outputs": [
            "estrutura do Business Plan Vivo",
            "blocos de decisão",
            "versão investidor/cliente/interna",
            "roadmap de evolução do plano",
        ],
    },
    {
        "slug": "chris_cfo",
        "name": "Chris CFO",
        "layer": "financeiro",
        "mission": "Traduzir estratégia em modelo financeiro, caixa, margem, cenários, valuation e indicadores.",
        "signals": [
            "preço indefinido",
            "margem pouco clara",
            "ausência de projeções",
            "captação sem tese financeira",
        ],
        "outputs": [
            "modelo de receita",
            "projeções e cenários",
            "unit economics",
            "indicadores financeiros para decisão",
        ],
    },
    {
        "slug": "chris_growth",
        "name": "Chris Growth",
        "layer": "growth",
        "mission": "Organizar aquisição, posicionamento, canais, funil e crescimento sustentável.",
        "signals": [
            "proposta de valor pouco clara",
            "lead não qualificado",
            "canal de aquisição indefinido",
            "baixa conversão",
        ],
        "outputs": [
            "estratégia de aquisição",
            "canais prioritários",
            "experimentos de growth",
            "métricas de tração",
        ],
    },
    {
        "slug": "chris_sales",
        "name": "Chris Sales",
        "layer": "vendas",
        "mission": "Estruturar processo comercial, CRM, abordagem, follow-up, propostas e conversão.",
        "signals": [
            "vendas dependem do fundador",
            "follow-up manual",
            "propostas sem padrão",
            "pipeline sem previsibilidade",
        ],
        "outputs": [
            "playbook comercial",
            "critérios de qualificação",
            "roteiro de venda consultiva",
            "agentes comerciais recomendados",
        ],
    },
    {
        "slug": "chris_marketing",
        "name": "Chris Marketing",
        "layer": "marketing",
        "mission": "Fortalecer marca, narrativa, conteúdo, diferenciação, prova de autoridade e demanda.",
        "signals": [
            "narrativa genérica",
            "diferencial pouco defendido",
            "conteúdo sem tese",
            "marca não transmite valor premium",
        ],
        "outputs": [
            "posicionamento",
            "mensagens-chave",
            "pilares de conteúdo",
            "argumentos de diferenciação",
        ],
    },
    {
        "slug": "chris_investor",
        "name": "Chris Investor",
        "layer": "investidores",
        "mission": "Preparar tese, pitch, narrativa de mercado, riscos controláveis, tração e próximos marcos.",
        "signals": [
            "pitch sem clareza",
            "risco mal explicado",
            "mercado não dimensionado",
            "roadmap sem milestones",
        ],
        "outputs": [
            "tese investidor-ready",
            "estrutura de pitch",
            "mapa de riscos e mitigação",
            "marcos para captação",
        ],
    },
    {
        "slug": "chris_operations",
        "name": "Chris Operations",
        "layer": "operações",
        "mission": "Transformar rotinas, processos, atendimento e execução em operação acompanhável.",
        "signals": [
            "retrabalho",
            "processo manual",
            "tarefas dependem de pessoas-chave",
            "sem indicadores operacionais",
        ],
        "outputs": [
            "mapa de processos",
            "oportunidades de automação",
            "agentes operacionais",
            "rotina de acompanhamento",
        ],
    },
    {
        "slug": "chris_customer_success",
        "name": "Chris Customer Success",
        "layer": "customer_success",
        "mission": "Garantir implantação, acompanhamento, sucesso do cliente, evolução e retenção.",
        "signals": [
            "cliente não sabe próximo passo",
            "implantação sem métrica",
            "valor percebido demora",
            "ausência de rotina de sucesso",
        ],
        "outputs": [
            "plano de implantação",
            "rituais de acompanhamento",
            "indicadores de sucesso",
            "roadmap de evolução por cliente",
        ],
    },
    {
        "slug": "chris_pricing",
        "name": "Chris Pricing",
        "layer": "pricing",
        "mission": "Definir pacotes, preço, setup, recorrência, enterprise e valor percebido.",
        "signals": [
            "ticket indefinido",
            "escopo customizado demais",
            "baixo valor percebido",
            "preço não captura complexidade",
        ],
        "outputs": [
            "pacotes comerciais",
            "modelo de preço",
            "critérios de escopo",
            "matriz de valor",
        ],
    },
    {
        "slug": "chris_partnerships",
        "name": "Chris Partnerships",
        "layer": "parcerias",
        "mission": "Mapear canais, alianças, parceiros estratégicos, co-criação e distribuição.",
        "signals": [
            "crescimento só por venda direta",
            "falta de canais",
            "parcerias sem tese",
            "baixa escala comercial",
        ],
        "outputs": [
            "mapa de parceiros",
            "tese de parceria",
            "modelo de colaboração",
            "canais de distribuição",
        ],
    },
]


def get_business_specialists() -> List[Dict[str, Any]]:
    return [dict(item) for item in BUSINESS_SPECIALISTS]


def render_business_specialist_roster() -> str:
    lines = [
        "Chris — squad executivo recomendado",
        "",
        "Para evoluir a PatroAI/ORKIO como negócio premium, eu organizaria a atuação da Chris em especialistas por eixo de decisão:",
        "",
    ]

    for idx, specialist in enumerate(BUSINESS_SPECIALISTS, start=1):
        lines.append(f"{idx}. {specialist['name']}")
        lines.append(f"- Camada: {specialist['layer']}")
        lines.append(f"- Missão: {specialist['mission']}")
        signals = "; ".join(specialist.get("signals", [])[:3])
        if signals:
            lines.append(f"- Sinais que observa: {signals}.")
        lines.append("")

    lines.extend([
        "Governança:",
        "- Esses especialistas são eixos de análise executiva, não execução automática.",
        "- Cada achado deve virar hipótese de negócio, ação mínima, indicador de sucesso e responsável.",
        "- Implantação, automação, proposta ou compromisso comercial real continuam dependendo de validação humana.",
    ])

    return "\n".join(lines).strip()
