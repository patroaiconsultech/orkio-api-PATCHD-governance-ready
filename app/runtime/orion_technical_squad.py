from __future__ import annotations

from typing import Any, Dict, List


ORION_TECHNICAL_SQUAD_VERSION = "AO49_ORION_TECHNICAL_SQUAD_V1"


TECHNICAL_SPECIALISTS: List[Dict[str, Any]] = [
    {
        "slug": "orion_backend",
        "name": "Orion Backend",
        "layer": "backend",
        "mission": "APIs, rotas, contratos, persistência, handlers e integrações internas.",
        "signals": [
            "endpoint retorna 200 mas usuário não recebe resposta útil",
            "handler errado captura intenção",
            "main.py concentra responsabilidades demais",
            "payload final incompleto para a UI",
        ],
        "outputs": [
            "causa provável por rota/função",
            "patch mínimo por arquivo",
            "rollback por bloco",
            "teste de endpoint e teste real na UI",
        ],
    },
    {
        "slug": "orion_frontend",
        "name": "Orion Frontend",
        "layer": "frontend",
        "mission": "UI, renderização, AppConsole, estados visuais, execução recolhida, links e experiência premium.",
        "signals": [
            "[object Object] na interface",
            "agente exibido diferente do agente final",
            "botão/CTA quebrado",
            "input travado após stream",
        ],
        "outputs": [
            "componente afetado",
            "estado React afetado",
            "patch mínimo visual",
            "teste de build e teste real de clique",
        ],
    },
    {
        "slug": "orion_runtime_sse",
        "name": "Orion Runtime/SSE",
        "layer": "stream/SSE",
        "mission": "Eventos de stream, terminal events, timeout, fallback útil e encerramento seguro.",
        "signals": [
            "terminal guard",
            "stream sem done",
            "timeout em pergunta simples",
            "keepalive sem chunk útil",
            "resposta final não chega na UI",
        ],
        "outputs": [
            "contrato SSE esperado",
            "ponto de encerramento",
            "evento done/error obrigatório",
            "matriz de timeout",
        ],
    },
    {
        "slug": "orion_router_intent",
        "name": "Orion Router/Intent",
        "layer": "runtime/intent",
        "mission": "Roteamento por @mention, intenção, fast-paths, policies e precedência de rails.",
        "signals": [
            "Chris responde por Orkio",
            "Orkio responde por Orion",
            "pergunta comum vira auditoria",
            "GitHub captura pergunta normal",
            "plain conversation vence mention",
        ],
        "outputs": [
            "matriz de precedência",
            "separação entre conversa, auditoria, GitHub e action",
            "teste por agente",
            "risco de regressão por fast-path",
        ],
    },
    {
        "slug": "orion_devops_sre",
        "name": "Orion DevOps/SRE",
        "layer": "deploy/configuração",
        "mission": "Deploy, variáveis, logs, saúde, builds, readiness e observabilidade.",
        "signals": [
            "API sobe mas fluxo não funciona",
            "build passa mas UI quebra",
            "logs normais com severity error",
            "variável de ambiente ausente",
        ],
        "outputs": [
            "checklist pre-deploy",
            "go/no-go",
            "rollback",
            "observabilidade mínima",
        ],
    },
    {
        "slug": "orion_security",
        "name": "Orion Security",
        "layer": "auth/security",
        "mission": "Tokens, permissões, LGPD, exposição de dados, escrita governada e superfícies sensíveis.",
        "signals": [
            "token exposto",
            "write_executed sem aprovação",
            "acesso admin indevido",
            "log sensível na UI",
        ],
        "outputs": [
            "risco de segurança",
            "bloqueio mínimo",
            "governança de permissão",
            "teste de não-escrita",
        ],
    },
    {
        "slug": "orion_data_db",
        "name": "Orion Data/DB",
        "layer": "storage/contexto",
        "mission": "Memória, contexto, schema, migrations, histórico da thread e persistência.",
        "signals": [
            "palavra-chave não recupera",
            "nome do usuário some",
            "thread perde contexto",
            "migration pendente",
        ],
        "outputs": [
            "fonte de contexto",
            "risco de perda de memória",
            "teste factual",
            "rollback de migration",
        ],
    },
    {
        "slug": "orion_realtime_voice",
        "name": "Orion Realtime/Voice",
        "layer": "voz/avatar",
        "mission": "Realtime, STT/TTS, microfone, voz, avatar, transcrição e ponte para chat/orquestração.",
        "signals": [
            "voz não responde",
            "microfone negado",
            "transcript final não vira ação",
            "TTS não toca resposta longa",
        ],
        "outputs": [
            "diagnóstico de voz",
            "fallback texto",
            "ponte realtime/chat",
            "teste de sessão",
        ],
    },
    {
        "slug": "orion_qa_release",
        "name": "Orion QA/Release",
        "layer": "QA/release",
        "mission": "Matriz de regressão, smoke tests, critérios de pronto e validação de fluxo real.",
        "signals": [
            "patch aplicado sem teste real",
            "build passou mas fluxo falhou",
            "regressão em agente secundário",
            "cenário crítico não testado",
        ],
        "outputs": [
            "matriz P0/P1/P2",
            "testes obrigatórios",
            "critério de go/no-go",
            "plano de rollback",
        ],
    },
]


def get_technical_specialists() -> List[Dict[str, Any]]:
    return [dict(item) for item in TECHNICAL_SPECIALISTS]


def render_specialist_roster() -> str:
    lines = [
        "Orion — squad técnico recomendado",
        "",
        "Para a plataforma evoluir com previsibilidade, eu organizaria a atuação técnica em especialistas por camada:",
        "",
    ]

    for idx, specialist in enumerate(TECHNICAL_SPECIALISTS, start=1):
        lines.append(f"{idx}. {specialist['name']}")
        lines.append(f"- Camada: {specialist['layer']}")
        lines.append(f"- Missão: {specialist['mission']}")
        signals = "; ".join(specialist.get("signals", [])[:3])
        if signals:
            lines.append(f"- Sinais que observa: {signals}.")
        lines.append("")

    lines.extend([
        "Governança:",
        "- Esses especialistas são eixos de diagnóstico técnico, não execução automática.",
        "- Cada achado deve virar hipótese, patch mínimo, teste e rollback.",
        "- Escrita, branch, PR ou deploy continuam bloqueados sem aprovação humana.",
    ])

    return "\n".join(lines).strip()


def get_specialists_for_layers(layers: List[str]) -> List[Dict[str, Any]]:
    wanted = {str(layer or "").strip().lower() for layer in layers if str(layer or "").strip()}
    if not wanted:
        return get_technical_specialists()

    selected = []
    for specialist in TECHNICAL_SPECIALISTS:
        layer = str(specialist.get("layer") or "").lower()
        slug = str(specialist.get("slug") or "").lower()
        name = str(specialist.get("name") or "").lower()
        if any(item in layer or item in slug or item in name for item in wanted):
            selected.append(dict(specialist))

    return selected or get_technical_specialists()
