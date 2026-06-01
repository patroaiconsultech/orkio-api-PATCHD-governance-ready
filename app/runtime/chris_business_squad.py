from __future__ import annotations
from typing import Any, Dict, List

CHRIS_BUSINESS_SQUAD_VERSION = "AO54_CHRIS_BUSINESS_SQUAD_NO_CYCLE"

BUSINESS_SPECIALISTS: List[Dict[str, Any]] = [
    {"name": "Chris Business Plan", "layer": "business_plan", "mission": "Transformar visão, tese, mercado, oferta, receita e execução em Business Plan vivo."},
    {"name": "Chris CFO", "layer": "financeiro", "mission": "Traduzir estratégia em modelo financeiro, caixa, margem, cenários, valuation e indicadores."},
    {"name": "Chris Growth", "layer": "growth", "mission": "Organizar aquisição, posicionamento, canais, funil e crescimento sustentável."},
    {"name": "Chris Sales", "layer": "vendas", "mission": "Estruturar processo comercial, CRM, abordagem, follow-up, propostas e conversão."},
    {"name": "Chris Marketing", "layer": "marketing", "mission": "Fortalecer marca, narrativa, conteúdo, diferenciação, prova de autoridade e demanda."},
    {"name": "Chris Investor", "layer": "investidores", "mission": "Preparar tese, pitch, narrativa de mercado, riscos controláveis, tração e próximos marcos."},
    {"name": "Chris Operations", "layer": "operações", "mission": "Transformar rotinas, processos, atendimento e execução em operação acompanhável."},
    {"name": "Chris Customer Success", "layer": "customer_success", "mission": "Garantir implantação, acompanhamento, sucesso do cliente, evolução e retenção."},
    {"name": "Chris Pricing", "layer": "pricing", "mission": "Definir pacotes, preço, setup, recorrência, enterprise e valor percebido."},
    {"name": "Chris Partnerships", "layer": "parcerias", "mission": "Mapear canais, alianças, parceiros estratégicos, co-criação e distribuição."},
]

def get_business_specialists() -> List[Dict[str, Any]]:
    return [dict(item) for item in BUSINESS_SPECIALISTS]

def render_business_specialist_roster() -> str:
    lines = ["Chris — squad executivo recomendado", "", "Para evoluir a PatroAI/ORKIO como negócio premium, eu organizaria a atuação da Chris em especialistas por eixo de decisão:", ""]
    for idx, item in enumerate(BUSINESS_SPECIALISTS, 1):
        lines += [f"{idx}. {item['name']}", f"- Camada: {item['layer']}", f"- Missão: {item['mission']}", ""]
    lines += [
        "Governança:",
        "- Esses especialistas são eixos de análise executiva, não execução automática.",
        "- Cada achado deve virar hipótese de negócio, ação mínima, indicador de sucesso e responsável.",
        "- Implantação, automação, proposta ou compromisso comercial real continuam dependendo de validação humana.",
    ]
    return "\n".join(lines).strip()
