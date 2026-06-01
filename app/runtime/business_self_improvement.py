from __future__ import annotations
from typing import Any, Dict, List

BUSINESS_SELF_IMPROVEMENT_VERSION = "AO54_BUSINESS_SELF_IMPROVEMENT_NO_CYCLE"

ITEMS: List[Dict[str, Any]] = [
    {"id":"BIZ-P0-001","priority":"P0","layer":"business_plan","title":"Transformar o Business Plan em objeto central da plataforma","minimum":"Criar página estática premium de Business Plan Vivo com sumário executivo, verticais, modelo de receita, ESG, integrações, sucessão, roadmap e versão investidor.","premium":"Transformar a página em módulo editável com versões, comentários, geração assistida, exportação PDF/DOCX e modos interno/cliente/investidor.","metric":"Usuário entende a tese da PatroAI em menos de 5 minutos.","specs":["Chris Business Plan","Chris Investor","Chris Customer Success"]},
    {"id":"BIZ-P0-002","priority":"P0","layer":"positioning","title":"Consolidar narrativa premium da metodologia PatroAI/ORKIO","minimum":"Criar bloco de posicionamento: Business Plan vivo + agentes personalizados + execução tecnológica + governança + acompanhamento consultivo premium.","premium":"Criar narrativa por público: empreendedor, empresa consolidada, investidor, parceiro e vertical setorial.","metric":"A proposta de valor pode ser explicada em uma frase, um parágrafo e uma página.","specs":["Chris Marketing","Chris Investor","Chris Growth"]},
    {"id":"BIZ-P1-003","priority":"P1","layer":"revenue_model","title":"Estruturar pacotes comerciais e modelo de receita","minimum":"Criar três pacotes: Diagnóstico Executivo, Implantação Inicial e Plataforma/Agentes Premium.","premium":"Criar pricing calculator por complexidade, número de agentes, integrações, acompanhamento e nível de governança.","metric":"Lead entende rapidamente o que comprar, por onde começar e o que acontece depois.","specs":["Chris Pricing","Chris Sales","Chris CFO"]},
    {"id":"BIZ-P1-004","priority":"P1","layer":"go_to_market","title":"Definir go-to-market consultivo","minimum":"Criar funil: dor → diagnóstico → escopo → proposta → implantação → acompanhamento.","premium":"Criar agentes de CRM, follow-up, proposta, qualificação e customer success integrados ao funil.","metric":"Cada oportunidade tem estágio, próxima ação, valor estimado e critério de avanço.","specs":["Chris Sales","Chris Growth","Chris Customer Success"]},
    {"id":"BIZ-P1-005","priority":"P1","layer":"verticals","title":"Organizar verticais PatroAI como portfólio vivo","minimum":"Criar seção de verticais com problema, público, solução, monetização e status.","premium":"Criar dashboard de portfólio com maturidade, roadmap, próximos marcos e necessidades por vertical.","metric":"Investidor ou parceiro entende a lógica da holding e a relação entre as verticais.","specs":["Chris Business Plan","Chris Investor","Chris Operations"]},
    {"id":"BIZ-P2-006","priority":"P2","layer":"customer_success","title":"Criar metodologia de implantação e acompanhamento","minimum":"Criar jornada de implantação: descoberta, escopo, agentes, piloto, indicadores, evolução.","premium":"Criar dashboard de sucesso por cliente com milestones, agentes implantados, ROI e próximos passos.","metric":"Cliente sabe o que será implantado, quando, por quem e como o sucesso será medido.","specs":["Chris Customer Success","Chris Operations","Chris CFO"]},
]

def render_business_improvement_diagnosis() -> str:
    lines = ["Chris — diagnóstico de evolução de negócio", "", "A PatroAI/ORKIO já tem uma base narrativa forte: Business Plan vivo, agentes personalizados, execução tecnológica, governança e equipe consultiva premium. O próximo passo é transformar isso em produto, oferta e processo comercial repetível.", "", "Mapa por prioridade:", ""]
    for item in ITEMS:
        lines += [f"{item['priority']} — {item['title']}", f"- Camada: {item['layer']}", f"- Ação mínima: {item['minimum']}", f"- Especialistas: {', '.join(item['specs'])}", ""]
    lines += ["Veredito executivo:", "- Verde: a tese está clara e já pode virar experiência premium dentro da plataforma.", "- Amarelo: a oferta precisa ser empacotada para venda consultiva.", "- Vermelho: não deixar Business Plan, verticais e proposta de valor espalhados apenas em conversas.", "", "Próximo passo correto: criar primeiro o módulo Business Plan Vivo como página premium."]
    return "\n".join(lines).strip()

def render_business_priority_plan() -> str:
    lines = ["Chris — plano de evolução de negócio por prioridade", "", "Critério: transformar a visão estratégica em produto vendável, implantável e acompanhável. Nada aqui implica proposta comercial automática ou compromisso sem validação humana.", ""]
    for p, title in [("P0","P0 — consolidar narrativa e objeto central"),("P1","P1 — empacotar oferta e acelerar venda consultiva"),("P2","P2 — aprofundar diferenciais e sucesso do cliente")]:
        group = [i for i in ITEMS if i["priority"] == p]
        if not group: continue
        lines.append(title)
        for item in group:
            lines += ["", f"{item['id']} — {item['title']}", f"- Camada: {item['layer']}", f"- Ação mínima: {item['minimum']}", f"- Evolução premium: {item['premium']}", f"- Métrica de sucesso: {item['metric']}", f"- Especialistas: {', '.join(item['specs'])}"]
        lines.append("")
    lines += ["Ordem segura recomendada:", "1. Página Business Plan Vivo estática premium.", "2. Estrutura de verticais da holding.", "3. Pacotes comerciais e pricing inicial.", "4. Funil consultivo e playbook de vendas.", "5. Módulo editável com versões e exportação.", "6. Dashboard de sucesso e acompanhamento por cliente."]
    return "\n".join(lines).strip()

def render_business_specialist_assignment() -> str:
    return """Chris — squad executivo recomendado

1. Chris Business Plan — Business Plan vivo, tese, mercado, oferta, receita e execução.
2. Chris CFO — modelo financeiro, caixa, margem, valuation, cenários e indicadores.
3. Chris Growth — aquisição, posicionamento, canais, funil e crescimento sustentável.
4. Chris Sales — CRM, abordagem, follow-up, propostas e conversão.
5. Chris Marketing — marca, narrativa, conteúdo, diferenciação e prova de autoridade.
6. Chris Investor — pitch, tese, riscos controláveis, tração e próximos marcos.
7. Chris Operations — processos, rotinas, atendimento e operação acompanhável.
8. Chris Customer Success — implantação, acompanhamento, sucesso, evolução e retenção.
9. Chris Pricing — pacotes, preço, setup, recorrência e valor percebido.
10. Chris Partnerships — canais, alianças, parceiros estratégicos e distribuição.

Governança:
- Esses especialistas são eixos de análise executiva, não execução automática.
- Cada achado deve virar hipótese de negócio, ação mínima, indicador de sucesso e responsável."""

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
