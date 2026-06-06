# ORKIO_AO67A_REALTIME_UNLOCK_JOURNEY
"""Realtime Unlock Journey for public Orkio conversations.

Purpose
-------
Keep Realtime as a stable voice capability while moving the *invitation,
education and gamification* layer to the chat experience.

This module is intentionally stateless, dependency-free and reversible.
It does not start Realtime, does not call OpenAI, does not write to DB and does
not alter /api/realtime/* behavior.

Main integration pattern:
    decision = decorate_orkio_policy_decision_with_realtime_unlock(decision, message)

AO67A principles:
- Realtime is a reward/journey moment, not a raw button.
- The chat explains the 2-minute voice experience before the user clicks.
- Voice session itself should stay simple: listen, answer, end safely.
- Do not over-offer voice for factual/short commands.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional


AO67A_REALTIME_UNLOCK_VERSION = "AO68A-HF1_CONVERSATIONAL_PROTECTION_LAYER"


def _norm(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        raw = unicodedata.normalize("NFD", raw)
        raw = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    except Exception:
        pass
    raw = raw.lower()
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", str(text or "").strip()) if w])


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


_SHORT_DIRECT_PATTERNS = (
    "em uma frase",
    "uma frase",
    "responda curto",
    "responda apenas",
    "so responda",
    "só responda",
    "sim ou nao",
    "sim ou não",
    "quem e",
    "quem é",
    "quando foi criado",
    "qual e",
    "qual é",
    "defina",
    "explique em uma linha",
)

_BLOCKED_TECH_OR_INTERNAL_PATTERNS = (
    "patch",
    "diff",
    "arquivo completo",
    "github",
    "deploy",
    "backend",
    "frontend",
    "main.py",
    "appconsole",
    "orion",
    "auditor",
    "auditoria tecnica",
    "auditoria técnica",
    "router",
    "sse",
    "stack trace",
    "log",
    "logs",
)

_ALREADY_VOICE_PATTERNS = (
    "realtime",
    "real time",
    "tempo real",
    "voz",
    "audio",
    "áudio",
    "microfone",
    "microphone",
    "raiozinho",
    "icone de voz",
    "ícone de voz",
    "2 minutos",
    "dois minutos",
)

_COMPLEXITY_PATTERNS = (
    "nao sei por onde comecar",
    "não sei por onde começar",
    "estou perdido",
    "estou travado",
    "preciso organizar",
    "preciso estruturar",
    "preciso decidir",
    "tenho varias duvidas",
    "tenho várias dúvidas",
    "varias perguntas",
    "várias perguntas",
    "muitas coisas",
    "muito contexto",
    "me ajuda a planejar",
    "plano de acao",
    "plano de ação",
    "estrategia",
    "estratégia",
    "roadmap",
    "business plan",
    "captação",
    "captacao",
    "investidor",
    "investidores",
    "go to market",
    "go-to-market",
    "arquitetura",
    "automacao",
    "automação",
    "vendas",
    "atendimento",
    "produto",
    "pitch",
    "empresa",
    "startup",
    "negocio",
    "negócio",
    "processo",
    "processos",
)

_EMOTIONAL_OR_URGENCY_PATTERNS = (
    "urgente",
    "pressa",
    "cansado",
    "cansada",
    "esgotado",
    "esgotada",
    "preocupado",
    "preocupada",
    "ansioso",
    "ansiosa",
    "travado",
    "travada",
    "perdido",
    "perdida",
    "preciso de clareza",
    "preciso de ajuda",
)


def should_offer_realtime_unlock(message: Any, *, visible_agent: Optional[str] = None) -> Dict[str, Any]:
    """Return a decision describing whether Orkio should invite the user to Realtime.

    The decision is conservative on purpose:
    - Avoids short/factual requests.
    - Avoids technical/internal/audit contexts.
    - Avoids repeating if user already talks about voice/realtime.
    - Favors complex, strategic, emotionally loaded, or multi-question prompts.
    """

    raw = str(message or "").strip()
    text = _norm(raw)
    words = _word_count(raw)
    question_marks = raw.count("?") + raw.count("？")

    if not text:
        return {"offer": False, "reason": "empty"}

    if _contains_any(text, _ALREADY_VOICE_PATTERNS):
        return {"offer": False, "reason": "already_voice_context"}

    if _contains_any(text, _SHORT_DIRECT_PATTERNS) and words <= 28:
        return {"offer": False, "reason": "short_direct_request"}

    if _contains_any(text, _BLOCKED_TECH_OR_INTERNAL_PATTERNS):
        return {"offer": False, "reason": "technical_or_internal_context"}

    complexity_hits = [term for term in _COMPLEXITY_PATTERNS if term in text]
    emotional_hits = [term for term in _EMOTIONAL_OR_URGENCY_PATTERNS if term in text]

    score = 0
    reasons = []

    if words >= 45:
        score += 2
        reasons.append("long_context")
    elif words >= 28:
        score += 1
        reasons.append("medium_context")

    if question_marks >= 2:
        score += 2
        reasons.append("multiple_questions")
    elif question_marks == 1 and words >= 25:
        score += 1
        reasons.append("question_with_context")

    if complexity_hits:
        score += min(3, len(complexity_hits))
        reasons.append("strategic_complexity")

    if emotional_hits:
        score += min(2, len(emotional_hits))
        reasons.append("emotional_or_urgency_signal")

    # A very short message should not trigger the reward unless explicit complexity is present.
    if words < 18 and not complexity_hits and not emotional_hits:
        return {"offer": False, "reason": "too_short"}

    offer = score >= 3
    return {
        "offer": bool(offer),
        "reason": "realtime_unlock_candidate" if offer else "score_below_threshold",
        "score": score,
        "signals": reasons,
        "word_count": words,
    }


def build_realtime_unlock_invite() -> str:
    """Premium invitation copy inserted by Orkio in chat, not inside Realtime."""

    return (
        "\n\n—\n"
        "Percebo que existe bastante contexto aqui. Uma conversa rápida por voz pode acelerar muito nosso entendimento.\n\n"
        "Posso liberar uma sessão de voz em tempo real para avançarmos de forma mais dinâmica. Quando ela iniciar, teremos até 2 minutos para aproveitar ao máximo esse momento; depois continuamos normalmente pelo chat, preservando o que foi construído.\n\n"
        "Conforme você interage e compartilha mais contexto por escrito, novos recursos e experiências vão sendo liberados na jornada. Quando fizer sentido para você, basta clicar no ícone de voz."
    )


def build_realtime_unlock_explanation() -> str:
    """Answer direct user questions about how the Realtime journey works."""

    return (
        "O Realtime funciona como um recurso de jornada: primeiro conversamos por texto para eu entender melhor seu contexto; quando fizer sentido, eu te convido para uma sessão rápida por voz.\n\n"
        "Ao iniciar, teremos até 2 minutos para absorver o máximo de informação possível. Depois, seguimos pelo chat com tudo mais organizado.\n\n"
        "Quanto mais você interage, compartilha objetivos, dúvidas e contexto, mais recursos podem ser liberados ao longo da experiência."
    )


def is_realtime_unlock_conversational_context(message: Any) -> bool:
    """Return True when the user is negotiating a natural voice/realtime journey.

    This is the AO68A protection layer. It prevents technical-audit templates
    from hijacking normal user phrases that contain words like "realtime",
    "abrir", "simular", "2 minutos" or "tempo real".

    It is deliberately narrow: technical/audit/patch/github/deploy contexts
    still remain available for AO20BC.
    """

    text = _norm(message)
    if not text:
        return False

    hard_technical_terms = (
        "patch",
        "diff",
        "arquivo completo",
        "github",
        "deploy",
        "backend",
        "frontend",
        "main.py",
        "appconsole",
        "stack trace",
        "logs",
        "log do railway",
        "erro 500",
        "sse",
        "router ao20",
        "auditoria tecnica",
        "auditoria técnica",
        "war room",
    )
    if _contains_any(text, hard_technical_terms):
        return False

    voice_terms = (
        "realtime",
        "real time",
        "tempo real",
        "voz",
        "audio",
        "áudio",
        "microfone",
        "raiozinho",
        "icone de voz",
        "ícone de voz",
        "2 minutos",
        "dois minutos",
    )
    journey_terms = (
        "simular",
        "simulação",
        "simulacao",
        "conversa rapida",
        "conversa rápida",
        "conversarmos",
        "conversar",
        "abrir",
        "abre",
        "abrirá",
        "abrira",
        "liberar",
        "libere",
        "disponibilizar",
        "disponibilize",
        "apresenta a opcao",
        "apresentar a opcao",
        "apresenta a opção",
        "apresentar a opção",
        "vou dar",
        "dar tres informacoes",
        "dar três informações",
        "tres informacoes",
        "três informações",
        "tres pontos",
        "três pontos",
    )
    polite_request_terms = (
        "por favor",
        "poderia",
        "pode",
        "posso",
        "ok",
        "combinado",
        "quando fizer sentido",
    )

    has_voice = _contains_any(text, voice_terms)
    has_journey = _contains_any(text, journey_terms)
    has_polite_request = _contains_any(text, polite_request_terms)

    # Direct voice request.
    if has_voice and (has_journey or has_polite_request):
        return True

    # Continuation after Orkio invited the user to provide context.
    if has_journey and _contains_any(text, ("vou dar", "tres informacoes", "três informações", "tres pontos", "três pontos")):
        return True

    return False


def _realtime_unlock_direct_answer(message: Any) -> str:
    """Friendly Orkio response for direct Realtime journey requests."""

    text = _norm(message)

    if _contains_any(text, ("vou dar", "tres informacoes", "três informações", "tres pontos", "três pontos")):
        return (
            "Perfeito. Me envie essas três informações, uma por vez ou todas juntas.\n\n"
            "Depois disso eu organizo rapidamente o contexto e te oriento a usar o ícone de voz para abrirmos uma conversa em tempo real. "
            "Quando iniciar, teremos até 2 minutos para aproveitar bem esse momento e depois seguimos pelo chat com tudo preservado."
        )

    if _contains_any(text, ("disponibilizar", "disponibilize", "liberar", "libere", "abrir", "abre", "2 minutos", "dois minutos")):
        return (
            "Sim. Podemos usar uma conversa em tempo real como próximo passo.\n\n"
            "Para funcionar bem, primeiro me dê um pouco de contexto por texto. Em seguida, clique no ícone de voz/raiozinho para iniciar. "
            "Quando a sessão abrir, teremos até 2 minutos para absorver o máximo de informação possível; depois continuamos normalmente pelo chat."
        )

    if _contains_any(text, ("simular", "simulação", "simulacao")):
        return (
            "Claro. Vamos simular essa jornada.\n\n"
            "Primeiro trocamos algumas mensagens por texto para eu entender o contexto. Depois eu te convido a usar o ícone de voz para uma conversa em tempo real. "
            "Quando ela iniciar, teremos até 2 minutos para aproveitar bem a troca; ao final, seguimos pelo chat com o contexto organizado."
        )

    return build_realtime_unlock_explanation()


def _is_direct_realtime_journey_question(message: Any) -> bool:
    text = _norm(message)
    if not text:
        return False
    direct_terms = (
        "como funciona o realtime",
        "como funciona o real time",
        "como funciona a voz",
        "como funciona o recurso de voz",
        "como libero a voz",
        "como liberar a voz",
        "como liberar o realtime",
        "como desbloqueia",
        "como desbloquear",
        "dois minutos de voz",
        "2 minutos de voz",
        "surpresas no caminho",
        "recursos serao liberados",
        "recursos serão liberados",
    )
    return _contains_any(text, direct_terms) or is_realtime_unlock_conversational_context(message)

def build_realtime_unlock_journey_decision(
    message: Any,
    *,
    visible_agent: Optional[str] = None,
    target_agent_slug: Optional[str] = None,
    dest_mode: Optional[str] = None,
    route_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Standalone AO67A journey decision.

    HF2 upgrade:
    - Direct questions about voice/realtime are still answered immediately.
    - Conversational unlock candidates now become a handled Orkio response
      before Chris/valuation fast-path can capture the turn.
    - Technical/audit/internal messages remain untouched because
      should_offer_realtime_unlock() explicitly rejects them.
    """

    if _is_direct_realtime_journey_question(message):
        return {
            "handled": True,
            "reason": "ao67a_realtime_unlock_explanation",
            "answer": _realtime_unlock_direct_answer(message),
            "agent_name": "Orkio",
            "visible_agent": "Orkio",
            "final_speaker": "Orkio",
            "runtime_hints": {
                "ao67a_realtime_unlock": True,
                "journey_version": AO67A_REALTIME_UNLOCK_VERSION,
                "precedence": "before_chris_fastpath",
            },
        }

    candidate = should_offer_realtime_unlock(message, visible_agent=visible_agent)
    if candidate.get("offer"):
        answer = (
            "Entendi. Antes de tentar resolver tudo de uma vez, eu organizaria isso em uma primeira camada simples: "
            "quais são os três projetos, qual deles está mais urgente e qual decisão precisa ficar clara agora.\n\n"
            "Podemos começar por texto com uma visão rápida de prioridade e, se fizer sentido, acelerar com voz.\n"
            + build_realtime_unlock_invite()
        )
        return {
            "handled": True,
            "reason": "ao67a_realtime_unlock_candidate",
            "answer": answer,
            "agent_name": "Orkio",
            "visible_agent": "Orkio",
            "final_speaker": "Orkio",
            "runtime_hints": {
                "ao67a_realtime_unlock": True,
                "ao67a_realtime_unlock_candidate": candidate,
                "journey_version": AO67A_REALTIME_UNLOCK_VERSION,
                "precedence": "before_chris_fastpath",
                "write_executed": False,
            },
        }

    return {
        "handled": False,
        "reason": candidate.get("reason") or "ao67a_no_realtime_unlock_candidate",
        "runtime_hints": {
            "ao67a_realtime_unlock_checked": True,
            "ao67a_realtime_unlock_candidate": candidate,
            "journey_version": AO67A_REALTIME_UNLOCK_VERSION,
        },
    }


def decorate_orkio_policy_decision_with_realtime_unlock(
    decision: Optional[Dict[str, Any]],
    message: Any,
    *,
    visible_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Append the Realtime unlock invitation to an existing Orkio decision.

    Safe behavior:
    - If decision is not handled, return it unchanged.
    - If answer is empty, return it unchanged.
    - If answer already mentions voice/realtime, return unchanged.
    - If prompt is a good unlock candidate, append a compact premium invitation.
    """

    if not isinstance(decision, dict):
        return {"handled": False, "reason": "ao67a_invalid_decision"}

    if not decision.get("handled"):
        return decision

    answer = str(decision.get("answer") or "").strip()
    if not answer:
        return decision

    answer_norm = _norm(answer)
    if _contains_any(answer_norm, _ALREADY_VOICE_PATTERNS):
        return decision

    candidate = should_offer_realtime_unlock(message, visible_agent=visible_agent)
    if not candidate.get("offer"):
        try:
            hints = dict(decision.get("runtime_hints") or {})
            hints["ao67a_realtime_unlock_checked"] = True
            hints["ao67a_realtime_unlock_reason"] = candidate.get("reason")
            decision["runtime_hints"] = hints
        except Exception:
            pass
        return decision

    decorated = dict(decision)
    decorated["answer"] = answer + build_realtime_unlock_invite()
    decorated["reason"] = str(decorated.get("reason") or "public_orkio_policy") + "+ao67a_realtime_unlock_invite"
    decorated["agent_name"] = decorated.get("agent_name") or "Orkio"
    decorated["visible_agent"] = decorated.get("visible_agent") or "Orkio"
    decorated["final_speaker"] = decorated.get("final_speaker") or "Orkio"

    hints = dict(decorated.get("runtime_hints") or {})
    hints.update({
        "ao67a_realtime_unlock": True,
        "ao67a_realtime_unlock_candidate": candidate,
        "journey_version": AO67A_REALTIME_UNLOCK_VERSION,
    })
    decorated["runtime_hints"] = hints
    return decorated

