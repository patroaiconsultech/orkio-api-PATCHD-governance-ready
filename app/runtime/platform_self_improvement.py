from __future__ import annotations

from typing import Any, Dict, List

from .orion_technical_squad import get_technical_specialists, render_specialist_roster


PLATFORM_SELF_IMPROVEMENT_VERSION = "AO50_PLATFORM_SELF_IMPROVEMENT_V1"


IMPROVEMENT_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "P0-RUNTIME-001",
        "priority": "P0",
        "layer": "runtime/intent",
        "title": "Consolidar matriz de roteamento e precedência",
        "symptom": "Fast-paths e policies ainda podem competir por @mention, conversa comum, auditoria, GitHub e modo público.",
        "validated_fact": "A estabilização recente melhorou Orkio, Chris e Orion, mas a governança de precedência ainda está espalhada.",
        "probable_root_cause": "Regras de agente, intenção, capability e fallback ainda vivem em múltiplos blocos do main.py e módulos auxiliares.",
        "minimum_patch": "Criar routing_contract.py com decisão única: requested_agent, final_speaker, route_family, capability_required e routing_locked.",
        "premium_patch": "Criar Router Kernel com matriz declarativa, testes unitários por intenção e relatório de decisão por turno.",
        "rollback": "Manter hook antigo e desativar o routing_contract por feature flag.",
        "validation": [
            "@Chris não pode ser respondido por Orion",
            "@Orion memória factual não vira auditoria",
            "GitHub readonly não captura pergunta comum",
            "Orkio público continua host",
        ],
        "specialists": ["Orion Router/Intent", "Orion Runtime/SSE", "Orion QA/Release"],
    },
    {
        "id": "P0-MAIN-002",
        "priority": "P0",
        "layer": "backend",
        "title": "Desinchar app/main.py por extração incremental",
        "symptom": "Cada patch no main.py aumenta risco de regressão transversal.",
        "validated_fact": "A extração de policies do Orkio, Chris e Orion reduziu risco e acelerou correção.",
        "probable_root_cause": "main.py acumula roteamento, stream, persistence, policies, fallbacks, GitHub, auditoria e terminal guard.",
        "minimum_patch": "Congelar lógica nova no main.py e mover novas decisões para módulos em app/runtime.",
        "premium_patch": "Extrair routing_contract.py, capability_policy.py, stream_outcome.py e agent_registry.py em fases.",
        "rollback": "Imports e hooks pequenos podem ser removidos sem apagar módulos.",
        "validation": [
            "py_compile app/main.py",
            "chat real Orkio/Chris/Orion",
            "GitHub readonly",
            "auditoria readonly",
        ],
        "specialists": ["Orion Backend", "Orion Router/Intent", "Orion QA/Release"],
    },
    {
        "id": "P1-STREAM-003",
        "priority": "P1",
        "layer": "stream/SSE",
        "title": "Padronizar contrato terminal de stream",
        "symptom": "Timeouts e terminal guard ainda podem aparecer quando o runtime principal não encerra de forma previsível.",
        "validated_fact": "Fluxos atuais encerraram com segurança, mas a arquitetura ainda depende de múltiplos caminhos de done/error/fallback.",
        "probable_root_cause": "SSE, fallback e terminal guard não estão centralizados em um stream_outcome único.",
        "minimum_patch": "Criar helper de emissão final padronizada para done/error com runtime_hints consistentes.",
        "premium_patch": "Criar stream_outcome.py com contrato único para todos os fast-paths e runtime principal.",
        "rollback": "Manter emissores atuais e desativar helper por rota.",
        "validation": [
            "pergunta simples não cai em AO46C",
            "erro recuperável libera input",
            "done sempre emitido",
            "Ver execução sem objeto bruto",
        ],
        "specialists": ["Orion Runtime/SSE", "Orion Frontend", "Orion QA/Release"],
    },
    {
        "id": "P1-FRONTEND-004",
        "priority": "P1",
        "layer": "frontend/UX",
        "title": "Extrair AppConsole em componentes e hooks",
        "symptom": "AppConsole.jsx concentra chat, stream, trace, voz, auth, CTA, renderização e navegação.",
        "validated_fact": "Correções de [object Object] e WhatsApp CTA exigiram cuidado alto por tamanho do arquivo.",
        "probable_root_cause": "Estado e renderização de múltiplas responsabilidades estão acoplados no mesmo componente.",
        "minimum_patch": "Extrair ExecutionTracePanel e utilitários de safe text sem mudar comportamento.",
        "premium_patch": "Criar useChatStream, useExecutionTrace, ChatMessage, ChatComposer e WhatsAppCtaCard.",
        "rollback": "Manter AppConsole original e reverter import do componente extraído.",
        "validation": [
            "npm run build",
            "chat responde",
            "Ver execução abre",
            "WhatsApp CTA funciona",
        ],
        "specialists": ["Orion Frontend", "Orion QA/Release"],
    },
    {
        "id": "P1-GOV-005",
        "priority": "P1",
        "layer": "governance/security",
        "title": "Separar conversa, auditoria readonly e execução governada",
        "symptom": "A plataforma precisa auto reconhecer melhorias sem executar alterações indevidas.",
        "validated_fact": "GitHub readonly e auditoria readonly foram preservados nos testes recentes.",
        "probable_root_cause": "Autoavaliação, proposal, patch e execução ainda precisam de contratos mais explícitos.",
        "minimum_patch": "Criar capability_policy.py para determinar readonly, proposal_only, approved_apply e write_allowed.",
        "premium_patch": "Criar governança end-to-end com issue_map, patch_plan, dry-run, aprovação e execução rastreada.",
        "rollback": "Desativar capability_policy e manter rails antigos.",
        "validation": [
            "write_executed=false em readonly",
            "proposal_created=false quando usuário pede só diagnóstico",
            "GitHub token não aparece",
            "rollback documentado",
        ],
        "specialists": ["Orion Security", "Orion Backend", "Orion DevOps/SRE"],
    },
    {
        "id": "P2-DATA-006",
        "priority": "P2",
        "layer": "storage/contexto",
        "title": "Fortalecer memória factual e histórico de thread",
        "symptom": "Memória factual funciona, mas precisa virar contrato explícito com testes por thread.",
        "validated_fact": "Orion recuperou EFATAH777 e Daniel após os patches recentes.",
        "probable_root_cause": "Seed factual, memória de thread e policy pública ainda dependem de guards manuais.",
        "minimum_patch": "Criar testes de memória factual e bypass padrão para seed/direct-answer em todas as policies.",
        "premium_patch": "Criar memory_contract.py com leitura, escrita e recuperação auditáveis por thread.",
        "rollback": "Desativar memory_contract e manter mecanismo atual.",
        "validation": [
            "palavra-chave recuperada",
            "nome recuperado",
            "empresa recuperada",
            "seed responde apenas OK",
        ],
        "specialists": ["Orion Data/DB", "Orion Router/Intent", "Orion QA/Release"],
    },
    {
        "id": "P2-VOICE-007",
        "priority": "P2",
        "layer": "voz/avatar",
        "title": "Provar ponte Realtime → Orquestração → TTS",
        "symptom": "Voz/realtime precisa provar que pedidos técnicos seguem o mesmo pipeline do chat texto.",
        "validated_fact": "Auditorias anteriores apontaram necessidade de Realtime Orchestration Bridge.",
        "probable_root_cause": "Transcrição final e resposta falada podem não passar pelos mesmos contracts do chat texto.",
        "minimum_patch": "Mapear transcript.final para rota de chat com route_family preservado.",
        "premium_patch": "Criar realtime_orchestration_bridge.py com telemetria e fallback texto.",
        "rollback": "Manter voz em modo texto/assistente sem acionar orquestração técnica.",
        "validation": [
            "voz curta responde",
            "voz técnica aciona Orion quando devido",
            "fallback texto funciona",
            "TTS toca resposta final",
        ],
        "specialists": ["Orion Realtime/Voice", "Orion Runtime/SSE", "Orion QA/Release"],
    },
]


def get_improvement_items() -> List[Dict[str, Any]]:
    return [dict(item) for item in IMPROVEMENT_ITEMS]


def render_platform_improvement_diagnosis() -> str:
    lines = [
        "Orion — diagnóstico técnico de melhoria da plataforma",
        "",
        "A plataforma já avançou em Orkio, Chris, Orion, CTA WhatsApp, memória factual, GitHub readonly e auditoria readonly. O próximo salto é transformar esse avanço em arquitetura mais previsível, modular e governada.",
        "",
        "Mapa por prioridade:",
        "",
    ]

    for item in IMPROVEMENT_ITEMS:
        lines.append(f"{item['priority']} — {item['title']}")
        lines.append(f"- Camada: {item['layer']}")
        lines.append(f"- Sintoma: {item['symptom']}")
        lines.append(f"- Causa provável: {item['probable_root_cause']}")
        lines.append(f"- Patch mínimo: {item['minimum_patch']}")
        lines.append(f"- Especialistas: {', '.join(item['specialists'])}")
        lines.append("")

    lines.extend([
        "Veredito técnico:",
        "- Verde: a base modular começou certo com policies externas.",
        "- Amarelo: roteamento, stream e AppConsole ainda precisam extração incremental.",
        "- Vermelho: não permitir autoexecução sem aprovação humana.",
        "",
        "Próximo passo correto:",
        "Começar por routing_contract.py e continuar reduzindo app/main.py sem refatoração big bang.",
    ])

    return "\n".join(lines).strip()


def render_priority_plan() -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in IMPROVEMENT_ITEMS:
        grouped.setdefault(item["priority"], []).append(item)

    lines = [
        "Orion — plano de melhoria por prioridade",
        "",
        "Critério: restaurar e proteger funcionamento útil antes de expansão. Nada aqui implica escrita automática, branch, commit ou deploy.",
        "",
    ]

    for priority in ["P0", "P1", "P2"]:
        items = grouped.get(priority, [])
        if not items:
            continue

        title = {
            "P0": "P0 — reduzir risco estrutural imediato",
            "P1": "P1 — estabilizar operação e experiência",
            "P2": "P2 — evoluir capacidade e profundidade",
        }.get(priority, priority)

        lines.append(title)
        for item in items:
            lines.append("")
            lines.append(f"{item['id']} — {item['title']}")
            lines.append(f"- Camada: {item['layer']}")
            lines.append(f"- Patch mínimo: {item['minimum_patch']}")
            lines.append(f"- Patch premium: {item['premium_patch']}")
            lines.append(f"- Rollback: {item['rollback']}")
            lines.append("- Testes:")
            for test in item.get("validation", []):
                lines.append(f"  - {test}")
        lines.append("")

    lines.extend([
        "Ordem segura recomendada:",
        "1. routing_contract.py",
        "2. stream_outcome.py",
        "3. ExecutionTracePanel/useExecutionTrace no frontend",
        "4. capability_policy.py",
        "5. memory_contract.py",
        "6. realtime_orchestration_bridge.py",
    ])

    return "\n".join(lines).strip()


def render_specialist_assignment() -> str:
    return render_specialist_roster()
