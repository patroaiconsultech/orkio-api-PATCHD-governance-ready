import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, uploadFile, chat, chatStream, transcribeAudio, requestFounderHandoff, getRealtimeClientSecret, startRealtimeSession, startSummitSession, postRealtimeEventsBatch, endRealtimeSession, getRealtimeSession, getSummitSessionScore, submitSummitSessionReview, downloadRealtimeAta as downloadRealtimeAtaFile, guardRealtimeTranscript, getOrionSquadHealth, getOrionSquadPreview, getAgentCapabilities } from "../ui/api.js";
import { clearSession, getTenant, getToken, getUser, isAdmin, isApproved, setSession, logout } from "../lib/auth.js";
import { ORKIO_CANONICAL_VOICE_ID, ORKIO_DEFAULT_TTS_SPEED, ORKIO_DEFAULT_VOICE_ID, ORKIO_VOICES, coerceTtsSpeed, coerceVoiceId } from "../lib/voices.js";
import TermsModal from "../ui/TermsModal.jsx";
import PWAInstallPrompt from "../components/PWAInstallPrompt.jsx";
import OnboardingModal from "../components/OnboardingModal.jsx";
import { startSessionHeartbeat } from "../lib/sessionHeartbeat.js";
import EmptyStatePremium from "../components/EmptyStatePremium.jsx";
import ExecutionTimeline from "../components/ExecutionTimeline.jsx";
import MessageBubble from "../components/chat/MessageBubble.jsx";
import RealtimeTimeboxOverlay from "../components/realtime/RealtimeTimeboxOverlay.jsx";
import RealtimeTranscriptSummary from "../components/realtime/RealtimeTranscriptSummary.jsx";
import { useRealtimeTranscriptSummary } from "../hooks/realtime/useRealtimeTranscriptSummary.js";

// AO68A-HF6R10_NO_BACKEND_END_ON_WARMUP — suppress fake quota/cooldown on failed realtime warmup

// AO68A-HF6R9_REALTIME_NO_COOLDOWN_ON_RETRY — safe AppConsole patch applied

// ORKIO_AO60D_REALTIME_MOBILE_HARDENING
function buildRealtimeDiagnosticError(code, message, diagnostic = {}) {
  const err = new Error(message || "Falha ao iniciar Realtime");
  err.code = code || "REALTIME_DIAGNOSTIC_ERROR";
  err.userMessage = message || "Não consegui abrir a voz em tempo real agora.";
  err.diagnostic = diagnostic || {};
  return err;
}

function getRealtimeBrowserPreflight() {
  const result = {
    ok: true,
    online: true,
    secureContext: true,
    hasMediaDevices: true,
    hasGetUserMedia: true,
    protocol: "",
    host: "",
    reason: null,
  };

  try {
    if (typeof window !== "undefined") {
      result.secureContext = Boolean(
        window.isSecureContext ||
        window.location?.protocol === "https:" ||
        /^localhost$|^127\.0\.0\.1$/.test(window.location?.hostname || "")
      );
      result.protocol = window.location?.protocol || "";
      result.host = window.location?.host || "";
    }
  } catch {}

  try {
    if (typeof navigator !== "undefined") {
      result.online = navigator.onLine !== false;
      result.hasMediaDevices = Boolean(navigator.mediaDevices);
      result.hasGetUserMedia = Boolean(navigator.mediaDevices?.getUserMedia);
    }
  } catch {}

  if (!result.online) {
    result.ok = false;
    result.reason = "browser_offline";
  } else if (!result.secureContext) {
    result.ok = false;
    result.reason = "insecure_context";
  } else if (!result.hasMediaDevices || !result.hasGetUserMedia) {
    result.ok = false;
    result.reason = "media_devices_unavailable";
  }

  return result;
}

function realtimePreflightMessage(reason) {
  if (reason === "browser_offline") {
    return "Não consegui abrir a voz em tempo real porque o dispositivo parece estar sem conexão. O chat continua funcionando quando a internet voltar.";
  }
  if (reason === "insecure_context") {
    return "A voz em tempo real precisa de uma conexão segura HTTPS no navegador/PWA. O chat continua disponível por texto.";
  }
  if (reason === "media_devices_unavailable") {
    return "Este navegador/PWA não expôs o microfone para a voz em tempo real. Atualize o app, verifique permissões ou continue por texto.";
  }
  return "Não consegui abrir a voz em tempo real agora. O chat continua funcionando normalmente.";
}


function normalizeUserFacingRuntimeMessage(value, context = "") {
  let normalizedValue = value;
  if (value && typeof value === "object") {
    normalizedValue =
      value.userMessage ??
      value.message ??
      value.detail?.message ??
      value.detail ??
      value.code ??
      value.error ??
      value.statusText ??
      "";
    if (typeof normalizedValue === "object") {
      try { normalizedValue = JSON.stringify(normalizedValue); } catch { normalizedValue = ""; }
    }
  }
  const raw = String(normalizedValue || "").trim();
  const lower = raw.toLowerCase();

  // ORKIO_AO60C_PWA_REALTIME_DIAGNOSTIC_GUARD
  if (
    lower.includes("failed to fetch") ||
    lower.includes("network_fetch_failed") ||
    lower.includes("network request failed") ||
    lower.includes("load failed") ||
    lower.includes("networkerror") ||
    lower.includes("cors") ||
    lower.includes("typeerror: failed")
  ) {
    if (context === "voice" || context === "realtime") {
      return (
        "Não consegui abrir a voz em tempo real agora. O chat continua funcionando normalmente.\n\n" +
        "Motivo provável: a conexão de voz não foi concluída entre o PWA e a API. " +
        "Tente novamente em alguns segundos ou continue por texto."
      );
    }

    return (
      "Não consegui concluir a conexão agora. Verifique sua internet e tente novamente. " +
      "O chat continua disponível por texto."
    );
  }

  if (context === "voice" || context === "realtime") {
    if (
      lower.includes("browser_offline") ||
      lower.includes("insecure_context") ||
      lower.includes("media_devices_unavailable") ||
      lower.includes("mic_permission_denied") ||
      lower.includes("mic_get_user_media_failed") ||
      lower.includes("realtime_sdp_fetch_failed")
    ) {
      if (lower.includes("browser_offline")) {
        return "Não consegui abrir a voz em tempo real porque o dispositivo parece estar sem conexão. O chat continua funcionando normalmente quando a internet voltar.";
      }
      if (lower.includes("insecure_context")) {
        return "A voz em tempo real precisa de uma conexão segura HTTPS no navegador/PWA. O chat continua disponível por texto.";
      }
      if (lower.includes("media_devices_unavailable")) {
        return "Este navegador/PWA não liberou acesso ao microfone para a voz em tempo real. Verifique as permissões do app ou continue por texto.";
      }
      if (lower.includes("mic_permission_denied")) {
        return "O microfone está bloqueado para este PWA. Libere a permissão de microfone nas configurações do navegador/app e tente novamente.";
      }
      if (lower.includes("mic_get_user_media_failed")) {
        return "Não consegui capturar o áudio do microfone neste dispositivo. Tente novamente, revise as permissões ou continue por texto.";
      }
      if (lower.includes("realtime_sdp_fetch_failed")) {
        return "Não consegui concluir a conexão de voz em tempo real com o provedor agora. O chat continua disponível por texto.";
      }
    }
  }

  if (
    context === "voice" || context === "realtime"
  ) {
    if (
      lower.includes("insufficient_quota") ||
      lower.includes("current quota") ||
      lower.includes("billing") ||
      lower.includes("billing_hard_limit") ||
      lower.includes("exceeded your current quota")
    ) {
      return (
        "Realtime indisponível por quota/billing da OpenAI. " +
        "A recarga ou ajuste de billing precisa ser feito antes de novo teste. " +
        "O chat por texto continua disponível."
      );
    }

    if (
      lower.includes("rate_limited") ||
      lower.includes("status_429") ||
      lower.includes("http 429") ||
      lower.includes("realtime_cooldown_active") ||
      lower.includes("too many requests")
    ) {
      return "A voz em tempo real estará disponível novamente em alguns minutos. O chat por texto continua disponível.";
    }

    if (
      lower.includes("auth_forbidden") ||
      lower.includes("status_403") ||
      lower.includes("http 403") ||
      lower.includes("forbidden")
    ) {
      return (
        "A voz em tempo real não foi autorizada para esta sessão. " +
        "Verifique se o onboarding foi concluído e tente novamente. O chat continua disponível por texto."
      );
    }

    if (
      lower.includes("auth_session_expired") ||
      lower.includes("status_401") ||
      lower.includes("unauthorized") ||
      lower.includes("session expired")
    ) {
      return (
        "Sua sessão precisa ser atualizada antes de iniciar a voz em tempo real. " +
        "Entre novamente e tente outra vez. O chat continua disponível por texto."
      );
    }
  }

  if (!raw) {
    return context === "voice"
      ? "Não consegui acessar a voz neste momento. Você pode continuar por texto."
      : "Não consegui concluir esta ação agora.";
  }

  if (
    lower.includes("requested device not found") ||
    lower.includes("device not found") ||
    lower.includes("notfounderror") ||
    lower.includes("microphone not found") ||
    lower.includes("no input devices")
  ) {
    return "Microfone não encontrado. Verifique se há um microfone conectado e se o navegador tem permissão para usá-lo. Você também pode continuar por texto.";
  }

  if (
    lower.includes("permission denied") ||
    lower.includes("notallowederror") ||
    lower.includes("permission dismissed")
  ) {
    return "Permissão de microfone negada. Libere o acesso ao microfone no navegador ou continue por texto.";
  }

  if (
    lower.includes("realtime connection failed") ||
    lower.includes("realtime connection disconnected") ||
    lower.includes("pc_failed")
  ) {
    return "A conexão de voz oscilou. A conversa por texto segue disponível normalmente.";
  }

  if (lower.includes("onboarding incomplete") || lower.includes("cadastro complementar pendente")) {
    return "Seu cadastro complementar precisa ser concluído para liberar este recurso. Se você acabou de salvar o contexto, abra uma nova conversa ou tente novamente em instantes.";
  }

  if (lower === "[object object]") {
    return "Não consegui concluir esta ação agora. Tente novamente em instantes.";
  }

  return raw;
}

function humanizeConsoleStatusMessage(value) {
  return normalizeUserFacingRuntimeMessage(value);
}


// ORKIO_UI_SAFE_TRACE_OBJECT_NORMALIZATION_FINAL
// Normaliza valores antes de entrarem no executionTrace.
// Evita que objetos JS apareçam como "[object Object]" no painel "Ver execução".
function safeTraceText(value, fallback = "") {
  if (value === null || value === undefined) return fallback;

  if (typeof value === "string") {
    const raw = value.trim();
    if (!raw || raw === "[object Object]") return fallback;
    return raw;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const joined = value
      .map((item) => safeTraceText(item, ""))
      .filter(Boolean)
      .join(", ");
    return joined || fallback;
  }

  if (typeof value === "object") {
    const preferred =
      value.label ??
      value.message ??
      value.status ??
      value.reason ??
      value.detail ??
      value.name ??
      value.code ??
      value.event ??
      value.step ??
      value.type;

    if (preferred !== undefined) {
      return safeTraceText(preferred, fallback);
    }

    try {
      const compact = JSON.stringify(value);
      if (compact && compact !== "{}") {
        return compact.length > 220 ? `${compact.slice(0, 217)}...` : compact;
      }
    } catch {}
  }

  return fallback;
}

function safeTraceBadges(badges) {
  if (!Array.isArray(badges)) return [];
  return badges.map((badge) => safeTraceText(badge, "")).filter(Boolean);
}

function sanitizeExecutionTraceStep(step) {
  const source = step && typeof step === "object" ? step : {};

  return {
    ...source,
    kind: safeTraceText(source.kind, "status"),
    label: safeTraceText(source.label, "Etapa registrada"),
    detail: safeTraceText(source.detail, ""),
    agentName: safeTraceText(source.agentName, ""),
    badges: safeTraceBadges(source.badges),
    source: safeTraceText(source.source, ""),
  };
}


// ORKIO_WHATSAPP_CTA_PREMIUM
// Transforma links WhatsApp enviados pelo backend em um CTA visual premium,
// sem alterar o conteúdo semântico da resposta do agente.
function normalizeExternalHref(rawUrl = "") {
  let url = String(rawUrl || "").trim();
  let trailing = "";

  while (/[),.;!?]+$/.test(url)) {
    trailing = `${url.slice(-1)}${trailing}`;
    url = url.slice(0, -1);
  }

  const href = url.toLowerCase().startsWith("www.") ? `https://${url}` : url;
  return { href, displayUrl: url, trailing };
}

function isWhatsappUrl(rawUrl = "") {
  const url = String(rawUrl || "").trim().toLowerCase();
  return (
    url.includes("wa.me/") ||
    url.includes("api.whatsapp.com/send") ||
    url.includes("whatsapp.com/send")
  );
}

function renderWhatsappCtaCard(href, key) {
  const safeHref = href || "https://wa.me/5551989697605";

  return (
    <div
      key={key}
      style={{
        marginTop: 14,
        marginBottom: 8,
        padding: "14px",
        borderRadius: "18px",
        border: "1px solid rgba(52,211,153,0.34)",
        background:
          "linear-gradient(135deg, rgba(16,185,129,0.16), rgba(15,23,42,0.34))",
        boxShadow: "0 18px 40px rgba(0,0,0,0.22)",
        whiteSpace: "normal",
      }}
    >
      <div
        style={{
          fontSize: "13px",
          fontWeight: 950,
          color: "#d1fae5",
          letterSpacing: "0.2px",
          marginBottom: 6,
        }}
      >
        Quer transformar isso em projeto real?
      </div>

      <div
        style={{
          fontSize: "12px",
          lineHeight: 1.45,
          color: "rgba(236,253,245,0.86)",
          marginBottom: 12,
        }}
      >
        Nossa equipe pode mapear sua demanda e desenhar os agentes personalizados ideais para sua empresa.
      </div>

      <a
        href={safeHref}
        target="_blank"
        rel="noreferrer noopener"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          textDecoration: "none",
          borderRadius: "999px",
          padding: "10px 14px",
          background: "linear-gradient(135deg, #22c55e, #14b8a6)",
          color: "#04111d",
          fontSize: "13px",
          fontWeight: 950,
          boxShadow: "0 12px 28px rgba(20,184,166,0.24)",
        }}
      >
        💬 Falar com a equipe no WhatsApp
      </a>

      <div
        style={{
          marginTop: 9,
          fontSize: "11px",
          color: "rgba(209,250,229,0.62)",
          fontWeight: 700,
        }}
      >
        Atendimento humano • ORKIO/PATROAI
      </div>
    </div>
  );
}

function renderMessageContentPremium(value) {
  const text = String(value || "");
  if (!text) return "";

  const urlRegex = /(https?:\/\/[^\s<>"']+|www\.[^\s<>"']+)/gi;
  const nodes = [];
  let lastIndex = 0;
  let matchIndex = 0;
  let match;

  while ((match = urlRegex.exec(text)) !== null) {
    const rawUrl = match[0];
    const before = text.slice(lastIndex, match.index);
    if (before) nodes.push(before);

    const { href, displayUrl, trailing } = normalizeExternalHref(rawUrl);

    if (isWhatsappUrl(href)) {
      nodes.push(renderWhatsappCtaCard(href, `whatsapp-cta-${match.index}-${matchIndex}`));
    } else {
      nodes.push(
        <a
          key={`link-${match.index}-${matchIndex}`}
          href={href}
          target="_blank"
          rel="noreferrer noopener"
          style={{
            color: "#93c5fd",
            fontWeight: 800,
            textDecoration: "underline",
            textUnderlineOffset: "3px",
            overflowWrap: "anywhere",
          }}
        >
          {displayUrl}
        </a>
      );
    }

    if (trailing) nodes.push(trailing);
    lastIndex = match.index + rawUrl.length;
    matchIndex += 1;
  }

  const after = text.slice(lastIndex);
  if (after) nodes.push(after);

  return nodes.length ? nodes : text;
}



const ORKIO_ENV = (typeof window !== "undefined" && window.__ORKIO_ENV__) ? window.__ORKIO_ENV__ : {};
const SUMMIT_VOICE_MODE = ((ORKIO_ENV.VITE_SUMMIT_VOICE_MODE || import.meta.env.VITE_SUMMIT_VOICE_MODE || "realtime").trim().toLowerCase() === "stt_tts")
  ? "stt_tts"
  : "realtime";
const SPEECH_RECOGNITION_LANG = ((ORKIO_ENV.VITE_SPEECH_RECOGNITION_LANG || import.meta.env.VITE_SPEECH_RECOGNITION_LANG || "pt-BR").trim() || "pt-BR");


// METATRON_CHAT_FORCE_STREAM_AND_TIMEOUT
// Auditoria 16/05: o stream estava sendo abortado cedo demais pelo connect timeout
// de 15s. Mantemos /api/chat/stream como rail primário e ampliamos a janela de
// conexão/turno para permitir respostas multiagente sem cancelar prematuramente.
// METATRON_PLATFORM_RECOVERY_HARD_STREAM
// Recuperação operacional 17/05:
// O runtime/env estava conseguindo desligar o stream e empurrar o chat direto
// para /api/chat, caminho que fica preso em preflight/provisional headers.
// Para restabelecer a plataforma, o chat textual SEMPRE tenta /api/chat/stream
// como trilho primário. O env não pode desativar esse trilho.
const ORKIO_CHAT_STREAM_PRIMARY = true;
const CHAT_STREAM_TIMEOUT_MS = Math.max(
  30000,
  Number(ORKIO_ENV.VITE_CHAT_STREAM_TIMEOUT_MS || import.meta.env.VITE_CHAT_STREAM_TIMEOUT_MS || 120000) || 120000
);
const CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT_MS = Math.max(
  10000,
  Math.min(
    60000,
    Number(
      ORKIO_ENV.VITE_CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT_MS ||
        import.meta.env.VITE_CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT_MS ||
        25000
    ) || 25000
  )
);
// AO20K-HF4G_FRONTEND_STREAM_TERMINAL_GUARD
// Se o backend mantiver o SSE vivo apenas com keepalive/status, a UI não deve
// permanecer em "runtime" indefinidamente. O consumidor encerra com fallback
// seguro quando não vê chunk útil dentro da janela acima.

const CHAT_STREAM_CONNECT_TIMEOUT_MS = Math.max(
  30000,
  Number(ORKIO_ENV.VITE_CHAT_STREAM_CONNECT_TIMEOUT_MS || import.meta.env.VITE_CHAT_STREAM_CONNECT_TIMEOUT_MS || 90000) || 90000
);
const CHAT_TURN_RECONCILE_ATTEMPTS = Math.max(
  1,
  Number(ORKIO_ENV.VITE_CHAT_TURN_RECONCILE_ATTEMPTS || import.meta.env.VITE_CHAT_TURN_RECONCILE_ATTEMPTS || 2) || 2
);

// METATRON_CHAT_RECOVERY_DIRECT_FALLBACK
// Recuperação operacional 17/05:
// /api/chat/stream permanece como rail primário, mas o fallback /api/chat volta a ficar
// habilitado para restaurar a plataforma quando o SSE não estabilizar.
// O fallback segue com AbortController + timeout para não travar a UI.
// METATRON_PLATFORM_RECOVERY_HARD_STREAM
// /api/chat direto está comprovadamente instável neste deploy: preflight 200,
// POST pendente/provisional headers. Mantemos o fallback DESLIGADO por padrão
// para não trocar um erro de stream por um travamento indefinido.
// Só habilite com VITE_CHAT_DIRECT_FALLBACK_ENABLED=true após o POST /api/chat
// aparecer como 200 nos logs da API.
const ORKIO_CHAT_DIRECT_FALLBACK_ENABLED = (
  String(ORKIO_ENV.VITE_CHAT_DIRECT_FALLBACK_ENABLED || import.meta.env.VITE_CHAT_DIRECT_FALLBACK_ENABLED || "false")
    .trim()
    .toLowerCase() === "true"
);

const WALLET_UI_ENABLED = false;

const EMPTY_STATE_PREVIEW_STEPS = [
  { title: "Readiness", description: "Shell preservado, acessos visíveis e console pronto para a primeira ação com percepção premium." },
  { title: "Focus", description: "O centro da experiência destaca a próxima melhor ação sem esconder threads, wallet e navegação." },
  { title: "Activation", description: "A primeira execução nasce com prompts guiados, contexto e leitura de impacto imediato." },
  { title: "Executive output", description: "Timeline, telemetria e resposta final mantêm linguagem mais madura e decisiva." },
];

const EMPTY_STATE_PREVIEW_LOGS = [
  "Primeira vitória visível no centro do console.",
  "Prompt guiado, blueprint e próximos passos acessíveis no primeiro clique.",
  "Sidebar, usuário e navegação continuam intactos.",
  "Leitura premium reforçada por contraste, profundidade e hierarquia.",
];

class StreamSemanticError extends Error {
  constructor(payload = {}) {
    super(payload?.message || payload?.error || "Stream semantic error");
    this.name = "StreamSemanticError";
    this.payload = payload || {};
    this.status = payload?.code || "STREAM_ERROR";
  }
}

function withTimeout(promise, ms, label = "timeout") {
  let timer = null;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      const err = new Error(label);
      err.code = "STREAM_TIMEOUT";
      reject(err);
    }, Math.max(1000, Number(ms || 0)));
  });

  return Promise.race([promise, timeout]).finally(() => {
    if (timer) clearTimeout(timer);
  });
}

function isAbortLikeError(err) {
  return err?.name === "AbortError" ||
    err?.code === "CHAT_STREAM_ABORTED" ||
    err?.code === "STREAM_TIMEOUT" ||
    err?.code === "CHAT_STREAM_TIMEOUT" ||
    err?.code === "FETCH_ABORTED" ||
    err?.code === "CHAT_DIRECT_TIMEOUT";
}



async function consumeChatStream(
  response,
  {
    onStatus,
    onError,
    onDone,
    onChunk,
    onAgentDone,
    onKeepalive,
    onExecution,
    signal,
    isStale,
  } = {}
) {
  const reader = response?.body?.getReader?.();
  if (!reader) return { thread_id: null, trace_id: null, event_count: 0, used_stream: false };

  const abortStream = () => {
    try { reader.cancel?.(); } catch {}
    const err = new Error("CHAT_STREAM_ABORTED");
    err.name = "AbortError";
    err.code = "CHAT_STREAM_ABORTED";
    throw err;
  };

  const decoder = new TextDecoder();
  let buf = "";
  let lastThreadId = null;
  let lastTraceId = null;
  let eventCount = 0;
  let donePayload = null;
  let draftText = "";
  let doneSeen = false;
  const streamStartedAt = Date.now();
  let lastStreamActivityAt = streamStartedAt;
  let firstUsefulChunkAt = null;

  const markStreamActivity = () => {
    lastStreamActivityAt = Date.now();
  };

  const buildStreamTerminalError = (code, message) => {
    const err = new Error(message || code);
    err.code = code;
    err.thread_id = lastThreadId;
    err.trace_id = lastTraceId;
    err.draftText = draftText;
    return err;
  };

  // AO-24_STREAM_KEEPALIVE_PROGRESS_GUARD
  // status/keepalive SSE events mean the backend is alive and still processing.
  // Do not kill a live stream just because the first useful chunk is slower.
  // Keep the terminal guard only for true stream silence/inactivity.
  const assertStreamActivityProgress = () => {
    if (doneSeen || firstUsefulChunkAt) return;

    const silentFor = Date.now() - lastStreamActivityAt;
    const maxSilentMs = Math.max(CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT_MS, 45000);

    if (silentFor > maxSilentMs) {
      throw buildStreamTerminalError(
        "CHAT_STREAM_NO_ACTIVITY_TIMEOUT",
        "CHAT_STREAM_NO_ACTIVITY_TIMEOUT"
      );
    }
  };

  const flushBlock = (block) => {
    const lines = String(block || "").split(/\r?\n/).filter(Boolean);
    if (!lines.length) return;
    let ev = "message";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) ev = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    let payload = {};
    if (dataLines.length) {
      try { payload = JSON.parse(dataLines.join("\n")); } catch { payload = { raw: dataLines.join("\n") }; }
    }
    try {
      console.log("SSE_EVENT", ev, payload);
    } catch {}
    if (signal?.aborted || isStale?.()) abortStream();
    markStreamActivity();
    if (payload?.thread_id) lastThreadId = payload.thread_id;
    if (payload?.trace_id) lastTraceId = payload.trace_id;
    eventCount += 1;
    if (ev === "status") {
      onStatus?.(payload);
      assertStreamActivityProgress();
    }
    if (ev === "execution") onExecution?.(payload);
    if (ev === "agent_started" || ev === "orchestrator_merge") {
      onExecution?.({ ...(payload || {}), event: ev, step: ev });
    }
    if (ev === "agent_chunk") {
      const delta = String(payload?.delta ?? payload?.content ?? payload?.text ?? "");
      if (delta) {
        draftText += delta;
        firstUsefulChunkAt = firstUsefulChunkAt || Date.now();
      }
      onChunk?.(payload, draftText);
      onExecution?.({ ...(payload || {}), event: ev, step: ev });
    }
    if (ev === "chunk") {
      const delta = String(payload?.delta ?? payload?.content ?? "");
      if (delta) {
        draftText += delta;
        firstUsefulChunkAt = firstUsefulChunkAt || Date.now();
      }
      onChunk?.(payload, draftText);
    }
    if (ev === "agent_done") onAgentDone?.(payload, draftText);
    if (ev === "keepalive") {
      onKeepalive?.(payload);
      assertStreamActivityProgress();
    }
    if (ev === "error") {
      onError?.(payload);

      // METATRON_CHAT_STREAM_TERMINAL_GUARD_CLIENT
      // O backend pode emitir um erro operacional recuperável e, em seguida,
      // enviar chunk/agent_done/done para liberar a UI com mensagem segura.
      // Não devemos abortar o parser nesses códigos; devemos continuar lendo
      // até o event: done.
      const recoverableCodes = new Set([
        "CHAT_STREAM_TERMINAL_TIMEOUT",
        "CHAT_STREAM_RUNTIME_TIMEOUT",
        "CHAT_STREAM_BACKEND_TIMEOUT",
        "CHAT_STREAM_RECOVERY_DONE",
        "CHAT_STREAM_RECOVERY_SHIM_FAILED",
        "CHAT_STREAM_FATAL",
        "STREAM_RECOVERED_WITH_OPERATIONAL_MESSAGE",
      ]);

      const agentScopedRecoverableError = !!payload?.agent_id && payload?.code !== "SERVER_BUSY";
      const terminalRecoverableError = recoverableCodes.has(String(payload?.code || ""));

      if (!agentScopedRecoverableError && !terminalRecoverableError) {
        throw new StreamSemanticError(payload);
      }
    }
    if (ev === "done") {
      donePayload = payload || {};
      onDone?.(payload);
      doneSeen = true;
      try { reader.cancel?.(); } catch {}
      return;
    }
  };

  while (true) {
    if (signal?.aborted || isStale?.()) abortStream();
    const { value, done } = await reader.read();
    if (signal?.aborted || isStale?.()) abortStream();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split(/\r?\n\r?\n/);
    buf = parts.pop() || "";
    for (const part of parts) {
      flushBlock(part);
      if (doneSeen) break;
    }
    if (doneSeen) break;
  }
  if (!doneSeen && buf.trim()) flushBlock(buf);
  if (!doneSeen) {
    throw buildStreamTerminalError(
      "CHAT_STREAM_ENDED_WITHOUT_DONE",
      "CHAT_STREAM_ENDED_WITHOUT_DONE"
    );
  }
  return {
    thread_id: donePayload?.thread_id || lastThreadId,
    trace_id: donePayload?.trace_id || lastTraceId,
    event_count: eventCount,
    used_stream: true,
    runtime_hints: donePayload?.runtime_hints || null,
    execution_cursor: donePayload?.runtime_hints?.routing?.execution_cursor || null,
    execution_lifecycle: donePayload?.runtime_hints?.routing?.execution_lifecycle || null,
    routing_source: donePayload?.runtime_hints?.routing?.routing_source || null,
    route_applied: !!donePayload?.runtime_hints?.routing?.route_applied,
    done_payload: donePayload,
    draft_text: draftText,
  };
}

const REALTIME_IDLE_FOLLOWUP_ENABLED = ((ORKIO_ENV.VITE_REALTIME_IDLE_FOLLOWUP_ENABLED || import.meta.env.VITE_REALTIME_IDLE_FOLLOWUP_ENABLED || "true").toString().trim().toLowerCase() !== "false");
const REALTIME_IDLE_FOLLOWUP_MS = Math.max(5000, Number(ORKIO_ENV.VITE_REALTIME_IDLE_FOLLOWUP_MS || import.meta.env.VITE_REALTIME_IDLE_FOLLOWUP_MS || 10000) || 10000);
const REALTIME_REARM_AFTER_ASSISTANT_MS = Math.max(800, Number(ORKIO_ENV.VITE_REALTIME_RESTART_AFTER_TTS_MS || import.meta.env.VITE_REALTIME_RESTART_AFTER_TTS_MS || 1800) || 1800);

const REALTIME_AUTO_RESPONSE_ENABLED = ((ORKIO_ENV.VITE_REALTIME_AUTO_RESPONSE_ENABLED || import.meta.env.VITE_REALTIME_AUTO_RESPONSE_ENABLED || "true").toString().trim().toLowerCase() !== "false");

// AO68A-HF6R8 — stable realtime VAD defaults for PT/EN demos.
const REALTIME_SERVER_VAD_THRESHOLD = Math.min(
  0.95,
  Math.max(
    0.1,
    Number(
      ORKIO_ENV.VITE_REALTIME_VAD_THRESHOLD ||
      import.meta.env.VITE_REALTIME_VAD_THRESHOLD ||
      0.72
    ) || 0.72
  )
);
const REALTIME_SERVER_VAD_SILENCE_MS = Math.max(
  250,
  Number(
    ORKIO_ENV.VITE_REALTIME_VAD_SILENCE_MS ||
    import.meta.env.VITE_REALTIME_VAD_SILENCE_MS ||
    1800
  ) || 1800
);
const REALTIME_SERVER_VAD_PREFIX_MS = Math.max(
  0,
  Number(
    ORKIO_ENV.VITE_REALTIME_VAD_PREFIX_PADDING_MS ||
    ORKIO_ENV.VITE_REALTIME_VAD_HOLD_MS ||
    import.meta.env.VITE_REALTIME_VAD_PREFIX_PADDING_MS ||
    import.meta.env.VITE_REALTIME_VAD_HOLD_MS ||
    500
  ) || 500
);

function resolveRealtimeIdleDisplayName(userObj) {
  const raw = (userObj?.name || userObj?.full_name || "").toString().trim();
  if (!raw) return "";
  const first = raw.split(/\s+/).filter(Boolean)[0] || raw;
  return first.replace(/[^\p{L}\p{N}]/gu, "") || "";
}


function normalizeAgentVoiceId(raw, fallback = ORKIO_DEFAULT_VOICE_ID) {
  const voice = String(raw || "").trim().toLowerCase();
  const aliases = {
    marine: "marin",
    marin: "marin",
    nova: "shimmer",
    onyx: "echo",
    fable: "sage",
  };
  const valid = new Set(["alloy","ash","ballad","cedar","coral","echo","fable","marin","nova","onyx","sage","shimmer","verse"]);
  const normalized = aliases[voice] || voice;
  return valid.has(normalized) ? normalized : (String(fallback || ORKIO_DEFAULT_VOICE_ID).trim().toLowerCase() || ORKIO_DEFAULT_VOICE_ID);
}


function extractPatchGovernanceMeta(content) {
  const text = String(content || "");
  if (!/PATCH GOVERNANCE RESPONSE/i.test(text)) return null;
  const get = (name) => {
    const m = text.match(new RegExp(`^\\s*${name}\\s*:\\s*([^\\n]+)`, "im"));
    return m ? String(m[1] || "").trim() : "";
  };
  const auditReceiptId = get("audit_receipt_id");
  const patchMode = get("patch_mode");
  const writeAllowed = get("write_allowed");
  return {
    audit_receipt_id: auditReceiptId,
    patch_mode: patchMode,
    write_allowed: writeAllowed,
    can_approve: Boolean(auditReceiptId && /proposal_only/i.test(patchMode) && /false/i.test(writeAllowed)),
  };
}


function extractPatchApprovalMeta(content) {
  const text = String(content || "");
  const isApprovalResponse = /PATCH APPROVAL RESPONSE/i.test(text);
  const isGovernedExecutionResponse = /GOVERNED PATCH EXECUTION RESPONSE|PATCH EXECUTION RESPONSE/i.test(text);
  if (!isApprovalResponse && !isGovernedExecutionResponse) return null;

  const get = (name) => {
    const m = text.match(new RegExp(`^\\s*-?\\s*${name}\\s*:\\s*([^\\n]+)`, "im"));
    return m ? String(m[1] || "").trim() : "";
  };

  const status = get("status");
  const auditReceiptId = get("audit_receipt_id");
  const patchMode = get("patch_mode");
  const writeAllowed = get("write_allowed");
  const humanApproved = get("human_approved");
  const approvalId = get("approval_id");
  const patchId = get("patch_id");
  const executionChannel = get("execution_channel");

  const terminalExecution = /execution_completed|execution_failed|execution_cancelled|execution_blocked_no_executable_artifact|execution_blocked_executor_not_wired|execution_request_failed|execution_blocked_missing_approval|execution_blocked_invalid_context/i.test(status);
  const approvedPending =
    /approval_registered/i.test(status) ||
    /execution_blocked_conversational_channel/i.test(status) ||
    /side_channel_required/i.test(executionChannel) ||
    (/approved_apply/i.test(patchMode) && /true/i.test(humanApproved) && !terminalExecution);

  return {
    status,
    audit_receipt_id: auditReceiptId,
    approval_id: approvalId,
    patch_id: patchId,
    patch_mode: patchMode,
    write_allowed: writeAllowed,
    human_approved: humanApproved,
    execution_channel: executionChannel,
    can_execute: Boolean(approvedPending && /approved_apply/i.test(patchMode) && /true/i.test(humanApproved) && !terminalExecution),
  };
}

function findPendingApprovedPatchExecution(items) {
  const arr = Array.isArray(items) ? items : [];
  let latestApproval = null;
  let latestTerminal = null;
  let latestProposal = null;

  for (const m of arr) {
    const content = String(m?.content || "");
    const ts = Number(m?.created_at || 0) || 0;
    const id = String(m?.id || "");
    const key = `${ts}:${id}`;

    // PATCH23: any newer proposal supersedes previous approval/execution state.
    // Without this, an old approved_apply message can keep rendering an execution
    // button for a stale patch_id/audit_receipt_id after a new proposal appears.
    const isProposal =
      /PATCH GOVERNANCE RESPONSE/i.test(content) &&
      /patch_mode\s*:\s*proposal_only/i.test(content);
    if (isProposal) {
      const auditMatch = content.match(/^\s*audit_receipt_id\s*:\s*([^\n]+)/im);
      latestProposal = {
        message: m,
        key,
        audit_receipt_id: auditMatch ? String(auditMatch[1] || "").trim() : "",
      };
    }

    const approval = extractPatchApprovalMeta(content);
    if (approval?.can_execute) {
      latestApproval = { message: m, meta: approval, key };
    }

    // A conversational-channel block is NOT a terminal execution result.
    // It only tells the user to use the governed side-channel button.
    // Keep the approved execution pending so the "Executar patch aprovado" button remains visible.
    const isExecutionResponse = /GOVERNED PATCH EXECUTION RESPONSE|PATCH EXECUTION RESPONSE/i.test(content);
    const isConversationalBlock = /execution_blocked_conversational_channel/i.test(content);
    const isRealTerminalExecution =
      /execution_completed|execution_failed|execution_cancelled|execution_blocked_no_executable_artifact|execution_blocked_executor_not_wired|execution_request_failed|execution_blocked_missing_approval|execution_blocked_invalid_context/i.test(content);

    if (isExecutionResponse && isRealTerminalExecution && !isConversationalBlock) {
      latestTerminal = { message: m, key };
    }
  }

  if (!latestApproval) return null;

  // A newer proposal invalidates old approved-apply UI state.
  if (latestProposal && String(latestProposal.key) > String(latestApproval.key)) {
    return null;
  }

  if (latestTerminal && String(latestTerminal.key) > String(latestApproval.key)) return null;
  return latestApproval;
}

function buildPendingExecutionGuidance() {
  return [
    "GOVERNED PATCH EXECUTION RESPONSE",
    "",
    "- status: execution_blocked_conversational_channel",
    "- patch_mode: approved_apply",
    "- write_allowed: false",
    "- human_approved: true",
    "",
    "Resultado:",
    "Existe uma execução governada aprovada aguardando ação, mas o chat comum não executa patches.",
    "Use exclusivamente o botão “Executar patch aprovado”.",
    "Nenhuma escrita, branch, commit ou PR foi executado por esta mensagem.",
  ].join("\n");
}

function resolveAgentVoice(agentLike) {
  const name = String(agentLike?.agent_name || agentLike?.name || "").trim().toLowerCase();
  const dbVoice = String(agentLike?.voice_id || "").trim();
  const envMap = {
    orkio: (window.__ORKIO_ENV__?.VITE_ORKIO_VOICE_ID || import.meta.env.VITE_ORKIO_VOICE_ID || "").trim(),
    chris: (window.__ORKIO_ENV__?.VITE_CHRIS_VOICE_ID || import.meta.env.VITE_CHRIS_VOICE_ID || "").trim(),
    orion: (window.__ORKIO_ENV__?.VITE_ORION_VOICE_ID || import.meta.env.VITE_ORION_VOICE_ID || "").trim(),
  };
  const defaultVoice = (window.__ORKIO_ENV__?.VITE_REALTIME_VOICE || import.meta.env.VITE_REALTIME_VOICE || ORKIO_DEFAULT_VOICE_ID).trim() || ORKIO_DEFAULT_VOICE_ID;
  return normalizeAgentVoiceId(dbVoice || envMap[name] || defaultVoice, defaultVoice);
}


function canonicalizeSpeakerLabel(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const normalizedKey = text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

  const map = {
    ux_frontend: "UX Frontend",
    auditor: "Auditor",
    systems_architect: "Systems Architect",
    backend_engineer: "Backend Engineer",
    frontend_engineer: "Frontend Engineer",
    qa_release_engineer: "QA Release Engineer",
    devops_sre: "DevOps SRE",
    security_guardian: "Security Guardian",
    data_db_architect: "Data DB Architect",
    realtime_voice_engineer: "Realtime Voice Engineer",
    orkio: "Orkio",
    chris: "Chris",
    orion: "Orion",
    agent: "Agent",
    agente: "Agent",
    assistant: "Agent",
    model: "Agent",
  };

  return map[normalizedKey] || text;
}

// AO64D — Public assistant speaker sanitation.
// Orion is an internal audit/governance agent and must not appear as the visible
// assistant for AMCHAM/public users. Backend may return blocked_agent=Orion and
// resolved_agent=Orkio; the UI must honor the resolved public speaker.
function canSeeInternalOrionSpeaker() {
  try {
    return Boolean(isAdmin?.());
  } catch {
    return false;
  }
}

function readRuntimeRoutingField(messageLike, key) {
  try {
    return (
      messageLike?.[key] ||
      messageLike?.runtime_hints?.routing?.[key] ||
      messageLike?.runtimeHints?.routing?.[key] ||
      messageLike?.done_payload?.[key] ||
      messageLike?.done_payload?.runtime_hints?.routing?.[key] ||
      ""
    );
  } catch {
    return "";
  }
}

function sanitizePublicAssistantSpeaker(messageLike, proposedName = "Orkio") {
  const proposed = canonicalizeSpeakerLabel(proposedName || "Orkio");
  const proposedKey = String(proposed || "").trim().toLowerCase();

  const blockedAgent = canonicalizeSpeakerLabel(
    readRuntimeRoutingField(messageLike, "blocked_agent") ||
    readRuntimeRoutingField(messageLike, "blockedAgent") ||
    messageLike?.blocked_agent ||
    messageLike?.blockedAgent ||
    ""
  );
  const resolvedAgent = canonicalizeSpeakerLabel(
    readRuntimeRoutingField(messageLike, "resolved_agent") ||
    readRuntimeRoutingField(messageLike, "resolvedAgent") ||
    messageLike?.resolved_agent ||
    messageLike?.resolvedAgent ||
    ""
  );
  const finalSpeaker = canonicalizeSpeakerLabel(
    messageLike?.final_speaker ||
    readRuntimeRoutingField(messageLike, "final_speaker") ||
    ""
  );
  const visibleAgent = canonicalizeSpeakerLabel(
    messageLike?.visible_agent ||
    readRuntimeRoutingField(messageLike, "visible_agent") ||
    ""
  );

  const blockedKey = String(blockedAgent || "").trim().toLowerCase();
  const resolvedKey = String(resolvedAgent || "").trim().toLowerCase();
  const finalKey = String(finalSpeaker || "").trim().toLowerCase();
  const visibleKey = String(visibleAgent || "").trim().toLowerCase();
  const contentText = String(
    messageLike?.answer ||
    messageLike?.message ||
    messageLike?.final_text ||
    messageLike?.content ||
    messageLike?.text ||
    ""
  ).toLowerCase();

  if (
    blockedKey === "orion" ||
    resolvedKey === "orkio" ||
    contentText.includes("orion é um agente interno") ||
    contentText.includes("orion faz parte da equipe interna") ||
    contentText.includes("orion e um agente interno")
  ) {
    return "Orkio";
  }

  if ((finalKey === "orkio" || visibleKey === "orkio") && proposedKey === "orion") {
    return "Orkio";
  }

  if (proposedKey === "orion" && !canSeeInternalOrionSpeaker()) {
    return "Orkio";
  }

  return proposed || "Orkio";
}


function inferSpeakerNameFromContent(content) {
  const text = String(content || "").trim();
  if (!text) return "";
  const lines = text
    .split(/\r?\n/)
    .map((line) => String(line || "").replace(/^[\s#>*-]+/, "").replace(/\s*[:：]\s*$/, "").trim())
    .filter(Boolean);

  if (!lines.length) return "";
  const first = lines[0];
  const inferred = canonicalizeSpeakerLabel(first);
  const normalizedInferred = String(inferred || "").trim().toLowerCase();
  const normalizedFirst = String(first || "").trim().toLowerCase();
  if (!inferred) return "";
  if (["agent", "assistant", "model", "agente"].includes(normalizedFirst)) return "Agent";
  if (inferred !== first) return inferred;
  return "";
}

function resolveAssistantDisplayName(messageLike, fallback = "Agent") {
  const rawName =
    messageLike?.agent_name ||
    messageLike?.final_speaker ||
    messageLike?.visible_agent ||
    messageLike?.speaker_name ||
    messageLike?.name ||
    "";

  const explicitFromContent = inferSpeakerNameFromContent(
    messageLike?.final_text || messageLike?.content || messageLike?.text || ""
  );

  const normalizedRaw = canonicalizeSpeakerLabel(rawName);
  const rawLower = String(normalizedRaw || "").trim().toLowerCase();

  let candidate = "";

  if (explicitFromContent && ["agent", "assistant", "model"].includes(rawLower)) {
    candidate = explicitFromContent;
  } else if (explicitFromContent && !rawName) {
    candidate = explicitFromContent;
  } else if (normalizedRaw) {
    candidate = normalizedRaw;
  } else if (explicitFromContent) {
    candidate = explicitFromContent;
  } else {
    candidate = fallback;
  }

  return sanitizePublicAssistantSpeaker(messageLike, candidate || fallback || "Orkio");
}

function normalizeMessageSpeaker(messageLike) {
  if (!messageLike || String(messageLike?.role || "").toLowerCase() !== "assistant") {
    return messageLike;
  }

  const displayName = resolveAssistantDisplayName(messageLike, "Orkio");

  return {
    ...messageLike,
    agent_name: displayName,
    final_speaker: displayName,
    visible_agent: displayName,
  };
}

// METATRON_CHAT_ORDER_STABILITY
// Mantém a ordem visual pergunta -> resposta mesmo quando o backend retorna mensagens
// fora de ordem, com timestamps empatados ou quando a reconciliação pós-stream substitui
// o histórico local pelo histórico persistido.
function coerceMessageTimestamp(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    // Backend pode retornar segundos; frontend local pode usar milissegundos.
    return value > 10_000_000_000 ? value : value * 1000;
  }

  const raw = String(value || "").trim();
  if (!raw) return null;

  const asNumber = Number(raw);
  if (Number.isFinite(asNumber)) {
    return asNumber > 10_000_000_000 ? asNumber : asNumber * 1000;
  }

  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function roleOrderForChat(role) {
  const normalized = String(role || "").toLowerCase();
  if (normalized === "user") return 10;
  if (normalized === "assistant") return 20;
  if (normalized === "agent") return 20;
  if (normalized === "tool") return 30;
  if (normalized === "system") return 40;
  return 50;
}

function getMessageSortTimestamp(message, fallbackIndex = 0) {
  const candidates = [
    message?.client_created_at,
    message?.created_at,
    message?.createdAt,
    message?.timestamp,
    message?.updated_at,
    message?.updatedAt,
  ];

  for (const candidate of candidates) {
    const parsed = coerceMessageTimestamp(candidate);
    if (parsed != null) return parsed;
  }

  return fallbackIndex;
}

function orderChatMessages(input) {
  const list = Array.isArray(input) ? input : [];
  return list
    .map((message, index) => ({ message, index }))
    .sort((a, b) => {
      const ta = getMessageSortTimestamp(a.message, a.index);
      const tb = getMessageSortTimestamp(b.message, b.index);

      if (ta !== tb) return ta - tb;

      const roleDelta = roleOrderForChat(a.message?.role) - roleOrderForChat(b.message?.role);
      if (roleDelta !== 0) return roleDelta;

      const clientOrderA = Number(a.message?.client_order ?? a.message?.clientOrder ?? NaN);
      const clientOrderB = Number(b.message?.client_order ?? b.message?.clientOrder ?? NaN);
      if (Number.isFinite(clientOrderA) && Number.isFinite(clientOrderB) && clientOrderA !== clientOrderB) {
        return clientOrderA - clientOrderB;
      }

      return a.index - b.index;
    })
    .map((entry) => entry.message);
}

function logRealtimeStep(step, payload = undefined) {
  try {
    const stamp = new Date().toISOString();
    if (payload === undefined) {
      console.log(`[Realtime][${stamp}] ${step}`);
    } else {
      console.log(`[Realtime][${stamp}] ${step}`, payload);
    }
  } catch {}
}


function hasAdminAccess(userObj) {
  if (!userObj) return false;
  const role = String(userObj?.role || "").trim().toLowerCase();
  const email = String(userObj?.email || userObj?.user_email || "").trim().toLowerCase();

  const envAdminEmails = String(
    ORKIO_ENV.VITE_ADMIN_EMAILS ||
    import.meta.env.VITE_ADMIN_EMAILS ||
    "daniel@patroai.com"
  )
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  return !!(
    role === "admin"
    || role === "owner"
    || role === "superadmin"
    || userObj?.is_admin === true
    || userObj?.admin === true
    || (email && envAdminEmails.includes(email))
  );
}


// Icons (inline SVG)
const IconPlus = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const IconSend = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const IconPaperclip = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21.44 11.05l-8.49 8.49a5 5 0 0 1-7.07-7.07l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.19 9.19a2 2 0 0 1-2.83-2.83l8.49-8.49" />
  </svg>
);

const IconEdit = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
  </svg>
);

const IconLogout = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const IconSettings = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const IconMessage = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 15a4 4 0 0 1-4 4H7l-4 4V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
  </svg>
);

const IconTrash = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
  </svg>
);


function tryParseEvent(content) {
  try {
    if (!content || typeof content !== "string") return null;
    const idx = content.indexOf("ORKIO_EVENT:");
    if (idx < 0) return null;
    const jsonStr = content.slice(idx + "ORKIO_EVENT:".length);
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

function stripEventMarker(content) {
  if (!content || typeof content !== "string") return content;
  const idx = content.indexOf("ORKIO_EVENT:");
  if (idx < 0) return content;
  return content.slice(0, idx).trim();
}

function formatTs(ts) {
  try {
    if (!ts) return "";
    return formatDateTime(ts);
  } catch {
    return "";
  }
}

function formatDateTime(ts) {
  if (ts === null || ts === undefined || ts === "") return "";
  try {
    let ms;
    if (typeof ts === "number") {
      // If value looks like milliseconds (13 digits), keep; if seconds (10 digits), convert.
      ms = ts > 10_000_000_000 ? ts : ts * 1000;
    } else {
      // ISO string or numeric string
      const n = Number(ts);
      if (!Number.isNaN(n) && Number.isFinite(n)) {
        ms = n > 10_000_000_000 ? n : n * 1000;
      } else {
        ms = new Date(ts).getTime();
      }
    }
    const d = new Date(ms);
    return new Intl.DateTimeFormat("pt-BR", {
      timeZone: "America/Sao_Paulo",
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(d);
  } catch {
    return "";
  }
}

function fmtUsd(value) {
  const n = Number(value || 0);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: n % 1 === 0 ? 0 : 2,
    }).format(n);
  } catch {
    return `$${n.toFixed(2)}`;
  }
}


function normalizeWalletErrorPayload(err) {
  const payload = err?.payload || err?.data || null;
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    if (payload.code === "WALLET_INSUFFICIENT_BALANCE") return payload;
    if (payload.detail && typeof payload.detail === "object" && payload.detail.code === "WALLET_INSUFFICIENT_BALANCE") {
      return payload.detail;
    }
  }
  if (typeof payload === "string") {
    try {
      const parsed = JSON.parse(payload);
      if (parsed?.code === "WALLET_INSUFFICIENT_BALANCE") return parsed;
      if (parsed?.detail?.code === "WALLET_INSUFFICIENT_BALANCE") return parsed.detail;
    } catch {}
  }
  const message = String(err?.message || "").trim();
  if (message) {
    try {
      const parsed = JSON.parse(message);
      if (parsed?.code === "WALLET_INSUFFICIENT_BALANCE") return parsed;
      if (parsed?.detail?.code === "WALLET_INSUFFICIENT_BALANCE") return parsed.detail;
    } catch {}
  }
  return null;
}

function buildWalletBlockedMessage(detail) {
  if (!detail) return "Sua wallet não possui saldo suficiente para continuar.";
  const current = Number(detail.current_balance_usd || detail.wallet?.balance_usd || 0);
  const required = Number(detail.required_usd || 0);
  const missing = Number(
    detail.missing_usd != null
      ? detail.missing_usd
      : Math.max(required - current, 0)
  );
  if (missing > 0.0001) {
    return `Saldo insuficiente na wallet. Faltam ${fmtUsd(missing)} para continuar.`;
  }
  if (required > 0.0001) {
    return `Saldo insuficiente na wallet. É recomendado manter pelo menos ${fmtUsd(required)} disponível.`;
  }
  return "Sua wallet não possui saldo suficiente para continuar.";
}

function isWalletBlockedError(err) {
  if (!err) return false;
  if (String(err?.status || "") === "402") return true;
  return normalizeWalletErrorPayload(err)?.code === "WALLET_INSUFFICIENT_BALANCE";
}




function summarizeExecutionStatus(payload = {}) {
  const raw = String(payload?.status || payload?.message || "").trim();
  if (!raw) return "Executando etapa";
  return raw.length > 140 ? `${raw.slice(0, 137)}...` : raw;
}

// AO20K-HF4M_PREMIUM_EXECUTION_TRACE_UX
function formatExecutionRoutingSource(raw = "") {
  const source = String(raw || "").trim();
  if (!source) return "";
  const labels = {
    "stream_ao20k_hf4k_simple_status": "Status seguro",
    "stream_ao20k_hf4k_immediate_memory_recall": "Memória imediata",
    "stream_ao20k_hf4k_simulation_only_branch_pr_plan": "Plano simulado",
  };
  return labels[source] || source.replace(/^stream_/, "").replaceAll("_", " ");
}

// HF6R2A_PREFER_HF6R1_ROUTE_METADATA
function formatRouteBadgeLabel(raw = "") {
  const value = String(raw || "").trim();
  if (!value) return "";
  const labels = {
    multi_intent_readonly_splitter: "multi intent readonly",
    multi_intent_readonly: "multi intent readonly",
    checkpoint_ack_readonly: "checkpoint readonly",
    checkpoint_readonly: "checkpoint readonly",
    safe_agent_ping: "agent ping",
    agent_ping: "agent ping",
    safe_agent_greeting: "agent greeting",
    agent_greeting: "agent greeting",
    readonly_audit_light: "readonly audit light",
    internal_diagnostic_token_readonly: "internal diagnostic token readonly",
    simple_greeting: "simple greeting",
    system_status_readonly: "system status readonly",
    controlled_evolution_readonly: "controlled evolution readonly",
    governed_pipeline_inventory_readonly: "governed pipeline inventory readonly",
    issue_map_patch_plan_readonly: "issue map patch plan readonly",
    branch_pr_plan_simulated_readonly: "branch/pr simulated readonly",
    safe_fastpath_coverage: "safe fast-path",
    technical_audit: "technical audit",
    orchestration_audit: "orchestration audit",
    general: "general",
  };
  return labels[value] || value.replaceAll("_", " ");
}

function buildExecutionBadgesFromRouting(routing = {}) {
  const badges = [];
  if (routing?.fast_path_hit || routing?.runtime_bypassed) badges.push("Fast-path");
  if (routing?.simulation_only) badges.push("Somente simulação");
  if (routing?.write_executed === false || routing?.write_allowed === false) badges.push("Sem escrita");
  if (routing?.branch_created === false && routing?.pr_created === false) badges.push("Sem branch/PR");

  // AO44_TRACE_LABEL_COHERENCE
  const preferredRoute =
    routing?.display_label ||
    routing?.execution_lifecycle ||
    routing?.route_kind ||
    routing?.route_family ||
    routing?.routing_source ||
    "";

  const routeBadge = formatRouteBadgeLabel(preferredRoute);
  if (routeBadge) badges.push(routeBadge);

  if (routing?.route_matrix_version === "HF6R1" || routing?.metadata_normalized) {
    badges.push("HF6R1");
  }

  return Array.from(new Set(badges.filter(Boolean))).slice(0, 5);
}

function buildExecutionDoneDetail(payload = {}) {
  const routing = payload?.runtime_hints?.routing || {};
  const parts = [];
  const sourceLabel = formatExecutionRoutingSource(routing?.routing_source);
  if (sourceLabel) parts.push(sourceLabel);
  if (routing?.simulation_only) parts.push("simulação readonly");
  if (routing?.write_executed === false) parts.push("sem escrita");
  if (routing?.execution_cursor?.current_node) parts.push(`nó ${routing.execution_cursor.current_node}`);
  return parts.join(" • ");
}


function normalizeCapabilityPayload(payload = null) {
  if (!payload || typeof payload !== "object") return null;
  const multiagent = payload?.multiagent && typeof payload.multiagent === "object" ? payload.multiagent : {};
  const github = payload?.github && typeof payload.github === "object" ? payload.github : {};
  return {
    multiagent,
    github,
  };
}

function formatGithubRuntimeStatus(capabilities = null) {
  const normalized = normalizeCapabilityPayload(capabilities);
  const github = normalized?.github || {};
  if (!github?.available) return "sem acesso";
  const mode = String(github?.mode || "").trim().toLowerCase();
  if (mode === "governed_pr_only") return "PR-only";
  if (github?.read_enabled && !github?.write_enabled) return "read-only";
  if (github?.write_enabled) return "conectado";
  return "conectado";
}

function formatActiveAgentRuntime(agentName = "") {
  const slug = String(agentName || "").trim().toLowerCase();
  if (!slug) return "";
  if (slug.startsWith("orion")) return "Orion analisando";
  if (slug.startsWith("chris")) return "Chris validando";
  if (slug.startsWith("auditor")) return "Auditor revisando";
  return "Orkio respondendo";
}

function traceStepTone(kind = "status") {
  if (kind === "error") return { icon: "⚠️", color: "#fca5a5", border: "rgba(248,113,113,0.24)", background: "rgba(127,29,29,0.22)" };
  if (kind === "done") return { icon: "✅", color: "#86efac", border: "rgba(74,222,128,0.24)", background: "rgba(20,83,45,0.22)" };
  if (kind === "agent") return { icon: "🧩", color: "#bfdbfe", border: "rgba(96,165,250,0.24)", background: "rgba(30,64,175,0.16)" };
  if (kind === "system") return { icon: "⚙️", color: "#c4b5fd", border: "rgba(139,92,246,0.24)", background: "rgba(76,29,149,0.18)" };
  return { icon: "⏳", color: "#e5e7eb", border: "rgba(148,163,184,0.20)", background: "rgba(15,23,42,0.26)" };
}

function resolveRealtimeTranscriptionLanguage(languageProfile) {
  // AO68A-HF6R8 — Onboarding controls the language hint. "auto" keeps provider auto-detect.
  const raw = String(languageProfile || "").trim();
  if (!raw) return null;

  const normalized = raw.toLowerCase().replace("_", "-");
  if (!normalized || normalized === "auto") return null;

  if (normalized === "pt" || normalized.startsWith("pt-")) return "pt";
  if (normalized === "en" || normalized.startsWith("en-")) return "en";
  if (normalized === "es" || normalized.startsWith("es-")) return "es";
  if (normalized === "fr" || normalized.startsWith("fr-")) return "fr";

  return normalized.split("-")[0] || null;
}


const ONBOARDING_USER_TYPES = [
  { value: "founder", label: "Founder" },
  { value: "investor", label: "Investor" },
  { value: "operator", label: "Operator" },
  { value: "partner", label: "Partner" },
  { value: "other", label: "Other" },
];

const ONBOARDING_INTENTS = [
  { value: "explore", label: "Explorar a plataforma" },
  { value: "meeting", label: "Agendar conversa" },
  { value: "pilot", label: "Avaliar piloto" },
  { value: "funding", label: "Discutir investimento" },
  { value: "other", label: "Outro" },
];

const ONBOARDING_COUNTRIES = [
  { value: "BR", label: "Brasil" },
  { value: "US", label: "Estados Unidos" },
  { value: "ES", label: "Espanha" },
  { value: "PT", label: "Portugal" },
  { value: "AR", label: "Argentina" },
  { value: "MX", label: "México" },
  { value: "CO", label: "Colômbia" },
  { value: "CL", label: "Chile" },
  { value: "UY", label: "Uruguai" },
  { value: "OTHER", label: "Outro" },
];

const ONBOARDING_LANGUAGES = [
  { value: "pt-BR", label: "Português (Brasil)" },
  { value: "en-US", label: "English (US)" },
  { value: "es-ES", label: "Español" },
  { value: "pt-PT", label: "Português (Portugal)" },
];

const DEFAULT_LANGUAGE_BY_COUNTRY = {
  BR: "pt-BR",
  PT: "pt-PT",
  ES: "es-ES",
  AR: "es-ES",
  MX: "es-ES",
  CO: "es-ES",
  CL: "es-ES",
  UY: "es-ES",
  US: "en-US",
  OTHER: "en-US",
};

function normalizeOnboardingUserType(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  const aliases = {
    founder: "founder",
    investor: "investor",
    operator: "operator",
    enterprise: "operator",
    developer: "operator",
    partner: "partner",
    other: "other",
  };
  return aliases[raw] || "";
}

function normalizeOnboardingIntent(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  const aliases = {
    explore: "explore",
    exploring: "explore",
    curious: "explore",
    meeting: "meeting",
    partnership: "meeting",
    pilot: "pilot",
    company_eval: "pilot",
    funding: "funding",
    investment: "funding",
    other: "other",
  };
  return aliases[raw] || "";
}

function suggestOnboardingLanguage(country) {
  const code = String(country || "").trim().toUpperCase();
  return DEFAULT_LANGUAGE_BY_COUNTRY[code] || "en-US";
}

// AO68A-HF5 — Realtime language propagation from onboarding.
// Keeps AMCHAM/PT-EN demos bilingual without forcing a global STT language.
function normalizeRealtimeLanguageProfile(raw) {
  const value = String(raw || "").trim();
  if (!value || value.toLowerCase() === "auto") return "auto";

  const normalized = value.toLowerCase().replace("_", "-");

  if (normalized === "pt" || normalized.startsWith("pt-")) return "pt";
  if (normalized === "en" || normalized.startsWith("en-")) return "en";
  if (normalized === "es" || normalized.startsWith("es-")) return "es";

  return "auto";
}

function getUserOnboardingLanguage(userObj, formObj) {
  const candidates = [
    formObj?.language,
    userObj?.language,
    userObj?.preferred_language,
    userObj?.language_profile,
    userObj?.profile?.language,
    userObj?.profile?.preferred_language,
    userObj?.onboarding?.language,
    userObj?.onboarding_context?.language,
  ];

  for (const candidate of candidates) {
    const value = String(candidate || "").trim();
    if (value) return value;
  }

  return "auto";
}

function buildRealtimeVoiceInstruction(languageProfile, messageText = "") {
  const lang = normalizeRealtimeLanguageProfile(languageProfile);
  const msg = String(messageText || "").trim();

  const base =
    lang === "en"
      ? "Answer the user by voice in English, briefly, naturally and helpfully."
      : lang === "es"
        ? "Responde al usuario por voz en español, de forma breve, natural y útil."
        : lang === "pt"
          ? "Responda ao usuário por voz em português, de forma curta, natural, útil e humana."
          : "Answer in the same language the user is using. Be brief, natural, useful and human.";

  return msg ? `${base} Mensagem do usuário: ${msg}` : base;
}

function buildRealtimeActivationProbeInstruction(languageProfile) {
  const lang = normalizeRealtimeLanguageProfile(languageProfile);

  if (lang === "en") {
    return {
      inputText: "Say only: Hello, I am Orkio in real time.",
      instructions: "Answer by audio in English, saying only: Hello, I am Orkio in real time.",
    };
  }

  if (lang === "es") {
    return {
      inputText: "Di solamente: Hola, soy Orkio en tiempo real.",
      instructions: "Responde en audio en español, diciendo solamente: Hola, soy Orkio en tiempo real.",
    };
  }

  return {
    inputText: "Diga apenas: Olá, eu sou o Orkio em tempo real.",
    instructions: "Responda em áudio em português, dizendo apenas: Olá, eu sou o Orkio em tempo real.",
  };
}

function normalizeWhatsapp(value) {
  return String(value || "").replace(/[^\d+]/g, "").trim();
}

function sanitizeOnboardingForm(data) {
  const country = String(data?.country || "").trim().toUpperCase() || "BR";
  const language = String(data?.language || "").trim() || suggestOnboardingLanguage(country);
  return {
    company: String(data?.company || "").trim(),
    role: String(data?.role || data?.profile_role || "").trim(),
    user_type: normalizeOnboardingUserType(data?.user_type) || "other",
    intent: normalizeOnboardingIntent(data?.intent) || "explore",
    country,
    language,
    whatsapp: normalizeWhatsapp(data?.whatsapp || ""),
    notes: String(data?.notes || "").trim(),
  };
}

export default function AppConsole() {

  const SHOW_REALTIME_AUDIT = false;

  // ORKIO_AO60I_REALTIME_TIMEBOX_COOLDOWN_COUNTER
  // ORKIO_AO60J_HF1_PREMIUM_2MIN_10MIN_WAKE_COUNTER
  // Unified web/PWA default = 2min session + 10min cooldown; backend remains source of truth.
  const REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS = 2 * 60;
  const REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS = 10 * 60;
  // AO64D-HF5_NO_HARD_TIMEBOX_ESG_FRONTEND
  // Time limits are now advisory-only. Backend HF4 removed hard cooldown/timebox,
  // and the frontend must not render a blocking clock nor auto-stop Realtime.
  const REALTIME_FRONTEND_HARD_TIMEBOX_ENABLED = false;
  // ORKIO_AO60K_HF5B_FRONTEND_ENDED_AT_SECONDS_TIMEBOX_VERIFY
  // Build marker used only for audit/debug so we can prove the active bundle contains HF5B.
  const ORKIO_AO60K_HF5B_BUILD_MARKER = "AO60K-HF5B_FRONTEND_ENDED_AT_SECONDS_TIMEBOX_VERIFY";
const ORKIO_AO61A_BUILD_MARKER = "AO61A_REALTIME_PREMIUM_UX_COOLDOWN_TRANSCRIPTION_LOCK";
const ORKIO_AO61A_HF3_BUILD_MARKER = "AO61A-HF3_TIMEBOX_COUNTER_AUTOSTOP_ASSISTANT_TRANSCRIPT";
const ORKIO_AO61A_HF4_BUILD_MARKER = "AO61A-HF4_FIXED_COUNTER_LONGEST_ASSISTANT_TRANSCRIPT";
const ORKIO_AO66R_HF4_BUILD_MARKER = "AO66R_REALTIME_ACTIVATION_REPAIR";

  const nav = useNavigate();


  async function confirmSessionExpired(reason = "unknown") {
    const t = getToken();
    const org = getTenant() || tenant || "public";

    if (!t) return true;

    try {
      await apiFetch("/api/me", {
        method: "GET",
        token: t,
        org,
        skipAuthRedirect: true,
      });
      return false;
    } catch (err) {
      if (err?.status === 401) {
        console.warn("session confirmed expired", { reason, code: err?.code });
        return true;
      }
      console.warn("session probe failed without confirmed expiry", {
        reason,
        status: err?.status,
        message: err?.message,
      });
      return false;
    }
  }

  async function logoutIfSessionReallyExpired(reason = "unknown") {
    const expired = await confirmSessionExpired(reason);
    if (expired) {
      clearSession();
      nav("/auth?session_expired=1");
      return true;
    }
    return false;
  }


  const [tenant, setTenant] = useState(getTenant() || "public");
  const [token, setToken] = useState(getToken());
  const [user, setUser] = useState(getUser());
  const canAccessAdmin = hasAdminAccess(user);

  // Summit presence heartbeat (single source of truth).
  // EFATA777 v12: the app must not keep an inline heartbeat loop in parallel with
  // startSessionHeartbeat(). A duplicated loop can keep sending stale tokens and
  // create noisy 401 races while another tab/session is already valid.
  React.useEffect(() => {
    if (!token) return undefined;

    const stopHeartbeat = startSessionHeartbeat({
      intervalMs: 45000,
      onUnauthorized: () => {
        void logoutIfSessionReallyExpired("heartbeat");
      },
    });

    return () => {
      try { stopHeartbeat?.(); } catch {}
    };
  }, [token, tenant]);

  useEffect(() => {
    try {
      console.log("ADMIN_RUNTIME_USER", user);
      console.log("ADMIN_RUNTIME_CAN_ACCESS", canAccessAdmin);
    } catch {}
  }, [user, canAccessAdmin]);

const [onboardingChecked, setOnboardingChecked] = useState(false);
const [bootstrapFailOpen, setBootstrapFailOpen] = useState(false);
const [onboardingOpen, setOnboardingOpen] = useState(false);
const [onboardingBusy, setOnboardingBusy] = useState(false);
const [onboardingStatus, setOnboardingStatus] = useState("");
const [onboardingForm, setOnboardingForm] = useState(() => sanitizeOnboardingForm(user));
  const [health, setHealth] = useState("checking");
  const [isMobile, setIsMobile] = useState(typeof window !== "undefined" ? window.innerWidth <= 820 : false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const [threads, setThreads] = useState([]);
  const [threadId, setThreadId] = useState("");
  const [messages, setMessages] = useState([]);
  const [agents, setAgents] = useState([]);
  const agentsByNameRef = useRef(new Map());
  const activeThreadIdRef = useRef("");
  const activeThreadEpochRef = useRef(0);
  const messagesAbortRef = useRef(null);
  const messagesLoadRequestRef = useRef(0);
  const requestedThreadIdRef = useRef("");
  const threadSelectionLockUntilRef = useRef(0);
  const pinnedThreadIdRef = useRef("");
  const initialStoredThreadIdRef = useRef("");
  const storageBootstrapConsumedRef = useRef(false);
  const storageBootstrapInitializedRef = useRef(false);
  const THREAD_STORAGE_KEY = "orkio_active_thread_id";

  function readStoredThreadId() {
    if (typeof window === "undefined") return "";
    try { return String(window.localStorage?.getItem(THREAD_STORAGE_KEY) || "").trim(); } catch { return ""; }
  }

  function persistActiveThreadId(nextId) {
    const safeId = String(nextId || "").trim();
    if (typeof window === "undefined") return;
    try {
      if (safeId) window.localStorage?.setItem(THREAD_STORAGE_KEY, safeId);
      else window.localStorage?.removeItem(THREAD_STORAGE_KEY);
    } catch {}
  }

  function getBootstrapStoredThreadId() {
    if (storageBootstrapConsumedRef.current) return "";
    if (!storageBootstrapInitializedRef.current) {
      initialStoredThreadIdRef.current = readStoredThreadId();
      storageBootstrapInitializedRef.current = true;
    }
    return String(initialStoredThreadIdRef.current || "").trim();
  }

  function consumeStoredThreadBootstrap(nextId = "") {
    storageBootstrapConsumedRef.current = true;
    initialStoredThreadIdRef.current = String(nextId || "").trim();
  }

  function lockThreadSelection(nextId = "", ttlMs = 15000) {
    const safeId = String(nextId || "").trim();
    if (safeId) pinnedThreadIdRef.current = safeId;
    threadSelectionLockUntilRef.current = Date.now() + Math.max(1000, Number(ttlMs || 0));
  }

  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const sendingRef = useRef(false);
  const [runtimeHints, setRuntimeHints] = useState(null);
  const showRuntimeHints = Boolean(user?.role === "admin" && typeof window !== "undefined" && window.localStorage?.getItem("orkio_show_runtime_hints") === "1");
  const showOrionSquad = Boolean(user?.role === "admin" && typeof window !== "undefined" && window.localStorage?.getItem("orkio_show_orion_squad") === "1");
  const [lastTraceId, setLastTraceId] = useState(null);
  const [agentCapabilities, setAgentCapabilities] = useState(null);
  const [activeRuntimeAgent, setActiveRuntimeAgent] = useState("");
  const [runtimeHandoffLabel, setRuntimeHandoffLabel] = useState("");
  const [orionSquadHealth, setOrionSquadHealth] = useState(null);
  const [orionSquadPreview, setOrionSquadPreview] = useState(null);
  const [walletSummary, setWalletSummary] = useState(null);
  const [walletSummaryLoading, setWalletSummaryLoading] = useState(false);
  const [walletSummaryError, setWalletSummaryError] = useState("");
  const [executionTrace, setExecutionTrace] = useState([]);
  const [patchApprovalModal, setPatchApprovalModal] = useState(null);
  const [patchApprovalPassword, setPatchApprovalPassword] = useState("");
  const [patchApprovalBusy, setPatchApprovalBusy] = useState(false);
  const [patchApprovalError, setPatchApprovalError] = useState("");
  const [executionTraceExpanded, setExecutionTraceExpanded] = useState(false);

  // Destination selector (Team / single / multi)
  const [destMode, setDestMode] = useState(() => {
    if (typeof window === "undefined") return "team";
    const stored = String(window.localStorage?.getItem("orkio_last_dest_mode") || "").trim().toLowerCase();
    return ["team", "single", "multi"].includes(stored) ? stored : "team";
  }); // team|single|multi
  const [destSingle, setDestSingle] = useState(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage?.getItem("orkio_last_dest_single") || "";
  }); // agent id
  const [destMulti, setDestMulti] = useState(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage?.getItem("orkio_last_dest_multi") || "[]";
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map((v) => String(v || "").trim()).filter(Boolean) : [];
    } catch {
      return [];
    }
  });   // agent ids

  // Upload modal
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFileObj, setUploadFileObj] = useState(null);
  const [uploadScope, setUploadScope] = useState("thread"); // thread|agents|institutional
  const [uploadAgentIds, setUploadAgentIds] = useState([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffNotice, setHandoffNotice] = useState("");
  const [showHandoffModal, setShowHandoffModal] = useState(false);
  const [handoffDraft, setHandoffDraft] = useState("");
  const [handoffInterestType, setHandoffInterestType] = useState("general");
  const [uploadProgress, setUploadProgress] = useState(false);

const fileInputRef = useRef(null);
const executionTraceRef = useRef([]);

const resetExecutionTrace = (steps = []) => {
  const normalized = Array.isArray(steps)
    ? steps.map((step, idx) => {
        const safeStep = sanitizeExecutionTraceStep(step);
        return {
          ...safeStep,
          id: safeStep.id || `trace-${Date.now()}-${idx}-${Math.random().toString(36).slice(2, 7)}`,
          ts: safeStep.ts || Date.now(),
        };
      })
    : [];

  executionTraceRef.current = normalized;
  setExecutionTrace(normalized);
};

const appendExecutionTrace = (step) => {
  if (!step) return;

  setExecutionTrace((prev) => {
    const safeStep = sanitizeExecutionTraceStep(step);

    const normalized = {
      ...safeStep,
      id: safeStep.id || `trace-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      ts: safeStep.ts || Date.now(),
    };

    const last = prev[prev.length - 1];
    if (
      last &&
      last.kind === normalized.kind &&
      last.label === normalized.label &&
      last.detail === normalized.detail &&
      last.agentName === normalized.agentName
    ) {
      return prev;
    }

    const next = [...prev.slice(-11), normalized];
    executionTraceRef.current = next;
    return next;
  });
};

const collapseExecutionTrace = (delayMs = 0) => {
  const run = () => {
    setExecutionTraceExpanded(false);
    try { window.localStorage?.setItem("orkio_execution_trace_open", "0"); } catch {}
  };
  if (delayMs > 0) {
    window.setTimeout(run, delayMs);
  } else {
    run();
  }
};

useEffect(() => {
  if (sending || !executionTrace.length) return undefined;
  const timer = window.setTimeout(() => {
    setExecutionTraceExpanded(false);
    try { window.localStorage?.setItem("orkio_execution_trace_open", "0"); } catch {}
  }, 900);
  return () => window.clearTimeout(timer);
}, [sending, executionTrace.length]);

const describeExecutionStatus = (payload = {}) => ({
  kind: payload?.agent_id ? "agent" : "status",
  label: summarizeExecutionStatus(payload),
  detail: payload?.message && payload?.message !== payload?.status ? String(payload.message) : "",
  agentName: payload?.agent_name || "",
});

const describeExecutionEvent = (payload = {}) => {
  const isHandoff = payload?.step === "agent_handoff";
  const handoffLabel = isHandoff
    ? `${payload?.from_agent_name || payload?.from_agent_id || "Agente"} → ${payload?.to_agent_name || payload?.agent_name || payload?.to_agent_id || "Agente"}`
    : null;
  return {
    kind: payload?.kind || (payload?.scope === "agent" ? "agent" : "system"),
    label: handoffLabel || payload?.label || summarizeExecutionStatus(payload),
    detail: String(payload?.detail || payload?.message || "").trim(),
    agentName: payload?.agent_name || payload?.to_agent_name || "",
  };
};

const describeExecutionError = (payload = {}) => {
  const label = payload?.code === "WALLET_INSUFFICIENT_BALANCE"
    ? "Saldo insuficiente para executar"
    : payload?.agent_name
    ? `${payload.agent_name} sinalizou uma falha`
    : "Execução interrompida";
  const detail = String(payload?.message || payload?.detail || payload?.error || "").trim();
  return {
    kind: "error",
    label,
    detail,
    agentName: payload?.agent_name || "",
  };
};

const describeExecutionDone = (payload = {}) => {
  const routing = payload?.runtime_hints?.routing || {};
  return {
    kind: "done",
    label: routing?.simulation_only ? "Execução simulada concluída" : "Execução concluída",
    detail: buildExecutionDoneDetail(payload),
    agentName: "",
    badges: buildExecutionBadgesFromRouting(routing),
    source: routing?.routing_source || "",
  };
};

useEffect(() => { executionTraceRef.current = executionTrace || []; }, [executionTrace]);

useEffect(() => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage?.setItem("orkio_execution_trace_open", executionTraceExpanded ? "1" : "0");
  } catch {}
}, [executionTraceExpanded]);

useEffect(() => {
  if (typeof window === "undefined") return;
  try {
    if (destSingle) window.localStorage?.setItem("orkio_last_dest_single", String(destSingle));
  } catch {}
}, [destSingle]);

useEffect(() => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage?.setItem("orkio_last_dest_mode", String(destMode || "team"));
  } catch {}
}, [destMode]);

useEffect(() => {
  if (typeof window === "undefined") return;
  try {
    const clean = Array.isArray(destMulti)
      ? Array.from(new Set(destMulti.map((v) => String(v || "").trim()).filter(Boolean)))
      : [];
    window.localStorage?.setItem("orkio_last_dest_multi", JSON.stringify(clean));
  } catch {}
}, [destMulti]);

useEffect(() => {
  let cancelled = false;
  async function loadCapabilities() {
    if (!token) {
      if (!cancelled) setAgentCapabilities(null);
      return;
    }
    try {
      const resp = await getAgentCapabilities({ token, org: tenant });
      if (!cancelled) setAgentCapabilities(normalizeCapabilityPayload(resp?.data || resp || null));
    } catch {
      if (!cancelled) setAgentCapabilities(null);
    }
  }
  void loadCapabilities();
  return () => { cancelled = true; };
}, [token, tenant]);

const messagesEndRef = useRef(null);
  const messagesRef = useRef([]); // PATCH0100_20B: keep latest messages for voice-to-voice sequencing

  // Voice-to-text (manual toggle)
  const [speechSupported] = useState(true);
  const speechRef = useRef(null);
  const [micEnabled, setMicEnabled] = useState(false);
  const micEnabledRef = useRef(false);
  const micRetryRef = useRef({ tries: 0, lastTry: 0 });

  // PATCH0100_13: Voice Mode (TTS + auto-send)
  const [voiceMode, setVoiceMode] = useState(SUMMIT_VOICE_MODE === "stt_tts");
  const voiceModeRef = useRef(SUMMIT_VOICE_MODE === "stt_tts");
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [ttsPlayingMessageId, setTtsPlayingMessageId] = useState(null);
  const ttsAudioRef = useRef(null);
  const ttsObjectUrlRef = useRef(null);
  // AO65A-HF3: allow stopping while /api/tts is still generating audio.
  const ttsAbortRef = useRef(null);
  const ttsStopRequestedRef = useRef(false);
  // AO65A-HF4: hard-stop protection against delayed blobs/audio callbacks after user stop.
  const ttsPlaySeqRef = useRef(0);
  const ttsSuppressAutoUntilRef = useRef(0);
  // AO65A-HF5: remember the message/text explicitly stopped by the user.
  // This blocks delayed automatic replays while still allowing a new user click.
  const ttsManualStopUntilRef = useRef(0);
  // AO65A-HF6: once the user stops message TTS, block all automatic classic TTS
  // until the next explicit user click. Timeout shields were not enough because
  // delayed auto paths can restart after the shield expires.
  const ttsManualStopActiveRef = useRef(false);
  const ttsStoppedMessageIdRef = useRef(null);
  const ttsStoppedTextRef = useRef("");
  const [ttsVoice, setTtsVoice] = useState(localStorage.getItem('orkio_tts_voice') || ORKIO_DEFAULT_VOICE_ID);
  const lastSpokenMsgRef = useRef('');
  const lastSpokenMessageIdRef = useRef(null);
  const micRestartTimeoutRef = useRef(null);
  const mediaRecorderStreamRef = useRef(null);
  const mediaRecorderSilenceIntervalRef = useRef(null);
  const mediaRecorderSilenceTimeoutRef = useRef(null);
  // PATCH0100_14: agent info from last chat response (for voice/avatar)
  const [lastAgentInfo, setLastAgentInfo] = useState(null);

  // PATCH0100_28: Terms acceptance modal
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [composerViewportOffset, setComposerViewportOffset] = useState(0);

  
  // Realtime/WebRTC voice mode (ultra low latency)
  const [realtimeMode, setRealtimeMode] = useState(false);
  const realtimeModeRef = useRef(false);
  const rtcPcRef = useRef(null);
  const rtcDcRef = useRef(null);
  const rtcAudioElRef = useRef(null);
  const rtcAudioProcessingRef = useRef(null);
  // ORKIO_AO60H_REALTIME_MOBILE_AUDIO_TRANSCRIPT_LIFECYCLE
  const rtcRemoteStreamRef = useRef(null);
  const rtcAudioWatchdogRef = useRef(null);
  const rtcWakeLockRef = useRef(null);
  // ORKIO_AO60J_REALTIME_FOREGROUND_WAKE_GUARD
  // Best-effort screen wake lock while Realtime is active in web/PWA foreground.
  // This keeps the display from auto-locking on supported Android/iOS/desktop browsers.
  const rtcWakeLockGuardTimerRef = useRef(null);
  const rtcWakeLockWantedRef = useRef(false);
  const rtcLastVisibilityHiddenAtRef = useRef(null);
  const rtcTextBufRef = useRef("");
  const rtcLastMagicRef = useRef("");
  const [rtcReadyToRespond, setRtcReadyToRespond] = useState(false);
  const rtcLastFinalTranscriptRef = useRef("");
  const rtcMagicEnabledRef = useRef(true);
  const rtcVoiceRef = useRef(ORKIO_DEFAULT_VOICE_ID);
  const rtcAudioTranscriptBufRef = useRef("");
  const rtcLastAssistantFinalRef = useRef("");
  const rtcAssistantFinalCommittedRef = useRef(false);
  const rtcAssistantFinalMessageIdRef = useRef(null);
  const rtcAssistantFinalTextRef = useRef("");
  const rtcAssistantPendingFinalTextRef = useRef("");
  const rtcAssistantPendingFinalSourceRef = useRef("");
  const rtcAssistantPendingFinalTimerRef = useRef(null);
  const rtcTimeboxHardStopTimerRef = useRef(null);
  const rtcTimeboxDeadlineRef = useRef(0);
  const rtcResponseTimeoutRef = useRef(null);
  const rtcAutoResponseFallbackTimerRef = useRef(null);
  const rtcLastTranscriptForAutoResponseRef = useRef("");
  const rtcFallbackActiveRef = useRef(false);
  const rtcResponseInFlightRef = useRef(false);
  // AO66R: activation repair — prove/trigger Realtime audio after the DataChannel opens.
  const rtcLastResponseCreatedAtRef = useRef(0);
  const rtcActivationProbeTimerRef = useRef(null);
  const rtcActivationProbeSentRef = useRef(false);
  // AO66A-HF2: prevent premature auto-end while Realtime is still stabilizing.
  const rtcSessionStartedAtRef = useRef(0);
  const rtcPendingAutoStopTimerRef = useRef(null);
  const rtcLastStopReasonRef = useRef("");


const rtcIdleFollowupTimerRef = useRef(null);
const rtcIdleFollowupSentRef = useRef(false);
const rtcLastUserActivityAtRef = useRef(0);

  // PATCH0100_27A: Realtime persistence (audit)
  const rtcSessionIdRef = useRef(null);
  const rtcThreadIdRef = useRef(null);
  const rtcEventQueueRef = useRef([]);
  const rtcFlushTimerRef = useRef(null);
  const rtcLivePollTimerRef = useRef(null);
  const rtcSeenBackendResponseIdsRef = useRef(new Set());
  const rtcConnectingRef = useRef(false);
  // ORKIO_AO60K_HF5_FRONTEND_MOBILE_REALTIME_RESTART_TRANSCRIPT_FIX
  // Hardens mobile/web restart lifecycle so a second Realtime attempt never inherits
  // stale peer/datachannel/audio/poll/timer/session state from the previous attempt.
  const rtcStartNonceRef = useRef(0);
  const rtcStopInFlightRef = useRef(false);
  const rtcStartupWatchdogTimerRef = useRef(null);
  const rtcLivePollSessionIdRef = useRef(null);
  // ORKIO_AO60I_REALTIME_TIMEBOX_COOLDOWN_COUNTER
  const rtcTimeboxTimerRef = useRef(null);
  // AO66R-HF6: timer starts only after Orkio's first spoken response completes.
  const rtcConversationStartedRef = useRef(false);
  const rtcPendingTimeboxSecondsRef = useRef(null);
  const rtcCooldownTimerRef = useRef(null);
  const rtcCooldownUntilRef = useRef(0);
  // ORKIO_AO60I_HF2_POLICY_REF
  // Keeps web and PWA timer/cooldown aligned with backend-returned timebox policy.
  const rtcTimeboxPolicyRef = useRef({
    maxSeconds: REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS,
    cooldownSeconds: REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS,
    remainingSeconds: null,
  });
  const [rtcTimeboxRemaining, setRtcTimeboxRemaining] = useState(null);
  const [rtcCooldownRemaining, setRtcCooldownRemaining] = useState(0);
  const [rtcPremiumStatus, setRtcPremiumStatus] = useState(null);
  const [rtcPremiumStatusDetail, setRtcPremiumStatusDetail] = useState("");
  // AO66R-HF4: visual kill switch independent from WebRTC/backend cleanup.
  const [rtcOverlayForceClosed, setRtcOverlayForceClosed] = useState(false);
  // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
  // Harden 429/cooldown UX so Realtime never stays visually active after backend blocks /start.
  // ORKIO_AO60K_HF1_RUNTIME_TIMEBOX_SYNC
  // Backend-returned timebox policy is the source of truth. This fixes cases where
  // the local cached user object temporarily looks like admin while the backend
  // correctly treats the session as public beta/non-admin.
  const rtcBackendTimeboxLimitedRef = useRef(false);
  const [rtcBackendTimeboxLimited, setRtcBackendTimeboxLimited] = useState(false);
  // AO01-HF6R16: backend-declared admin bypass is sovereign for frontend timebox/cooldown UI.
  const rtcAdminTimeboxBypassRef = useRef(false);
  const [rtcAdminTimeboxBypass, setRtcAdminTimeboxBypass] = useState(false);
  // PATCH0100_27_2B: UI log + punct status
  const [rtcAuditEvents, setRtcAuditEvents] = useState([]);
  const [rtcPunctStatus, setRtcPunctStatus] = useState(null); // null | 'pending' | 'done' | 'timeout'
  const [lastRealtimeSessionId, setLastRealtimeSessionId] = useState(null);
  const [summitSessionScore, setSummitSessionScore] = useState(null);
  const [summitReviewPending, setSummitReviewPending] = useState(false);
  // AO64D-HF1: Realtime transcript summary state/lifecycle extracted to a focused hook.
  const realtimeSummary = useRealtimeTranscriptSummary({
    logRealtimeStep,
    getSessionId: () => rtcSessionIdRef.current || lastRealtimeSessionId || null,
    getUserTextFallback: () => rtcLastFinalTranscriptRef.current,
    getAssistantTextFallback: () => rtcAssistantFinalTextRef.current,
    // AO64D-HF1A: keep PATCH 1 as summary-only. Do not inline to chat here.
    // Inline chat insertion needs a separate audited helper to avoid duplicate turns.
    appendSummaryToChat: null,
    inlineToChat: false,
    modalSuppressed: false,
  });
  const realtimeTranscriptSummary = realtimeSummary.summary;
  const realtimeTranscriptSummaryOpen = realtimeSummary.summaryOpen;
  const setRealtimeTranscriptSummaryOpen = realtimeSummary.setSummaryOpen;
  const realtimeTranscriptTurnsRef = realtimeSummary.turnsRef;
  const summitRuntimeModeRef = useRef((((window.__ORKIO_ENV__?.VITE_ORKIO_RUNTIME_MODE || import.meta.env.VITE_ORKIO_RUNTIME_MODE || "summit")).trim().toLowerCase() === "summit") ? "summit" : "platform");
  const summitLanguageProfileRef = useRef((((window.__ORKIO_ENV__?.VITE_SUMMIT_LANGUAGE_PROFILE || import.meta.env.VITE_SUMMIT_LANGUAGE_PROFILE || "pt-BR")).trim() || "auto"));
  const rtcLanguageProfileRef = useRef("auto");



// V2V-PATCH: trace_id por tentativa + status de fase + MediaRecorder
  const v2vTraceRef = useRef(null);

  // STREAM-STAB: anti-zombie (AbortController + runId)

// PATCH0113: Summit capacity modal (STREAM_LIMIT)
const [capacityOpen, setCapacityOpen] = React.useState(false);
const [capacitySeconds, setCapacitySeconds] = React.useState(30);
const capacityTimerRef = React.useRef(null);
const capacityPendingRef = React.useRef(null); // { msg }

const openCapacityModal = (msg, retryAfter = null) => {
  const parsedRetryAfter = Number.parseInt(String(retryAfter || ""), 10);
  const waitSeconds = Number.isFinite(parsedRetryAfter) && parsedRetryAfter > 0
    ? Math.min(300, parsedRetryAfter)
    : 30;

  setCapacityOpen(true);
  setCapacitySeconds(waitSeconds);
  capacityPendingRef.current = { msg: msg || "" };

  // EFATA777 v10.1: countdown is informational only.
  // Never auto-retry silently after 429; the user must trigger a retry explicitly.
  try { if (capacityTimerRef.current) clearInterval(capacityTimerRef.current); } catch {}
  capacityTimerRef.current = setInterval(() => {
    setCapacitySeconds((s) => {
      const next = Math.max(0, (s || 0) - 1);
      if (next === 0) {
        try { if (capacityTimerRef.current) clearInterval(capacityTimerRef.current); } catch {}
        capacityTimerRef.current = null;
      }
      return next;
    });
  }, 1000);
};

const closeCapacityModal = () => {
  setCapacityOpen(false);
  try { if (capacityTimerRef.current) clearInterval(capacityTimerRef.current); } catch {}
  capacityTimerRef.current = null;
};
  const streamCtlRef = useRef(null);
  const streamRunRef = useRef(0);

  const [v2vPhase, setV2vPhase] = useState(null); // null | 'recording' | 'stt' | 'chat' | 'tts' | 'playing' | 'error'
  const [v2vError, setV2vError] = useState(null);
  const [walletBlockedDetail, setWalletBlockedDetail] = useState(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  // BUG-02 FIX: flag para distinguir stop intencional (stopMicMediaRecorder)
  // de stop por VAD — evita processar áudio residual quando V2V é desligado
  const stopIntentionalRef = useRef(false);
  const [mediaRecorderSupported] = useState(!!(
    typeof window !== 'undefined' &&
    window.MediaRecorder &&
    navigator.mediaDevices?.getUserMedia
  ));

  
const BOOTSTRAP_FAILOPEN_MS = 3500;

useEffect(() => {
  if (onboardingChecked) {
    setBootstrapFailOpen(false);
    return undefined;
  }
  const timer = window.setTimeout(() => {
    try {
      console.warn("bootstrap fail-open triggered");
    } catch {}
    setBootstrapFailOpen(true);
    setOnboardingChecked(true);
  }, BOOTSTRAP_FAILOPEN_MS);
  return () => {
    try { window.clearTimeout(timer); } catch {}
  };
}, [onboardingChecked]);

useEffect(() => {
  let alive = true;

  async function bootstrapUser() {
    const t = getToken();
    const u = getUser();
    const org = getTenant() || "public";
    setToken(t);
    setTenant(org);
    setUser(u);

    if (!t) {
      nav("/auth");
      return;
    }

    try {
      const { data } = await apiFetch("/api/me", { method: "GET", token: t, org });
      if (!alive) return;
      if (data) {
        const mergedUser = {
          ...(u || {}),
          ...data,
          org_slug: data?.org_slug || u?.org_slug || org,
          role: data?.role || u?.role || "user",
          signup_source: data?.signup_source ?? u?.signup_source ?? null,
          signup_code_label: data?.signup_code_label ?? u?.signup_code_label ?? null,
          product_scope: data?.product_scope ?? u?.product_scope ?? null,
          country: data?.country ?? u?.country ?? null,
          language: data?.language ?? u?.language ?? null,
          whatsapp: data?.whatsapp ?? u?.whatsapp ?? null,
          is_admin: hasAdminAccess({
            ...(u || {}),
            ...data,
            role: data?.role || u?.role || "user",
            is_admin: data?.is_admin === true || u?.is_admin === true,
            admin: data?.admin === true || u?.admin === true,
          }),
        };
        mergedUser.admin = mergedUser.is_admin === true;

        setUser(mergedUser);
        try { setSession({ token: t, user: mergedUser, tenant: mergedUser.org_slug || org }); } catch {}

        const explicitPendingApproval = (
          mergedUser?.pending_approval === true
          || mergedUser?.auth_status === "pending_approval"
          || mergedUser?.status === "pending"
        );

        if (explicitPendingApproval) {
          clearSession();
          nav("/auth?pending_approval=1");
          return;
        }

        if (!mergedUser?.onboarding_completed) {
          setOnboardingForm(sanitizeOnboardingForm(mergedUser));
          // ORKIO_AO59B_MANDATORY_ONBOARDING_GATE
          // Onboarding is now a mandatory pre-chat activation step.
          setOnboardingOpen(true);
        }

        if (!mergedUser?.terms_accepted_at) {
          setShowTermsModal(true);
        }
      }
    } catch (err) {
      console.warn("bootstrapUser failed", err);
      if (err?.status === 401) {
        clearSession();
        nav("/auth?session_expired=1");
        return;
      }
    } finally {
      if (alive) setOnboardingChecked(true);
    }
  }

  bootstrapUser();
  return () => { alive = false; };
}, []);

  useEffect(() => {
    setWalletSummary(null);
    setWalletSummaryLoading(false);
    setWalletSummaryError("");
    return undefined;
  }, [token, tenant]);

  useEffect(() => {
    const onResize = () => {
      try { setIsMobile(window.innerWidth <= 820); } catch {}
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!isMobile) setMobileSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    if (SUMMIT_VOICE_MODE === "stt_tts") {
      setVoiceMode(true);
      voiceModeRef.current = true;
      if (realtimeModeRef.current) {
        try { void stopRealtime("voice_mode_lock"); } catch {}
        setRealtimeMode(false);
        realtimeModeRef.current = false;
      }
      return;
    }
    setVoiceMode(false);
    voiceModeRef.current = false;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        await apiFetch("/api/health", { token, org: tenant });
        if (!cancelled) setHealth("ok");
      } catch {
        if (!cancelled) setHealth("down");
      }
    }

    if (token) checkHealth();

    return () => {
      cancelled = true;
    };
  }, [token, tenant]);

  useEffect(() => {
    let cancelled = false;

    async function checkOrionSquadHealth() {
      if (!token || !showOrionSquad) {
        if (!cancelled) setOrionSquadHealth(null);
        return;
      }
      try {
        const resp = await getOrionSquadHealth({ token, org: tenant });
        if (!cancelled) setOrionSquadHealth(resp?.data || resp || null);
      } catch {
        if (!cancelled) setOrionSquadHealth({ ok: false });
      }
    }

    void checkOrionSquadHealth();

    return () => {
      cancelled = true;
    };
  }, [token, tenant, showOrionSquad]);

  async function refreshOrionSquadPreview(messageToPreview) {
    const previewMessage = String(messageToPreview || "").trim();
    if (!token || !showOrionSquad || !previewMessage) return;
    try {
      const resp = await getOrionSquadPreview({ token, org: tenant, message: previewMessage });
      setOrionSquadPreview(resp?.data || resp || null);
    } catch {
      // fail-open
    }
  }

  function scrollToBottom() {
    try {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch {}
  }

  useEffect(() => { scrollToBottom(); }, [messages]);

  const walletBalanceUsd = Number(walletSummary?.wallet?.balance_usd || 0);
  const walletLowBalanceThresholdUsd = Number(
    walletSummary?.wallet?.low_balance_threshold_usd
    ?? walletSummary?.wallet?.auto_recharge_threshold_usd
    ?? 3
  );
  const walletLowBalance = walletBalanceUsd <= walletLowBalanceThresholdUsd;
  const walletActivePlanName = walletSummary?.active_plan?.name || "";
  const walletAutoRechargeEnabled = !!walletSummary?.wallet?.auto_recharge_enabled;
  const walletSummaryUpdatedAt = walletSummary?.wallet?.updated_at || null;

  async function refreshWalletSummary() {
    setWalletSummary(null);
    setWalletSummaryLoading(false);
    setWalletSummaryError("");
    return null;
  }

  useEffect(() => {
    function onKeyDown(e) {
      if (!realtimeModeRef.current) return;
      if (!rtcReadyToRespond) return;
      // Don't hijack typing in inputs/textarea/contenteditable
      const el = document.activeElement;
      const tag = el?.tagName?.toLowerCase();
      const isTyping = tag === "input" || tag === "textarea" || el?.isContentEditable;
      if (isTyping) return;

      if (e.code === "Space" || e.key === " " || e.key === "Enter") {
        e.preventDefault();
        triggerRealtimeResponse("hotkey");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [rtcReadyToRespond]);
  useEffect(() => { messagesRef.current = orderChatMessages(messages || []); }, [messages]);

useEffect(() => {
  if (typeof window === "undefined" || !window.visualViewport) return undefined;
  const vv = window.visualViewport;
  const updateViewportOffset = () => {
    try {
      const keyboardOffset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      setComposerViewportOffset(keyboardOffset);
    } catch {
      setComposerViewportOffset(0);
    }
  };
  updateViewportOffset();
  vv.addEventListener("resize", updateViewportOffset);
  vv.addEventListener("scroll", updateViewportOffset);
  window.addEventListener("orientationchange", updateViewportOffset);
  return () => {
    vv.removeEventListener("resize", updateViewportOffset);
    vv.removeEventListener("scroll", updateViewportOffset);
    window.removeEventListener("orientationchange", updateViewportOffset);
  };
}, []);


  function activateThread(nextThreadId, opts = {}) {
    const nextId = String(nextThreadId || "");
    const { clearMessages = true, persist = true, lockMs = 15000 } = opts || {};
    activeThreadEpochRef.current += 1;
    streamRunRef.current += 1;
    try { streamCtlRef.current?.abort(); } catch {}
    activeThreadIdRef.current = nextId;
    requestedThreadIdRef.current = nextId;
    messagesLoadRequestRef.current += 1;
    consumeStoredThreadBootstrap(nextId);
    lockThreadSelection(nextId, lockMs);
    try { messagesAbortRef.current?.abort?.(); } catch {}
    messagesAbortRef.current = null;
    if (persist) {
      persistActiveThreadId(nextId);
    }
    if (clearMessages) {
      clearTmpAssistantDrafts();
      setMessages([]);
    }
    setThreadId((prev) => (String(prev || "") === nextId ? prev : nextId));
  }

  useEffect(() => {
    const safeThreadId = String(threadId || "");
    activeThreadIdRef.current = safeThreadId;
    if (safeThreadId) {
      persistActiveThreadId(safeThreadId);
    }
  }, [threadId]);

  useEffect(() => {
    if (!threadId) {
      const stored = getBootstrapStoredThreadId();
      if (stored) {
        activeThreadIdRef.current = stored;
        requestedThreadIdRef.current = stored;
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      try { messagesAbortRef.current?.abort?.(); } catch {}
      messagesAbortRef.current = null;
    };
  }, []);

  async function loadThreads(opts = {}) {
    try {
      const currentActive = String(activeThreadIdRef.current || threadId || "").trim();
      const explicitPreserveThreadId = String(
        opts?.preserveThreadId
        || currentActive
        || ""
      ).trim();
      const bootstrapThreadId = explicitPreserveThreadId ? "" : getBootstrapStoredThreadId();
      const preserveThreadId = String(explicitPreserveThreadId || bootstrapThreadId || "").trim();

      const { data } = await apiFetch("/api/threads", { token, org: tenant });
      const list = Array.isArray(data) ? data : [];
      setThreads(list);

      const hasPreserved = preserveThreadId && list.some((t) => String(t?.id || "") === preserveThreadId);
      const isLocked = threadSelectionLockUntilRef.current > Date.now();

      if (hasPreserved) {
        consumeStoredThreadBootstrap(preserveThreadId);
        if (String(activeThreadIdRef.current || "") !== preserveThreadId || String(threadId || "") !== preserveThreadId) {
          activateThread(preserveThreadId, { clearMessages: !opts?.keepMessages, persist: true, lockMs: isLocked ? Math.max(threadSelectionLockUntilRef.current - Date.now(), 1000) : 8000 });
        } else {
          persistActiveThreadId(preserveThreadId);
        }
        return list;
      }

      if (bootstrapThreadId) {
        consumeStoredThreadBootstrap("");
      }

      if (isLocked && preserveThreadId) {
        return list;
      }

      if (!currentActive && list?.[0]?.id) {
        activateThread(list[0].id, { clearMessages: true, persist: true, lockMs: 5000 });
        return list;
      }

      if (currentActive && !list.some((t) => String(t?.id || "") === currentActive)) {
        const fallbackId = String(list?.[0]?.id || "");
        if (fallbackId) {
          activateThread(fallbackId, { clearMessages: true, persist: true, lockMs: 5000 });
        } else {
          activateThread("", { clearMessages: true, persist: true, lockMs: 2000 });
        }
      }

      return list;
    } catch (e) {
      console.warn("loadThreads non-fatal error:", e);
      if (e?.status === 401) {
        await logoutIfSessionReallyExpired("loadThreads");
      }
      return [];
    }
  }

  async function loadMessages(tid, opts = {}) {
    const targetId = String(tid || "");
    if (!targetId) return [];
    const force = !!opts?.force;
    const expectedEpoch = Number.isFinite(Number(opts?.expectedEpoch))
      ? Number(opts.expectedEpoch)
      : activeThreadEpochRef.current;

    const currentActive = String(activeThreadIdRef.current || "");
    if (currentActive && targetId !== currentActive && !opts?.allowInactive) {
      return [];
    }

    const requestSeq = ++messagesLoadRequestRef.current;
    requestedThreadIdRef.current = targetId;

    let controller = null;
    try {
      if (!opts?.finalizeTurn && !opts?.preserveExistingRequest) {
        try { messagesAbortRef.current?.abort?.(); } catch {}
      }
      controller = (typeof AbortController !== "undefined") ? new AbortController() : null;
      messagesAbortRef.current = controller;

      const fetchOpts = { token, org: tenant };
      if (controller?.signal) fetchOpts.signal = controller.signal;

      const { data } = await apiFetch(
        `/api/messages?thread_id=${encodeURIComponent(targetId)}&include_welcome=0`,
        fetchOpts
      );

      const normalized = orderChatMessages(
        Array.isArray(data)
          ? data.map((item) => normalizeMessageSpeaker(item))
          : []
      );
      const sameRequest = requestSeq === messagesLoadRequestRef.current;
      const sameRequestedThread = requestedThreadIdRef.current === targetId;
      const sameActiveThread =
        String(activeThreadIdRef.current || "") === targetId;
      const sameEpoch = expectedEpoch === activeThreadEpochRef.current;
      const wasAborted = !!controller?.signal?.aborted;
      const finalizeTurn = !!opts?.finalizeTurn;
      const canApply =
        sameActiveThread &&
        !wasAborted &&
        (
          finalizeTurn ||
          (
            sameRequestedThread &&
            sameEpoch &&
            (force ? sameActiveThread : sameRequest)
          )
        );

      if (canApply) {
        setMessages(normalized);
      }
      return normalized;
    } catch (e) {
      if (e?.name !== "AbortError") {
        console.warn("loadMessages non-fatal error:", e);
        if (e?.status === 401) {
          await logoutIfSessionReallyExpired("loadMessages");
        }
      }
      return [];
    } finally {
      if (messagesAbortRef.current === controller) {
        messagesAbortRef.current = null;
      }
    }
  }

  async function finalizeChatTurn({
    threadId: turnThreadId,
    draftAssistantId,
    finalTextCandidate = "",
    finalAgentName = "Orkio",
    finalAgentId = null,
    finalVoiceId = null,
    finalAvatarUrl = null,
    turnStartedAt = 0,
  } = {}) {
    const tid = String(turnThreadId || "").trim();
    const finalText = String(finalTextCandidate || "").trim();
    const safeFinalText =
      finalText ||
      "Resposta concluída no backend. Atualizando histórico...";

    if (!tid) {
      setMessages((prev) => {
        const list = Array.isArray(prev) ? prev : [];
        let replaced = false;
        const next = list.map((m) => {
          if (String(m?.id || "") !== String(draftAssistantId || "")) return m;
          replaced = true;
          return {
            ...m,
            content: safeFinalText,
            agent_name: resolveAssistantDisplayName(
              { ...(m || {}), agent_name: m?.agent_name || finalAgentName || "Agent", content: safeFinalText },
              finalAgentName || "Agent"
            ),
            agent_id: m.agent_id || finalAgentId || null,
            voice_id: m.voice_id || finalVoiceId || null,
            avatar_url: m.avatar_url || finalAvatarUrl || null,
            finalized_locally: true,
          };
        });

        if (replaced) return next;

        const alreadyVisible = next.some((m) =>
          m?.role === "assistant" &&
          String(m?.content || "").trim() === safeFinalText
        );
        if (alreadyVisible) return next;

        return [
          ...next,
          {
            id: `stream-final-${Date.now()}`,
            role: "assistant",
            content: safeFinalText,
            agent_name: resolveAssistantDisplayName(
              { agent_name: finalAgentName || "Agent", content: safeFinalText },
              finalAgentName || "Agent"
            ),
            agent_id: finalAgentId || null,
            voice_id: finalVoiceId || null,
            avatar_url: finalAvatarUrl || null,
            finalized_locally: true,
            created_at: Math.floor(Date.now() / 1000),
          },
        ];
      });
      return [];
    }

    let fresh = [];
    const startedAt = Number(turnStartedAt || 0);
    for (let attempt = 0; attempt < CHAT_TURN_RECONCILE_ATTEMPTS; attempt += 1) {
      fresh = await loadMessages(tid, {
        force: true,
        allowInactive: true,
        finalizeTurn: true,
        preserveExistingRequest: true,
        expectedEpoch: activeThreadEpochRef.current,
      });

      const hasFreshAssistant = Array.isArray(fresh) && fresh.some((m) => {
        if (m?.role !== "assistant") return false;
        if (String(m?.id || "").startsWith("tmp-ass-")) return false;
        const createdAt = Number(m?.created_at || 0);
        if (!Number.isFinite(createdAt) || !startedAt) return true;
        return createdAt >= Math.max(0, startedAt - 2);
      });

      if (hasFreshAssistant) {
        return fresh;
      }

      await new Promise((resolve) => setTimeout(resolve, 450 + attempt * 450));
    }

    if (finalText) {
      setMessages((prev) => {
        const list = Array.isArray(prev) ? prev : [];
        const cleaned = list.filter((m) => String(m?.id || "") !== String(draftAssistantId || ""));

        const alreadyVisible = cleaned.some((m) =>
          m?.role === "assistant" &&
          String(m?.content || "").trim() === finalText
        );

        if (alreadyVisible) return cleaned;

        return [
          ...cleaned,
          {
            id: `stream-final-${Date.now()}`,
            role: "assistant",
            content: finalText,
            agent_name: resolveAssistantDisplayName({ agent_name: finalAgentName || "Agent", content: finalText }, finalAgentName || "Agent"),
            agent_id: finalAgentId || null,
            voice_id: finalVoiceId || null,
            avatar_url: finalAvatarUrl || null,
            created_at: Math.floor(Date.now() / 1000),
          },
        ];
      });
    } else {
      setMessages((prev) =>
        (Array.isArray(prev) ? prev : []).map((m) =>
          String(m?.id || "") === String(draftAssistantId || "")
            ? {
                ...m,
                content: safeFinalText,
                agent_name: resolveAssistantDisplayName({ ...(m || {}), agent_name: m?.agent_name || finalAgentName || "Agent", content: safeFinalText }, finalAgentName || "Agent"),
                agent_id: m.agent_id || finalAgentId || null,
                voice_id: m.voice_id || finalVoiceId || null,
                avatar_url: m.avatar_url || finalAvatarUrl || null,
                finalized_locally: true,
              }
            : m
        )
      );
    }

    return fresh;
  }

  function scheduleFinalTurnReconcile({ threadId: reconcileThreadId, turnStartedAt = 0, delayMs = 1200 } = {}) {
    const tid = String(reconcileThreadId || "").trim();
    if (!tid) return;
    window.setTimeout(() => {
      try {
        if (String(activeThreadIdRef.current || "") !== tid) return;
        void loadMessages(tid, {
          force: true,
          allowInactive: true,
          finalizeTurn: true,
          preserveExistingRequest: true,
          expectedEpoch: activeThreadEpochRef.current,
        }).then((fresh) => {
          if (hasPersistedAssistantForTurn(fresh, turnStartedAt)) {
            if (String(activeThreadIdRef.current || "") === tid) {
              setMessages(() => {
                const persisted = Array.isArray(fresh) ? fresh : [];
                if (!persisted.length) return persisted;
                return persisted.filter((m) => !String(m?.id || "").startsWith("tmp-ass-"));
              });
            }
            appendExecutionTrace({
              kind: "done",
              label: "Histórico reconciliado",
              detail: "A resposta persistida foi sincronizada no App Console sem exigir refresh manual.",
            });
          }
        });
      } catch {}
    }, Math.max(300, Number(delayMs || 1200)));
  }


  async function loadAgents() {
    try {
      const { data } = await apiFetch("/api/agents", { token, org: tenant });
      setAgents(data || []);
      try {
        const m = new Map();
        (data || []).forEach(a => { if (a?.name) m.set(String(a.name).trim(), a.id); });
        agentsByNameRef.current = m;
      } catch {}

      // Preserve the last manually selected agent when it still exists.
      // Do not force the console back to single-agent mode during agent reloads.
      if (Array.isArray(data) && data.length) {
        const orkio = data.find(a => (a.name || "").toLowerCase() === "orkio") || data.find(a => a.is_default) || data[0] || null;

        const currentExists = destSingle && data.some((a) => String(a.id) === String(destSingle));
        if (!currentExists) {
          const remembered = (typeof window !== "undefined" && window.localStorage?.getItem("orkio_last_dest_single")) || "";
          const rememberedAgent = remembered ? data.find((a) => String(a.id) === String(remembered)) : null;
          const nextAgent = rememberedAgent || orkio || null;
          if (nextAgent) setDestSingle(nextAgent.id);
        }

        setDestMulti((prev) => {
          const cleanPrev = Array.isArray(prev) ? prev.map((v) => String(v || "").trim()).filter(Boolean) : [];
          const valid = cleanPrev.filter((id) => data.some((a) => String(a.id) === String(id)));
          if (valid.length) return Array.from(new Set(valid));
          try {
            const raw = (typeof window !== "undefined" && window.localStorage?.getItem("orkio_last_dest_multi")) || "[]";
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
              const restored = parsed
                .map((v) => String(v || "").trim())
                .filter((id) => id && data.some((a) => String(a.id) === String(id)));
              if (restored.length) return Array.from(new Set(restored));
            }
          } catch {}
          return valid;
        });

        setDestMode((prev) => {
          const normalized = ["team", "single", "multi"].includes(String(prev || "").trim().toLowerCase())
            ? String(prev || "").trim().toLowerCase()
            : "team";
          if (normalized === "single" && !currentExists && !orkio) return "team";
          return normalized;
        });
      }
    } catch (e) {
      console.error("loadAgents error:", e);
    }
  }

  useEffect(() => {
    if (!token || !onboardingChecked || onboardingOpen) return;
    loadThreads();
    loadAgents();
  }, [token, tenant, onboardingChecked, onboardingOpen]);

  useEffect(() => {
    const currentThreadId = String(threadId || "");
    if (!currentThreadId) {
      setMessages([]);
      return;
    }
    const epochAtEffect = activeThreadEpochRef.current;
    clearTmpAssistantDrafts();
    setMessages([]);
    void loadMessages(currentThreadId, { force: true, expectedEpoch: epochAtEffect });
  }, [threadId]);






  async function createThread() {
    try {
      const { data } = await apiFetch("/api/threads", {
        method: "POST",
        token,
        org: tenant,
        body: { title: "Nova conversa" },
      });
      if (data?.id) {
        const newId = String(data.id || "");
        consumeStoredThreadBootstrap(newId);
        activateThread(newId, { clearMessages: true, persist: true, lockMs: 20000 });
        setThreads((prev) => {
          const list = Array.isArray(prev) ? prev.filter((t) => String(t?.id || "") !== newId) : [];
          return [{ ...(data || {}), id: newId }, ...list];
        });
        await loadThreads({ preserveThreadId: newId, keepMessages: true });
        if (String(activeThreadIdRef.current || "") === newId) {
          await loadMessages(newId, { force: true, expectedEpoch: activeThreadEpochRef.current });
        }
      }
    } catch (e) {
      alert(e?.message || "Falha ao criar conversa");
    }
  }

  async function deleteThread(threadId) {
    if (!threadId) return;
    if (!confirm('Deletar esta conversa?')) return;
    try {
      await apiFetch(`/api/threads/${encodeURIComponent(threadId)}`, {
        method: "DELETE",
        token,
        org: tenant,
      });
      // Reload threads and pick a safe next one
      const { data } = await apiFetch("/api/threads", { token, org: tenant });
      const list = data || [];
      setThreads(list);
      const nextId = list?.[0]?.id || "";
      if (nextId) {
        activateThread(nextId, { clearMessages: true, persist: true, lockMs: 10000 });
        await loadMessages(nextId, { force: true, expectedEpoch: activeThreadEpochRef.current });
      } else {
        consumeStoredThreadBootstrap("");
        activateThread("", { clearMessages: true, persist: true, lockMs: 3000 });
      }
    } catch (e) {
      console.error("deleteThread error:", e);
      alert(e?.message || "Falha ao deletar conversa");
    }
  }

  async function renameThread(tid) {
    const t = threads.find((x) => x.id === tid);
    const current = t?.title || "Nova conversa";
    const next = prompt("Renomear conversa:", current);
    if (!next) return;
    try {
      await apiFetch(`/api/threads/${encodeURIComponent(tid)}`, {
        method: "PATCH",
        token,
        org: tenant,
        body: { title: next },
      });
      await loadThreads({ preserveThreadId: String(activeThreadIdRef.current || threadId || "") });
    } catch (e) {
      alert(e?.message || "Falha ao renomear");
    }
  }

  async function doLogout() {
    try {
      await logout({ org: tenant, token });
    } finally {
      clearSession();
      nav("/auth");
    }
  }

function sanitizePublicAgentText(value = "") {
  return String(value || "")
    .replace(/\b(gpt[-_\s]?\d+(?:\.\d+)?|gpt|openai|claude|anthropic|gemini|llama|mistral|deepseek|reasoning|premium_reasoning|premium_reasoning_cto|model|llm)\b/gi, "")
    .replace(/\s*[·|/,-]\s*$/g, "")
    .replace(/^[\s·|/,-]+/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function getPublicAgentRole(agent = {}) {
  const raw =
    agent.public_role ||
    agent.publicRole ||
    agent.role_label ||
    agent.roleLabel ||
    agent.function ||
    agent.title ||
    agent.role ||
    "";

  const cleaned = sanitizePublicAgentText(raw);

  if (!cleaned || /^agente$/i.test(cleaned)) {
    const id = String(agent.id || agent.name || "").toLowerCase();
    if (id.includes("orion")) return "Auditor técnico";
    if (id.includes("chris")) return "Estratégia e negócios";
    if (id.includes("orkio")) return "Assistente principal";
    if (id.includes("team")) return "Equipe multiagente";
    return "Agente especialista";
  }

  return cleaned;
}

function formatPublicAgentLabel(agent = {}) {
  const name = sanitizePublicAgentText(agent.name || agent.label || agent.id || "Agente") || "Agente";
  const role = getPublicAgentRole(agent);
  if (!role || role.toLowerCase() === name.toLowerCase()) return name;
  return `${name} · ${role}`;
}

function formatAgentOptionLabel(agent) {
  return formatPublicAgentLabel(agent);
}


  function extractMentionNamesFromText(raw) {
    try {
      const text = String(raw || "");
      const matches = text.matchAll(/@([A-Za-z0-9_\-/]+(?:\s+[A-Za-z0-9_\-/]+){0,2})(?=(?:\s*[,.:;!?])|(?:\s+@)|$)/gi);
      const out = [];
      const seen = new Set();
      for (const match of matches) {
        const name = String(match?.[1] || "").trim();
        const key = name.toLowerCase();
        if (!name || seen.has(key)) continue;
        seen.add(key);
        out.push(name);
      }
      return out;
    } catch {
      return [];
    }
  }

  function buildMessagePrefix(rawMessage = "") {
    const userMentions = extractMentionNamesFromText(rawMessage);
    // EFATA777_DESTINATION_CONTRACT_V1:
    // If the user typed an explicit mention, do not add a synthetic @Team/@Agent
    // prefix. The canonical payload below is now the source of truth.
    if (userMentions.length) return "";
    if (destMode === "team") return "";
    if (destMode === "single") {
      const ag = agents.find((a) => String(a.id) === String(destSingle));
      return ag ? `@${ag.name} ` : "";
    }
    if (destMode === "multi") {
      const names = agents
        .filter((a) => destMulti.includes(String(a.id)))
        .map((a) => a.name)
        .filter(Boolean);
      if (!names.length) return "";
      return names.map((n) => `@${n}`).join(" ") + " ";
    }
    return "";
  }

  function buildDestinationContract(rawMessage = "", hostAgentId = null) {
    const mode = ["team", "single", "multi"].includes(String(destMode || "").toLowerCase())
      ? String(destMode || "team").toLowerCase()
      : "team";
    const singleAgent = agents.find((a) => String(a.id) === String(destSingle)) || null;
    const multiIds = Array.isArray(destMulti)
      ? Array.from(new Set(destMulti.map((id) => String(id || "").trim()).filter(Boolean)))
      : [];
    const mentionedNames = extractMentionNamesFromText(rawMessage);
    return {
      dest_mode: mode,
      agent_id: hostAgentId || null,
      agent_ids: mode === "multi" ? multiIds : [],
      target_agent_slug: mode === "single" ? String(destSingle || "") : null,
      visible_agent: mode === "single" ? String(singleAgent?.name || "") : "",
      requested_agent_names: mentionedNames,
    };
  }

  function resolveHostAgentId(modeOverride = null) {
    // ORKIO_AO60F_REALTIME_ORKIO_ONLY_IDENTITY_GUARD
    const namedOrkio =
      agents.find((a) => (a?.name || "").toLowerCase() === "orkio") ||
      agents.find((a) => (a?.slug || "").toLowerCase() === "orkio") ||
      agents.find((a) => (a?.key || "").toLowerCase() === "orkio") ||
      null;
    const fallbackAgent = namedOrkio || agents.find((a) => a?.is_default) || agents[0] || null;
    if (publicBetaOrkioOnly) {
      return namedOrkio?.id || null;
    }

    const mode = String(modeOverride || destMode || "team").trim().toLowerCase();

    if (mode === "single") {
      return destSingle || fallbackAgent?.id || null;
    }

    if (mode === "multi") {
      const selected = agents.filter((a) => destMulti.includes(String(a?.id || "")));
      if (selected.length === 1) {
        return selected[0]?.id || fallbackAgent?.id || null;
      }
      return fallbackAgent?.id || null;
    }

    return fallbackAgent?.id || null;
  }


  function appendToPlaceholder(delta) {
    if (!delta) return;

    setMessages((prev) => {
      const messages = Array.isArray(prev) ? [...prev] : [];

      for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i];

        if (
          m?.role === "assistant" &&
          String(m?.id || "").startsWith("tmp-ass-")
        ) {
          const oldContent =
            m.content === "⌛ Preparando resposta..."
              ? ""
              : (m.content || "");

          messages[i] = {
            ...m,
            content: oldContent + delta,
          };

          return messages;
        }
      }

      messages.push({
        id: `tmp-ass-${Date.now()}`,
        role: "assistant",
        content: delta,
        agent_name: "Orkio",
        created_at: Math.floor(Date.now() / 1000),
      });

      return messages;
    });
  }

  function clearTmpAssistantDrafts() {
    setMessages((prev) => (Array.isArray(prev)
      ? prev.filter((m) => !String(m?.id || "").startsWith("tmp-ass-"))
      : []));
  }

  function hasPersistedAssistantForTurn(freshMessages, turnStartedAt) {
    const list = Array.isArray(freshMessages) ? freshMessages : [];
    return list.some((m) => {
      if (m?.role !== "assistant") return false;
      if (String(m?.id || "").startsWith("tmp-ass-")) return false;
      const createdAt = Number(m?.created_at || 0);
      return Number.isFinite(createdAt) && createdAt >= Math.max(0, Number(turnStartedAt || 0) - 2);
    });
  }

  function resolveDoneFinalText(payload = {}, draftText = "") {
    const finalText = String(
      payload?.final_text ||
      payload?.message ||
      payload?.content ||
      draftText ||
      ""
    ).trim();

    if (finalText) return finalText;
    if (payload?.assistant_persisted) {
      return "Resposta concluída no backend. Sincronizando histórico...";
    }
    return "";
  }

  
  function fillPremiumPrompt(promptText) {
    const next = String(promptText || "").trim();
    if (!next) return;
    setText(next);
    try { window.requestAnimationFrame(() => textareaRef.current?.focus?.()); } catch {}
  }

  function handlePremiumPrimaryAction() { void sendMessage("Orkio, me ajuda a montar um plano de testes para liberar a plataforma para 5 usuários beta?"); }

  function handlePremiumSecondaryAction() {
    if (publicBetaOrkioOnly) {
      fillPremiumPrompt("Orkio, mapeie a oportunidade de maior impacto e menor risco para esta fase do meu negócio.");
      return;
    }
    fillPremiumPrompt("@Team mapeiem a oportunidade de maior impacto e menor risco para esta fase da plataforma.");
    try { setUploadStatus("Revise o pedido antes de acionar o Team. O modo multiagente está em estabilização."); setTimeout(() => setUploadStatus(""), 4200); } catch {}
  }

  function handlePremiumTertiaryAction() { fillPremiumPrompt("Orkio, organize um plano prático para eu testar a plataforma hoje com foco em impacto real e baixo risco."); }

function openPatchApprovalModal(message) {
    const meta = extractPatchGovernanceMeta(message?.content || "");
    if (!meta?.can_approve) return;
    setPatchApprovalError("");
    setPatchApprovalPassword("");
    setPatchApprovalModal({
      message_id: message?.id || null,
      thread_id: message?.thread_id || activeThreadIdRef.current || threadId || "",
      audit_receipt_id: meta.audit_receipt_id,
    });
  }

  async function submitPatchApproval() {
    const modal = patchApprovalModal || {};
    const approvalThreadId = String(modal.thread_id || activeThreadIdRef.current || threadId || "").trim();
    const password = String(patchApprovalPassword || "");
    if (!approvalThreadId) {
      setPatchApprovalError("Thread não encontrada para aprovação.");
      return;
    }
    if (!password) {
      setPatchApprovalError("Digite sua senha para confirmar.");
      return;
    }
    setPatchApprovalBusy(true);
    setPatchApprovalError("");
    try {
      const { data } = await apiFetch("/api/governance/approve-patch", {
        method: "POST",
        token,
        org: tenant,
        body: {
          thread_id: approvalThreadId,
          audit_receipt_id: modal.audit_receipt_id || undefined,
          password,
          auto_execute: false,
        },
      });
      const responseText = String(data?.message || "PATCH APPROVAL RESPONSE\n\n- status: approval_registered").trim();
      setMessages((prev) => [
        ...(Array.isArray(prev) ? prev : []),
        {
          id: `patch-approval-${Date.now()}`,
          role: "assistant",
          content: responseText,
          agent_name: canSeeInternalOrionSpeaker() ? "Orion" : "Orkio",
          agent_id: canSeeInternalOrionSpeaker() ? "orion" : "orkio",
          created_at: Math.floor(Date.now() / 1000),
        },
      ]);
      setPatchApprovalModal(null);
      setPatchApprovalPassword("");
      try { await loadMessages(approvalThreadId, { force: true, allowInactive: true, finalizeTurn: true }); } catch {}
    } catch (err) {
      setPatchApprovalError(err?.message || "Falha ao aprovar patch.");
    } finally {
      setPatchApprovalBusy(false);
    }
  }

  async function executeApprovedPatchFromMessage(message) {
    const approvalMeta = extractPatchApprovalMeta(message?.content || "");
    const approvalThreadId = String(message?.thread_id || activeThreadIdRef.current || threadId || "").trim();
    if (!approvalMeta?.can_execute || !approvalThreadId) return;
    try {
      setUploadStatus("⌛ Executando fluxo governado aprovado...");
      const { data } = await apiFetch("/api/governance/execute-approved-patch", {
        method: "POST",
        token,
        org: tenant,
        body: {
          thread_id: approvalThreadId,
          audit_receipt_id: approvalMeta.audit_receipt_id || undefined,
          dry_run: false,
        },
      });
      const responseText = String(data?.message || "GOVERNED PATCH EXECUTION RESPONSE\n\n- status: execution_request_finished").trim();
      setMessages((prev) => [
        ...(Array.isArray(prev) ? prev : []),
        {
          id: `patch-exec-${Date.now()}`,
          role: "assistant",
          content: responseText,
          agent_name: canSeeInternalOrionSpeaker() ? "Orion" : "Orkio",
          agent_id: canSeeInternalOrionSpeaker() ? "orion" : "orkio",
          created_at: Math.floor(Date.now() / 1000),
        },
      ]);
      try { await loadMessages(approvalThreadId, { force: true, allowInactive: true, finalizeTurn: true }); } catch {}
    } catch (err) {
      const responseText = `GOVERNED PATCH EXECUTION RESPONSE\n\n- status: execution_request_failed\n- detail: ${String(err?.message || "falha desconhecida")}`;
      setMessages((prev) => [
        ...(Array.isArray(prev) ? prev : []),
        {
          id: `patch-exec-error-${Date.now()}`,
          role: "assistant",
          content: responseText,
          agent_name: canSeeInternalOrionSpeaker() ? "Orion" : "Orkio",
          agent_id: canSeeInternalOrionSpeaker() ? "orion" : "orkio",
          created_at: Math.floor(Date.now() / 1000),
        },
      ]);
    } finally {
      setUploadStatus("");
      setSending(false);
      sendingRef.current = false;
    }
  }


async function sendMessage(presetMsg = null, opts = {}) {
    const isRetry = !!opts?.isRetry;
    clearRealtimeIdleFollowup();
    const msg = ((presetMsg ?? text) || "").trim();
    if (!msg || sendingRef.current) return;

    const pendingApprovedExecution = findPendingApprovedPatchExecution(messagesRef.current || messages);
    if (pendingApprovedExecution) {
      const guidance = buildPendingExecutionGuidance();
      setText("");
      setUploadStatus("⚠️ Execução aprovada pendente — use o botão governado.");
      setMessages((prev) => [
        ...(Array.isArray(prev) ? prev : []),
        {
          id: `patch-execution-pending-${Date.now()}`,
          role: "assistant",
          content: guidance,
          agent_name: canSeeInternalOrionSpeaker() ? "Orion" : "Orkio",
          agent_id: canSeeInternalOrionSpeaker() ? "orion" : "orkio",
          created_at: Math.floor(Date.now() / 1000),
        },
      ]);
      try {
        const target = pendingApprovedExecution?.message;
        if (target) setTimeout(() => {
          try {
            document.querySelector('[data-patch-execute-button="true"]')?.scrollIntoView({ behavior: "smooth", block: "center" });
          } catch {}
        }, 80);
      } catch {}
      return;
    }

    const turnStartedAt = Math.floor(Date.now() / 1000);
    sendingRef.current = true;
    setSending(true);

    // STREAM-STAB: start new run and abort any previous stream
    streamRunRef.current += 1;
    const myRun = streamRunRef.current;
    try { streamCtlRef.current?.abort(); } catch {}
    const ctl = new AbortController();
    streamCtlRef.current = ctl;
    const isStale = () => (myRun !== streamRunRef.current || ctl.signal.aborted);

    // UX: show progress while waiting
    try { setUploadStatus('⌛ Gerando resposta...'); } catch {}

    // AO20K-HF4G_FRONTEND_STREAM_TERMINAL_GUARD
    // Estes ids precisam existir também nos catches/finally. Antes ficavam
    // declarados dentro do try, mas alguns caminhos de erro usam draftAssistantId
    // fora daquele bloco.
    let optimisticUserId = "";
    let draftAssistantId = "";
    let traceId = "";
    let clientMessageId = "";

    try {
      const agentIdToSend = resolveHostAgentId(); // host agent depends on current routing mode
      if (publicBetaOrkioOnly) {
        logRealtimeStep("start:orkio_only_agent_guard", { agent_id: agentIdToSend || null });
      }
      const pref = buildMessagePrefix(msg);
      const finalMsg = pref + msg;
      const destinationContract = buildDestinationContract(msg, agentIdToSend);
      void refreshOrionSquadPreview(finalMsg);

      const describeDirectRailError = (err) => {
        if (err?.code === "CHAT_DIRECT_TIMEOUT") return "O fallback direto excedeu o tempo limite e foi abortado.";
        if (err?.code === "NETWORK_FETCH_FAILED") return "Falha de rede ao executar a resposta direta.";
        if (err?.code === "FETCH_ABORTED") return "A resposta direta foi abortada antes da conclusão.";
        return err?.message || "Não foi possível concluir a resposta direta.";
      };

      const failStreamWithoutDirectFallback = (reason = "CHAT_STREAM_FAILED_NO_DIRECT_FALLBACK") => {
        const err = new Error(reason);
        err.code = reason;
        appendExecutionTrace({
          kind: "error",
          label: "Stream não estabilizou",
          detail: "O trilho direto /api/chat está desativado neste deploy porque fica pendente em provisional headers. A UI liberou o input sem travar.",
        });
        setMessages((prev) => (Array.isArray(prev) ? prev : []).map((m) => (
          m.id === draftAssistantId
            ? {
                ...m,
                content: "Não consegui concluir a resposta pelo stream nesta tentativa. A tentativa foi encerrada com segurança; tente novamente.",
                agent_name: "Orkio",
              }
            : m
        )));
        throw err;
      };

      const runDirectChat = async () => {
        const directCtl = new AbortController();
        streamCtlRef.current = directCtl;

        let timeoutId = null;
        try {
          timeoutId = window.setTimeout(() => {
            try {
              directCtl.abort();
            } catch {}
          }, Math.min(CHAT_STREAM_TIMEOUT_MS, 20000));

          return await chat({
            token,
            org: tenant,
            thread_id: threadId,
            message: finalMsg,
            agent_id: destinationContract.agent_id,
            trace_id: traceId,
            client_message_id: clientMessageId,
            agent_ids: destinationContract.agent_ids,
            dest_mode: destinationContract.dest_mode,
            visible_agent: destinationContract.visible_agent,
            target_agent_slug: destinationContract.target_agent_slug,
            requested_agent_names: destinationContract.requested_agent_names,
            signal: directCtl.signal,
          });
        } catch (err) {
          if (directCtl.signal.aborted) {
            const wrapped = err instanceof Error ? err : new Error(String(err || "CHAT_DIRECT_TIMEOUT"));
            wrapped.code = "CHAT_DIRECT_TIMEOUT";
            wrapped.wasAborted = true;
            throw wrapped;
          }
          throw err;
        } finally {
          if (timeoutId) window.clearTimeout(timeoutId);
        }
      };


      optimisticUserId = `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      draftAssistantId = `tmp-ass-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const optimisticBaseTime = Date.now();

      const initialDraftAgentName = resolveAssistantDisplayName(
        {
          agent_name: destinationContract.visible_agent || activeRuntimeAgent || (destMode === "team" ? "Orkio" : ""),
          content: finalMsg,
        },
        destMode === "team" ? "Orkio" : "Agent"
      );

      // optimistic message
      if (!isRetry) {
        setMessages((prev) => [
          ...prev,
          {
            id: optimisticUserId,
            role: "user",
            content: msg,
            user_name: user?.name || user?.email,
            created_at: optimisticBaseTime,
            client_created_at: optimisticBaseTime,
            client_order: optimisticBaseTime,
          },
          {
            id: draftAssistantId,
            role: "assistant",
            content: "⌛ Preparando resposta...",
            agent_name: initialDraftAgentName,
            created_at: optimisticBaseTime + 1,
            client_created_at: optimisticBaseTime + 1,
            client_order: optimisticBaseTime + 1,
          },
        ]);
        setText("");
      }

      // V2V-PATCH: gerar trace_id por tentativa de V2V (correlaciona logs backend)
      traceId = `v2v-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      clientMessageId = (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID() : (`cm-${Date.now()}-${Math.random().toString(36).slice(2,10)}`);
      v2vTraceRef.current = traceId;
      setV2vPhase('chat');
      setV2vError(null);
      setWalletBlockedDetail(null);
      setExecutionTraceExpanded(true);
      try { window.localStorage?.setItem("orkio_execution_trace_open", "1"); } catch {}
      setActiveRuntimeAgent("Orkio");
      setRuntimeHandoffLabel("");
      resetExecutionTrace([
        {
          kind: "system",
          label: "Solicitação recebida",
          detail: publicBetaOrkioOnly
            ? "Orkio preparado para o beta público."
            : destMode === "team"
            ? "Modo Team acionado."
            : destMode === "multi"
            ? "Execução multiagente preparada."
            : agentIdToSend
            ? "Agente definido para esta execução."
            : "Roteamento automático preparado.",
        },
        {
          kind: "status",
          label: "Enviando para o runtime dOrkio",
          detail: ORKIO_CHAT_STREAM_PRIMARY
            ? "Aguardando resposta do stream principal."
            : "Aguardando resposta do trilho direto com timeout controlado.",
        },
      ]);

      // v4: SSE becomes the primary chat rail, with JSON fallback preserved.
      let resp = null;
      let newThreadId = threadId;
      let streamDonePayload = null;
      let streamMeta = null;

      if (ORKIO_CHAT_STREAM_PRIMARY) {
        try {
          appendExecutionTrace({
            kind: "system",
            label: "Stream principal acionado",
            detail: "Enviando via /api/chat/stream.",
          });

          try {
            console.info("ORKIO_CHAT_STREAM_DISPATCH", { traceId, threadId, destMode: destinationContract.dest_mode });
          } catch {}

          const streamResp = await withTimeout(chatStream({
            token,
            org: tenant,
            thread_id: threadId,
            message: finalMsg,
            agent_id: destinationContract.agent_id,
            trace_id: traceId,
            client_message_id: clientMessageId,
            agent_ids: destinationContract.agent_ids,
            dest_mode: destinationContract.dest_mode,
            visible_agent: destinationContract.visible_agent,
            target_agent_slug: destinationContract.target_agent_slug,
            requested_agent_names: destinationContract.requested_agent_names,
            signal: ctl.signal,
          }), CHAT_STREAM_CONNECT_TIMEOUT_MS, "CHAT_STREAM_CONNECT_TIMEOUT");
          streamMeta = await withTimeout(consumeChatStream(streamResp, {
            signal: ctl.signal,
            isStale,
            onStatus: (payload) => {
              if (isStale()) return;
              if (payload?.status) setUploadStatus(`⌛ ${payload.status}`);
              if (payload?.agent_name || payload?.final_speaker || payload?.visible_agent) setActiveRuntimeAgent(resolveAssistantDisplayName(payload, activeRuntimeAgent || "Agent"));
              appendExecutionTrace(describeExecutionStatus(payload));
            },
            onError: (payload) => {
              if (isStale()) return;
              appendExecutionTrace(describeExecutionError(payload));
              if (payload?.code === "WALLET_INSUFFICIENT_BALANCE") {
                setWalletBlockedDetail(payload);
                setV2vError(buildWalletBlockedMessage(payload));
                return;
              }
              if (payload?.agent_id && payload?.code !== "SERVER_BUSY") return;
              if (payload?.message) setV2vError(String(payload.message));
            },
            onExecution: (payload) => {
              if (isStale()) return;
              if (payload?.step === "agent_handoff") {
                const handoff = `${payload?.from_agent_name || payload?.from_agent_id || "Agente"} → ${payload?.to_agent_name || payload?.agent_name || payload?.to_agent_id || "Agente"}`;
                setRuntimeHandoffLabel(handoff);
                setActiveRuntimeAgent(payload?.to_agent_name || payload?.agent_name || "");
              } else if (payload?.agent_name) {
                setActiveRuntimeAgent(payload.agent_name);
              }
              appendExecutionTrace(describeExecutionEvent(payload));
            },
            onChunk: (payload, draftText) => {
              if (isStale()) return;
              setMessages((prev) => prev.map((m) => (
                m.id === draftAssistantId
                  ? {
                      ...m,
                      content: draftText || "⌛ Preparando resposta...",
                      agent_name: resolveAssistantDisplayName(
                        { ...(m || {}), ...(payload || {}), content: draftText || payload?.content || m?.content || "" },
                        m?.agent_name || "Agent"
                      ),
                      agent_id: payload?.agent_id || m.agent_id || null,
                      voice_id: payload?.voice_id || m.voice_id || null,
                      avatar_url: payload?.avatar_url || m.avatar_url || null,
                    }
                  : m
              )));
            },
            onAgentDone: (payload) => {
              if (isStale()) return;
              if (payload?.agent_name || payload?.final_speaker || payload?.visible_agent) setActiveRuntimeAgent(resolveAssistantDisplayName(payload, activeRuntimeAgent || "Agent"));
              appendExecutionTrace({
                kind: "agent",
                label: `${resolveAssistantDisplayName(payload, payload?.agent_id || "Agent")} concluiu uma etapa`,
                detail: payload?.message || payload?.status || "Resposta parcial pronta.",
                agentName: payload?.agent_name || "",
              });
              setMessages((prev) => prev.map((m) => (
                m.id === draftAssistantId
                  ? {
                      ...m,
                      content: (m.content || "").replace(/^⌛\s*/, "") || "Resposta concluída.",
                      agent_name: resolveAssistantDisplayName(
                        { ...(m || {}), ...(payload || {}), content: m?.content || payload?.content || "" },
                        m?.agent_name || "Agent"
                      ),
                      agent_id: payload?.agent_id || m.agent_id || null,
                      voice_id: payload?.voice_id || m.voice_id || null,
                      avatar_url: payload?.avatar_url || m.avatar_url || null,
                    }
                  : m
              )));
            },
            onKeepalive: () => {},
            onDone: (payload) => {
              if (isStale()) return;
              streamDonePayload = payload || null;
              appendExecutionTrace(describeExecutionDone(payload));
              if (payload?.thread_id) newThreadId = payload.thread_id;
              if (payload?.runtime_hints) {
                setRuntimeHints(payload.runtime_hints);
                if (payload.runtime_hints?.capabilities) {
                  setAgentCapabilities(normalizeCapabilityPayload(payload.runtime_hints.capabilities));
                }
              }
              if (payload?.trace_id) setLastTraceId(payload.trace_id);
              if (payload?.agent_name || payload?.final_speaker || payload?.visible_agent) {
                setActiveRuntimeAgent(resolveAssistantDisplayName(payload, activeRuntimeAgent || "Agent"));
              }

              const doneFinalText = resolveDoneFinalText(payload, "");
              if (doneFinalText || payload?.assistant_persisted || payload?.done) {
                setMessages((prev) => prev.map((m) => (
                  m.id === draftAssistantId
                    ? {
                        ...m,
                        content: doneFinalText || String(m?.content || "").replace(/^⌛\s*/, "") || "Resposta concluída.",
                        agent_name: resolveAssistantDisplayName(
                          { ...(m || {}), ...(payload || {}), content: doneFinalText || m?.content || "" },
                          m?.agent_name || "Agent"
                        ),
                        agent_id: payload?.agent_id || m.agent_id || null,
                        voice_id: payload?.voice_id || m.voice_id || null,
                        avatar_url: payload?.avatar_url || m.avatar_url || null,
                        assistant_message_id: payload?.assistant_message_id || m?.assistant_message_id || null,
                      }
                    : m
                )));
              }

              try { setUploadStatus(""); } catch {}
              setSending(false);
              sendingRef.current = false;
              setV2vPhase(null);
              setV2vError(null);
              setRuntimeHandoffLabel("");
              collapseExecutionTrace();
            },
          }), CHAT_STREAM_TIMEOUT_MS, "CHAT_STREAM_TIMEOUT");
          if (isStale()) return;
          resp = {
            data: {
              thread_id: streamMeta?.thread_id || newThreadId,
              used_stream: true,
              runtime_hints: streamMeta?.runtime_hints || null,
              trace_id: streamMeta?.trace_id || traceId,
              execution_cursor: streamMeta?.execution_cursor || null,
              execution_lifecycle: streamMeta?.execution_lifecycle || null,
              routing_source: streamMeta?.routing_source || null,
              route_applied: !!streamMeta?.route_applied,
            }
          };
          if (streamMeta?.thread_id) newThreadId = streamMeta.thread_id;
        } catch (streamErr) {
          if (
            streamErr?.code === "CHAT_STREAM_ENDED_WITHOUT_DONE" ||
            streamErr?.code === "CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT" ||
            streamErr?.code === "CHAT_STREAM_NO_ACTIVITY_TIMEOUT"
          ) {
            appendExecutionTrace({
              kind: "warning",
              label: "Stream encerrado com segurança",
              detail: streamErr?.code || "frontend_stream_terminal_guard",
            });
            setMessages((prev) =>
              (Array.isArray(prev) ? prev : []).map((m) =>
                m.id === draftAssistantId
                  ? {
                      ...m,
                      content:
                        streamErr?.draftText ||
                        "Não consegui concluir a resposta pelo stream nesta tentativa. A tentativa foi encerrada com segurança; tente novamente.",
                      agent_name: m.agent_name || "Orkio",
                    }
                  : m
              )
            );
            streamDonePayload = {
              thread_id: streamErr?.thread_id || newThreadId || threadId,
              trace_id: streamErr?.trace_id || traceId,
              stream_failed: true,
              frontend_stream_guard: true,
              reason: streamErr?.code || "frontend_stream_terminal_guard",
            };
            streamMeta = {
              thread_id: streamDonePayload.thread_id,
              trace_id: streamDonePayload.trace_id,
              used_stream: true,
              done_payload: streamDonePayload,
              draft_text: streamErr?.draftText || "",
            };
            try { setUploadStatus(""); } catch {}
            setSending(false);
            sendingRef.current = false;
            setV2vPhase(null);
            setV2vError(null);
            setRuntimeHandoffLabel("");
            collapseExecutionTrace();
            return;
          }

          if (streamErr instanceof StreamSemanticError) {
            appendExecutionTrace({
              kind: "warning",
              label: "Stream retornou erro semântico",
              detail: streamErr?.payload?.message || streamErr?.message || "Acionando recuperação pelo trilho direto.",
            });
          }

          if (isAbortLikeError(streamErr)) {
            try { ctl.abort(); } catch {}
            appendExecutionTrace({
              kind: "system",
              label: streamErr?.code === "CHAT_STREAM_TIMEOUT" || streamErr?.code === "STREAM_TIMEOUT"
                ? "Stream demorou demais"
                : "Stream interrompido",
              detail: "Tentando reconciliar a resposta persistida antes de acionar a resposta direta.",
            });

            const reconcileThreadId = String(newThreadId || threadId || "").trim();
            let reconciledMessages = [];
            if (reconcileThreadId) {
              try {
                reconciledMessages = await loadMessages(reconcileThreadId, {
                  force: true,
                  allowInactive: true,
                  finalizeTurn: true,
                  preserveExistingRequest: true,
                  expectedEpoch: activeThreadEpochRef.current,
                });
              } catch {}
            }

            if (hasPersistedAssistantForTurn(reconciledMessages, turnStartedAt)) {
              appendExecutionTrace({
                kind: "done",
                label: "Histórico reconciliado",
                detail: "A resposta persistida foi localizada após a degradação do stream.",
              });
              try { setUploadStatus(""); } catch {}
              setSending(false);
              sendingRef.current = false;
              setV2vPhase(null);
              setV2vError(null);
              setRuntimeHandoffLabel("");
              collapseExecutionTrace();
              resp = {
                data: {
                  thread_id: reconcileThreadId || newThreadId || threadId,
                  used_stream: true,
                  degraded_stream: true,
                  reconciled_after_stream_abort: true,
                  trace_id: traceId,
                },
              };
            } else {
              if (!ORKIO_CHAT_DIRECT_FALLBACK_ENABLED) {
                failStreamWithoutDirectFallback("CHAT_STREAM_FAILED_NO_DIRECT_FALLBACK");
              }
              appendExecutionTrace({
                kind: "system",
                label: "Alternando para resposta direta",
                detail: "O histórico ainda não tinha resposta persistida. Orkio vai tentar /api/chat com timeout controlado.",
              });
              try {
                resp = await runDirectChat();
              } catch (fallbackErr) {
                appendExecutionTrace({
                  kind: "error",
                  label: "Fallback direto falhou",
                  detail: describeDirectRailError(fallbackErr),
                });
                throw fallbackErr;
              }
            }
          } else if (streamErr?.status === 429 || streamErr?.code === "RATE_LIMITED" || streamErr?.isRateLimited) {
            appendExecutionTrace({
              kind: "warning",
              label: "Capacidade temporariamente atingida",
              detail: "O stream retornou 429. Orkio não acionou fallback duplicado; tente novamente em alguns instantes.",
            });
            setMessages((prev) =>
              (Array.isArray(prev) ? prev : []).map((m) =>
                m.id === draftAssistantId
                  ? {
                      ...m,
                      content: "Capacidade temporariamente atingida. Tente novamente em instantes.",
                      agent_name: "Orkio",
                    }
                  : m
              )
            );
            setV2vPhase(null);
            setV2vError(null);
            closeCapacityModal();
            openCapacityModal(msg, streamErr?.retryAfter || null);
            return;
          } else if (
            streamErr?.status === 401 ||
            streamErr?.status === 403 ||
            streamErr?.isAuthError ||
            streamErr?.code === "CHAT_STREAM_UNAUTHORIZED" ||
            streamErr?.code === "AUTH_SESSION_EXPIRED" ||
            streamErr?.code === "AUTH_FORBIDDEN"
          ) {
            appendExecutionTrace({
              kind: "warning",
              label: streamErr?.status === 403 ? "Acesso negado neste fluxo" : "Sessão expirada ou inconsistente",
              detail: streamErr?.status === 403
                ? "Orkio não acionou fallback duplicado após 403."
                : "Orkio não acionou fallback duplicado após 401. Validando a sessão atual.",
            });
            setMessages((prev) =>
              (Array.isArray(prev) ? prev : []).map((m) =>
                m.id === draftAssistantId
                  ? {
                      ...m,
                      content: streamErr?.status === 403
                        ? "Seu acesso foi negado para esta execução. Revise a sessão e tente novamente."
                        : "Sessão expirada ou inconsistente. Entre novamente para continuar.",
                      agent_name: "Orkio",
                    }
                  : m
              )
            );
            if (streamErr?.status === 403) {
              setV2vPhase("error");
              setV2vError("Acesso negado para esta execução.");
              return;
            }
            const expired = await logoutIfSessionReallyExpired("chatStream401");
            if (!expired) {
              setV2vPhase(null);
              setV2vError("Sessão oscilou. Tente enviar novamente.");
            }
            return;
          } else {
            if (!ORKIO_CHAT_DIRECT_FALLBACK_ENABLED) {
              failStreamWithoutDirectFallback("CHAT_STREAM_DEGRADED_NO_DIRECT_FALLBACK");
            }
            appendExecutionTrace({
              kind: "system",
              label: "Alternando para resposta direta",
              detail: "O stream foi degradado. Orkio vai tentar /api/chat com timeout controlado.",
            });
            try {
              resp = await runDirectChat();
            } catch (fallbackErr) {
              appendExecutionTrace({
                kind: "error",
                label: "Fallback direto falhou",
                detail: describeDirectRailError(fallbackErr),
              });
              throw fallbackErr;
            }
          }
        }

      } else {
        if (!ORKIO_CHAT_DIRECT_FALLBACK_ENABLED) {
          failStreamWithoutDirectFallback("CHAT_STREAM_PRIMARY_DISABLED_DIRECT_FALLBACK_DISABLED");
        }
        try {
          appendExecutionTrace({
            kind: "system",
            label: "Trilho direto acionado",
            detail: "Enviando via /api/chat com timeout e abort controlados.",
          });
          resp = await runDirectChat();
        } catch (directErr) {
          appendExecutionTrace({
            kind: "error",
            label: "Execução direta falhou",
            detail: describeDirectRailError(directErr),
          });
          throw directErr;
        }
      }

      if (resp?.status === 429) {
        appendExecutionTrace({
          kind: "warning",
          label: "Capacidade temporariamente atingida",
          detail: "A resposta direta retornou 429. O usuário pode tentar novamente em instantes.",
        });
        setMessages((prev) =>
          (Array.isArray(prev) ? prev : []).map((m) =>
            m.id === draftAssistantId
              ? {
                  ...m,
                  content: "Capacidade temporariamente atingida. Tente novamente em instantes.",
                  agent_name: "Orkio",
                }
              : m
          )
        );
        setV2vPhase(null);
        setV2vError(null);
        closeCapacityModal();
        openCapacityModal(msg, resp?.headers?.get?.("retry-after") || null);
        return;
      }

       // V2V-PATCH: se fallback /api/chat criou thread, capturar thread_id do resp
       if (resp?.data?.thread_id) newThreadId = resp.data.thread_id;
      // F-03 FIX: usar newThreadId (var local) em vez de threadId (closure stale do React)
      // Se a conversa foi criada durante o SSE stream, threadId ainda aponta para a thread antiga
      const effectiveTidForLoad = String(newThreadId || threadId || "");

      const finalTextCandidate = String(
        streamDonePayload?.final_text ||
        streamDonePayload?.message ||
        streamDonePayload?.content ||
        streamMeta?.done_payload?.final_text ||
        streamMeta?.done_payload?.message ||
        streamMeta?.done_payload?.content ||
        streamMeta?.draft_text ||
        ""
      ).trim();

      const finalAgentName = resolveAssistantDisplayName(
        {
          ...(streamMeta?.done_payload || {}),
          ...(streamDonePayload || {}),
          runtime_hints:
            streamDonePayload?.runtime_hints ||
            streamMeta?.runtime_hints ||
            streamMeta?.done_payload?.runtime_hints ||
            null,
        },
        streamDonePayload?.agent_name || streamMeta?.done_payload?.agent_name || "Orkio"
      );
      const finalAgentId =
        streamDonePayload?.agent_id ||
        streamMeta?.done_payload?.agent_id ||
        null;
      const finalVoiceId =
        streamDonePayload?.voice_id ||
        streamMeta?.done_payload?.voice_id ||
        null;
      const finalAvatarUrl =
        streamDonePayload?.avatar_url ||
        streamMeta?.done_payload?.avatar_url ||
        null;

      if (effectiveTidForLoad) {
        consumeStoredThreadBootstrap(effectiveTidForLoad);
        const currentActiveForFinalize = String(activeThreadIdRef.current || "");
        // AO01_THREAD_FOCUS_GUARD:
        // Uma finalização atrasada de stream não pode roubar o foco
        // quando o usuário já selecionou manualmente outra conversa.
        if (effectiveTidForLoad === currentActiveForFinalize) {
          activeThreadIdRef.current = effectiveTidForLoad;
          requestedThreadIdRef.current = effectiveTidForLoad;
          persistActiveThreadId(effectiveTidForLoad);
          lockThreadSelection(effectiveTidForLoad, 20000);
        }
      }

      // EFATA777 v9:
      // Finalize the visible turn before refreshing the thread sidebar. A slow
      // /api/threads or an epoch/abort race cannot block the assistant answer.
      const freshMessages = effectiveTidForLoad
        ? await finalizeChatTurn({
            threadId: effectiveTidForLoad,
            draftAssistantId,
            finalTextCandidate,
            finalAgentName,
            finalAgentId,
            finalVoiceId,
            finalAvatarUrl,
            turnStartedAt,
          })
        : await finalizeChatTurn({
            threadId: "",
            draftAssistantId,
            finalTextCandidate,
            finalAgentName,
            finalAgentId,
            finalVoiceId,
            finalAvatarUrl,
            turnStartedAt,
          });

      const doneAssistantMessageId = String(
        streamDonePayload?.assistant_message_id ||
        streamMeta?.done_payload?.assistant_message_id ||
        ""
      ).trim();

      const freshHasDoneAssistantId = !!doneAssistantMessageId && (Array.isArray(freshMessages) ? freshMessages : []).some((m) => (
        String(m?.id || "") === doneAssistantMessageId ||
        String(m?.assistant_message_id || "") === doneAssistantMessageId
      ));

      const freshHasAssistant = freshHasDoneAssistantId || hasPersistedAssistantForTurn(freshMessages, turnStartedAt);

      // AO-28_STREAM_DRAFT_RECONCILE_GUARD
      // When the stream already produced a final visible answer but /api/messages
      // is still behind, keep the streamed draft visible until the next reconcile.
      if (!freshHasAssistant && finalTextCandidate) {
        setMessages((prev) => {
          const list = Array.isArray(prev) ? [...prev] : [];

          const alreadyHasPersisted = !!doneAssistantMessageId && list.some((m) => (
            String(m?.id || "") === doneAssistantMessageId ||
            String(m?.assistant_message_id || "") === doneAssistantMessageId
          ));

          if (alreadyHasPersisted) return list;

          const draftIdx = list.findIndex((m) => (
            String(m?.id || "") === String(draftAssistantId || "") ||
            (!!doneAssistantMessageId && String(m?.assistant_message_id || "") === doneAssistantMessageId)
          ));

          const preservedDraft = {
            id: draftAssistantId || `tmp-ass-${Date.now()}`,
            role: "assistant",
            content: finalTextCandidate,
            agent_name: finalAgentName || "Orkio",
            agent_id: finalAgentId || null,
            voice_id: finalVoiceId || null,
            avatar_url: finalAvatarUrl || null,
            thread_id: effectiveTidForLoad || threadId || activeThreadIdRef.current || "",
            assistant_message_id: doneAssistantMessageId || null,
            created_at: Math.floor(Date.now() / 1000),
            stream_reconcile_pending: true,
          };

          if (draftIdx >= 0) {
            list[draftIdx] = {
              ...list[draftIdx],
              ...preservedDraft,
              content: finalTextCandidate || list[draftIdx]?.content || "",
            };
            return list;
          }

          return [...list, preservedDraft];
        });
      }

      if (!freshHasAssistant && effectiveTidForLoad) {
        scheduleFinalTurnReconcile({
          threadId: effectiveTidForLoad,
          turnStartedAt,
          delayMs: 1200,
        });
      }

      if (effectiveTidForLoad) {
        void loadThreads({ preserveThreadId: effectiveTidForLoad, keepMessages: true });
      }

      void refreshWalletSummary({ silent: true });

      // PATCH0100_14: store agent info from response
      if (resp?.data) {
        const ai = { agent_id: resp.data.agent_id, agent_name: resp.data.agent_name, voice_id: resolveAgentVoice({ agent_name: resp.data.agent_name, voice_id: resp.data.voice_id }), avatar_url: resp.data.avatar_url };
        setLastAgentInfo(ai);
        if (resp.data.agent_name) setActiveRuntimeAgent(resp.data.agent_name);
        if (resp.data.runtime_hints) {
          setRuntimeHints(resp.data.runtime_hints || null);
          if (resp.data.runtime_hints?.capabilities) {
            setAgentCapabilities(normalizeCapabilityPayload(resp.data.runtime_hints.capabilities));
          }
        }
        if (resp.data.trace_id) setLastTraceId(resp.data.trace_id);
        if (!resp?.data?.used_stream) {
          appendExecutionTrace({
            kind: "agent",
            label: `${resp.data.agent_name || "Orkio"} consolidou a resposta`,
            detail: resp.data.runtime_hints?.routing?.mode ? `modo ${resp.data.runtime_hints.routing.mode}` : "",
            agentName: resp.data.agent_name || "",
          });
          appendExecutionTrace({
            kind: "done",
            label: "Execução concluída",
            detail: buildExecutionDoneDetail({ runtime_hints: resp.data.runtime_hints || null }),
          });
        }
      }
      // V2V-PATCH: Auto-play TTS — fase TTS + fase playing com trace_id
      if (voiceModeRef.current) {
        if (micEnabledRef.current) stopMic();
        const prevLast = messagesRef.current?.slice?.().reverse?.().find?.(m => m.role === "assistant" && !String(m?.id||"").startsWith("tmp-ass-"))?.created_at || null;
        const fresh = (freshMessages || []);
        const assistants = (fresh || []).filter(m => m.role === "assistant" && !String(m.id || "").startsWith("tmp-ass-"));
        let toSpeak = assistants;
        if (prevLast) {
          // F-04: epoch Unix (segundos) → ms para JS
          const prevT = new Date((prevLast || 0) * 1000).getTime();
          toSpeak = assistants.filter(m => {
            const t = new Date((m.created_at || 0) * 1000).getTime();
            // BUG-03 FIX: filtro estrito (>) — não incluir a msg anterior (prevT)
            return isFinite(t) && t > prevT;
          });
        } else {
          toSpeak = assistants.slice(-1);
        }

        // Team: fala cada mensagem sequencialmente com voz correta por agente
        // Single: só a última
        if (destMode !== "team" && toSpeak.length > 1) toSpeak = toSpeak.slice(-1);

        const currentTrace = v2vTraceRef.current || traceId;
        const shouldAutoSpeakThisTurn =
          !!opts?.explicitVoiceRequested ||
          !!opts?.voiceRequested ||
          !!opts?.realtimeTurn;

        for (const m of toSpeak) {
          const content = (m.content || "").trim();
          if (!content) continue;
          if (!shouldAutoSpeakThisTurn) continue;
          const agentIdFallback = m.agent_id || null;
          // preferir message_id (backend resolve voz); agent_id só como fallback
          setV2vPhase('tts');
          try { setUploadStatus(`🔊 Gerando voz (${m.agent_name || 'agente'})...`); } catch {}
          await playTts(content, agentIdFallback, {
            forceAuto: true,
            messageId: m.id || null,
            traceId: currentTrace,
          });
        }
        setV2vPhase(null);
        setV2vError(null);
        // BUG-01 FIX: fallback — se playTts não reiniciou o mic (ex: autoplay bloqueado)
        // garantir que o ciclo V2V continua ouvindo
        if (voiceModeRef.current && !micEnabledRef.current) {
          scheduleMicRestart("post-tts");
        }
      }

    } catch (e) {
      if (isStale()) return;
      console.error("[V2V] sendMessage error:", e);
      if (
        e?.code === "CHAT_STREAM_ENDED_WITHOUT_DONE" ||
        e?.code === "CHAT_STREAM_NO_USEFUL_CHUNK_TIMEOUT" ||
        e?.code === "CHAT_STREAM_NO_ACTIVITY_TIMEOUT"
      ) {
        appendExecutionTrace({
          kind: "warning",
          label: "Stream finalizado sem confirmação",
          detail: e?.code || "frontend_stream_terminal_guard",
        });
        setMessages((prev) =>
          (Array.isArray(prev) ? prev : []).map((m) =>
            m.id === draftAssistantId
              ? {
                  ...m,
                  content:
                    e?.draftText ||
                    "Não consegui concluir a resposta pelo stream nesta tentativa. A tentativa foi encerrada com segurança; tente novamente.",
                  agent_name: m.agent_name || "Orkio",
                }
              : m
          )
        );
        setV2vPhase(null);
        setV2vError(null);
        return;
      }
      if (e?.status === 401) {
        const expired = await logoutIfSessionReallyExpired("sendMessage");
        if (expired) {
          setSending(false);
          return;
        }
      }
      if (isAbortLikeError(e)) {
        appendExecutionTrace({
          kind: "system",
          label: "Stream interrompido",
          detail: "Tentando sincronizar a resposta persistida.",
        });
        const effectiveTidForLoad = String(threadId || activeThreadIdRef.current || "");
        if (effectiveTidForLoad) {
          await finalizeChatTurn({
            threadId: effectiveTidForLoad,
            draftAssistantId,
            finalTextCandidate: "",
            finalAgentName: resolveAssistantDisplayName({ agent_name: activeRuntimeAgent }, "Orkio"),
            turnStartedAt,
          });
        }
        setV2vPhase(null);
        setV2vError(null);
        return;
      }
      if (
        e?.code === "CHAT_STREAM_FAILED_NO_DIRECT_FALLBACK" ||
        e?.code === "CHAT_STREAM_DEGRADED_NO_DIRECT_FALLBACK" ||
        e?.code === "CHAT_STREAM_PRIMARY_DISABLED_DIRECT_FALLBACK_DISABLED"
      ) {
        setV2vPhase("error");
        setV2vError("Stream não estabilizou e o fallback direto não estava disponível neste build.");
        return;
      }
      if (e?.status === 429 || e?.code === "RATE_LIMITED" || e?.isRateLimited) {
        appendExecutionTrace({
          kind: "warning",
          label: "Capacidade temporariamente atingida",
          detail: "A execução foi limitada temporariamente. Nenhum fallback duplicado foi acionado.",
        });
        setMessages((prev) =>
          (Array.isArray(prev) ? prev : []).map((m) =>
            m.id === draftAssistantId
              ? {
                  ...m,
                  content: "Capacidade temporariamente atingida. Tente novamente em instantes.",
                  agent_name: "Orkio",
                }
              : m
          )
        );
        closeCapacityModal();
        openCapacityModal(msg, e?.retryAfter || null);
        setV2vPhase(null);
        setV2vError(null);
        return;
      }
      setV2vPhase('error');
      const walletDetail = normalizeWalletErrorPayload(e);
      if (walletDetail || isWalletBlockedError(e)) {
        const detail = walletDetail || { code: "WALLET_INSUFFICIENT_BALANCE" };
        appendExecutionTrace({
          kind: "error",
          label: "Wallet bloqueou a execução",
          detail: buildWalletBlockedMessage(detail),
        });
        setWalletBlockedDetail(detail);
        setV2vError(buildWalletBlockedMessage(detail));
        setMessages((prev) => prev.map((m) => (
          m.id === draftAssistantId
            ? {
                ...m,
                content: buildWalletBlockedMessage(detail),
                agent_name: m.agent_name || "Wallet",
              }
            : m
        )));
        void refreshWalletSummary({ silent: false });
      } else {
        setWalletBlockedDetail(null);
        appendExecutionTrace({
          kind: "error",
          label: "Execução falhou",
          detail: e?.message || "Falha ao enviar mensagem",
        });
        // BUG-04 FIX: trocar alert() por setV2vError — alert() bloqueia JS thread
        // e impede o V2V de reiniciar o microfone
        setV2vError(normalizeUserFacingRuntimeMessage(e?.message || "Falha ao enviar mensagem"));
      }
    } finally {
      const stillCurrentTurn =
        streamCtlRef.current === ctl ||
        myRun === streamRunRef.current;

      if (stillCurrentTurn || sendingRef.current) {
        sendingRef.current = false;
        setSending(false);
        try { setUploadStatus(''); } catch {}
      }
      if (streamCtlRef.current === ctl) {
        streamCtlRef.current = null;
      }
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  // Voice recognition helpers
  function ensureSpeech() {
    if (!speechSupported) return null;
    if (speechRef.current) return speechRef.current;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const rec = new SR();
    rec.lang = SPEECH_RECOGNITION_LANG;
    rec.interimResults = true;
    rec.continuous = true;
    speechRef.current = rec;
    return rec;
  }

  function stopMic() {
    micEnabledRef.current = false;
    setMicEnabled(false);
    if (micRestartTimeoutRef.current) {
      clearTimeout(micRestartTimeoutRef.current);
      micRestartTimeoutRef.current = null;
    }
    // V2V-PATCH: parar MediaRecorder se ativo
    stopMicMediaRecorder();
    // parar SpeechRecognition se ativo
    const rec = speechRef.current;
    if (rec) {
      try { rec.onend = null; rec.stop(); } catch {}
    }
  }

  function clearMediaRecorderTimers() {
    if (mediaRecorderSilenceIntervalRef.current) {
      clearInterval(mediaRecorderSilenceIntervalRef.current);
      mediaRecorderSilenceIntervalRef.current = null;
    }
    if (mediaRecorderSilenceTimeoutRef.current) {
      clearTimeout(mediaRecorderSilenceTimeoutRef.current);
      mediaRecorderSilenceTimeoutRef.current = null;
    }
  }

  function scheduleMicRestart(reason = "unknown", delay = 300) {
    if (!voiceModeRef.current || micEnabledRef.current) return;
    if (micRestartTimeoutRef.current) clearTimeout(micRestartTimeoutRef.current);
    micRestartTimeoutRef.current = setTimeout(() => {
      micRestartTimeoutRef.current = null;
      if (!voiceModeRef.current || micEnabledRef.current) return;
      console.info('[V2V] mic restart reason=%s', reason);
      startMic();
    }, Math.max(0, Number(delay) || 0));
  }

  function resolveSttLanguage() {
    const explicit = (
      window.__ORKIO_ENV__?.VITE_STT_LANGUAGE ||
      window.__ORKIO_ENV__?.VITE_REALTIME_TRANSCRIBE_LANGUAGE ||
      import.meta.env.VITE_STT_LANGUAGE ||
      import.meta.env.VITE_REALTIME_TRANSCRIBE_LANGUAGE ||
      ""
    ).trim();
    if (explicit) return explicit;
    return voiceModeRef.current ? "pt" : null;
  }

  // V2V-PATCH: startMic usa MediaRecorder (webm/opus) quando disponível.
  // MediaRecorder → /api/stt (Whisper) → texto → sendMessage()
  // Fallback: SpeechRecognition (Chrome-only) → texto → sendMessage()
  function startMic() {
    if (micRestartTimeoutRef.current) {
      clearTimeout(micRestartTimeoutRef.current);
      micRestartTimeoutRef.current = null;
    }
    clearMediaRecorderTimers();
    micEnabledRef.current = true;
    setMicEnabled(true);
    setV2vError(null);

    // ── Caminho 1: MediaRecorder (todos os browsers modernos, qualidade superior) ──
    if (mediaRecorderSupported && voiceModeRef.current) {
      navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        .then(stream => {
          if (!micEnabledRef.current) {
            stream.getTracks().forEach(t => t.stop());
            return;
          }
          mediaRecorderStreamRef.current = stream;

          const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4');

          const mr = new MediaRecorder(stream, { mimeType });
          mediaRecorderRef.current = mr;
          audioChunksRef.current = [];

          mr.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
          };

          mr.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            // BUG-02 FIX: stop intencional (stopMicMediaRecorder) → descartar chunks
            if (stopIntentionalRef.current) {
              stopIntentionalRef.current = false;
              audioChunksRef.current = [];
              return;
            }
            if (!micEnabledRef.current && !voiceModeRef.current) return;

            const chunks = audioChunksRef.current;
            audioChunksRef.current = [];
            if (!chunks.length) return;

            const blob = new Blob(chunks, { type: mimeType });
            if (blob.size < 500) {
              console.warn('[V2V] áudio muito curto, ignorando');
              return;
            }

            const trace = `v2v-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
            v2vTraceRef.current = trace;
            setV2vPhase('stt');
            setUploadStatus('🎙️ Transcrevendo fala...');

            console.info('[V2V] v2v_record_received trace_id=%s size=%d', trace, blob.size);

            try {
              const sttLang = resolveSttLanguage();
              const result = await transcribeAudio(blob, { token, org: tenant, trace_id: trace, language: sttLang || null });
              const text = (result?.text || '').trim();
              console.info('[V2V] v2v_stt_ok trace_id=%s chars=%d preview=%s', trace, text.length, text.slice(0, 60));

              if (!text) {
                console.warn('[V2V] v2v_stt_fail trace_id=%s reason=empty_transcript', trace);
                setV2vPhase('error');
                setV2vError('Nenhum texto reconhecido. Fale novamente.');
                setUploadStatus('⚠️ Fala não reconhecida. Tente novamente.');
                setTimeout(() => setUploadStatus(''), 2500);
                // Reiniciar escuta
                if (micEnabledRef.current && voiceModeRef.current) {
                  scheduleMicRestart('empty_transcript', 800);
                }
                return;
              }

              setText(text);
              setV2vPhase('chat');
              setUploadStatus(`🎙️ "${text.slice(0, 50)}${text.length > 50 ? '…' : ''}"`);

              if (voiceModeRef.current && micEnabledRef.current) {
                micEnabledRef.current = false;
                setMicEnabled(false);
                // pequeno delay para garantir que o texto aparece no input
                setTimeout(() => sendMessage(), 80);
              }
            } catch (e) {
              console.error('[V2V] v2v_stt_fail trace_id=%s error:', trace, e);
              setV2vPhase('error');
              setV2vError(normalizeUserFacingRuntimeMessage(e?.message || "erro desconhecido", "voice"));
              setUploadStatus(`❌ STT: ${e?.message || 'Erro de transcrição'}`);
              setTimeout(() => setUploadStatus(''), 3000);
            }
          };

          // Gravar em segmentos de 4s — silêncio detectado por VAD simples (tamanho do chunk)
          mr.start(100); // PATCH0100_24D: smaller chunks for better VAD // coleta chunks a cada 4s

          // Auto-stop após 30s máximo ou quando detectar silêncio
          let silenceTimer = null;
          let lastSize = 0;

          // PATCH0100_24D: VAD menos agressivo (1.5s de silêncio consecutivo)
          let consecutiveSilences = 0;

          mediaRecorderSilenceIntervalRef.current = setInterval(() => {
            const currentSize = audioChunksRef.current.reduce((s, c) => s + c.size, 0);
            const delta = currentSize - lastSize;
            lastSize = currentSize;

            // Espera acumular um mínimo de áudio e só encerra após 3 janelas silenciosas (~1.5s)
            if (currentSize > 3000 && delta < 500) {
              consecutiveSilences += 1;
            } else {
              consecutiveSilences = 0;
            }

            if (consecutiveSilences >= 3) {
              clearMediaRecorderTimers();
              
              try { mr.stop(); } catch {}
            }
          }, 500);

          silenceTimer = setTimeout(() => {
            clearMediaRecorderTimers();
            if (mr.state === 'recording') {
              try { mr.stop(); } catch {}
            }
          }, 30000);

          mr.onerror = (e) => {
            clearMediaRecorderTimers();
            clearTimeout(silenceTimer);
            console.error('[V2V] MediaRecorder error:', e);
            micEnabledRef.current = false;
            setMicEnabled(false);
            setV2vPhase('error');
            setV2vError('Erro no microfone. Verifique permissões.');
          };
        })
        .catch(err => {
          console.warn('[V2V] getUserMedia falhou, fallback SpeechRecognition:', err?.message);
          micEnabledRef.current = false;
          setMicEnabled(false);
          // fallback para SpeechRecognition
          _startSpeechRecognition();
        });
      return;
    }

    // ── Caminho 2: SpeechRecognition (fallback Chrome/Edge) ──
    _startSpeechRecognition();
  }

  function stopMicMediaRecorder() {
    // PATCH0100_24D: não zerar chunks antes do onstop (race condition)
    // BUG-02 FIX: sinalizar stop intencional para que onstop descarte os chunks
    stopIntentionalRef.current = true;
    clearMediaRecorderTimers();
    const mr = mediaRecorderRef.current;
    mediaRecorderRef.current = null;

    const stream = mediaRecorderStreamRef.current;
    mediaRecorderStreamRef.current = null;
    if (stream) {
      try { stream.getTracks().forEach(t => t.stop()); } catch {}
    }

    // NÃO limpar audioChunksRef aqui: o handler onstop consome os chunks.
    if (mr && mr.state === 'recording') {
      try { mr.stop(); } catch {}
    }
  }

  function _startSpeechRecognition() {
    const rec = ensureSpeech();
    if (!rec) {
      setV2vError('Microfone não disponível neste browser. Use Chrome ou ative permissões.');
      micEnabledRef.current = false;
      setMicEnabled(false);
      return;
    }

    let finalText = "";
    let autoSendTimer = null;
    rec.onresult = (evt) => {
      let interim = "";
      for (let i = evt.resultIndex; i < evt.results.length; i++) {
        const transcript = evt.results[i][0].transcript;
        if (evt.results[i].isFinal) finalText += transcript;
        else interim += transcript;
      }
      const merged = (finalText || interim || "").trim();
      if (merged) setText(merged);

      if (voiceModeRef.current && finalText.trim()) {
        if (autoSendTimer) clearTimeout(autoSendTimer);
        autoSendTimer = setTimeout(() => {
          const toSend = finalText.trim();
          if (toSend && voiceModeRef.current) {
            finalText = "";
            try { rec.stop(); } catch {}
            micEnabledRef.current = false;
            setMicEnabled(false);
            sendMessage();
          }
        }, 1500);
      }
    };

    rec.onerror = () => { /* keep enabled; onend will handle retry */ };

    rec.onend = () => {
      if (!micEnabledRef.current) return;
      const now = Date.now();
      const st = micRetryRef.current;
      if (now - st.lastTry > 20000) { st.tries = 0; }
      st.lastTry = now;
      st.tries += 1;
      if (st.tries > 3) {
        micEnabledRef.current = false;
        setMicEnabled(false);
        setUploadStatus("Microfone pausou. Clique no 🎙️ para retomar.");
        setTimeout(() => setUploadStatus(""), 2500);
        return;
      }
      setTimeout(() => {
        if (micEnabledRef.current) { try { rec.start(); } catch {} }
      }, 300);
    };

    try { rec.start(); } catch {}
  }

  function toggleMic() {
    if (!speechSupported) return;
    if (micEnabled) stopMic();
    else startMic();
  }

  // PATCH0100_13: Voice Mode helpers
  function toggleVoiceMode() {
    if (SUMMIT_VOICE_MODE !== "stt_tts") return;
    const next = !voiceMode;
    if (next && realtimeModeRef.current) {
      void stopRealtime('voice_mode_selected');
      setRealtimeMode(false);
      realtimeModeRef.current = false;
    }
    setVoiceMode(next);
    voiceModeRef.current = next;
    if (next) {
      setV2vPhase(null);
      setV2vError(null);
      const canRecord = mediaRecorderSupported;
      if (canRecord && !micEnabled) startMic();
      const modeLabel = 'MediaRecorder + STT';
      setUploadStatus(`Voice mode active (${modeLabel}) — speak naturally and Orkio will answer out loud.`);
      setTimeout(() => setUploadStatus(''), 4000);
    } else {
      if (micEnabled) stopMic();
      stopTts();
      setV2vPhase(null);
      setV2vError(null);
      setUploadStatus('');
    }
  }



function inferInterestType(raw) {
  const s = (raw || "").toLowerCase();
  if (/(invest|aportar|aporte|funding|investor)/i.test(s)) return "investor";
  if (/(comprar|contratar|adquirir|saas|demo|pricing|plan|plano)/i.test(s)) return "sales";
  if (/(parceria|partner|partnership)/i.test(s)) return "partnership";
  return "general";
}

function buildFounderHandoffMessage() {
  const draft = (text || "").trim();
  if (draft) return draft;
  const lastUser = [...(messagesRef.current || [])].reverse().find((m) => m?.role === "user" && (m?.content || "").trim());
  return (lastUser?.content || "The user would like to speak with Daniel about a strategic opportunity.").trim();
}

function handleFounderHandoff() {
  const message = buildFounderHandoffMessage();
  if (!message || handoffBusy) return;
  setHandoffDraft(message);
  setHandoffInterestType(inferInterestType(message));
  setShowHandoffModal(true);
}

async function confirmFounderHandoff() {
  const message = (handoffDraft || buildFounderHandoffMessage()).trim();
  if (!message || handoffBusy) return;
  setHandoffBusy(true);
  setHandoffNotice("");
  try {
    await requestFounderHandoff({
      token,
      org: tenant,
      thread_id: threadId || null,
      interest_type: handoffInterestType || inferInterestType(message),
      message,
      source: "app_console",
      consent_contact: true,
    });
    setShowHandoffModal(false);
    setHandoffDraft("");
    setHandoffNotice("Founder follow-up requested. Daniel will review the context and continue with the right next step.");
    setTimeout(() => setHandoffNotice(""), 6000);
  } catch (e) {
    const detail = typeof e?.message === "string" ? e.message : "Could not request founder follow-up.";
    setHandoffNotice(detail);
    setTimeout(() => setHandoffNotice(""), 6000);
  } finally {
    setHandoffBusy(false);
  }
}



  function clearRealtimePendingAutoStop() {
    if (rtcPendingAutoStopTimerRef.current) {
      try { clearTimeout(rtcPendingAutoStopTimerRef.current); } catch {}
      rtcPendingAutoStopTimerRef.current = null;
    }
  }

  function getRealtimeSessionAgeMs() {
    try {
      const started = Number(rtcSessionStartedAtRef.current || 0);
      return started ? Math.max(0, Date.now() - started) : null;
    } catch {
      return null;
    }
  }

  function isExplicitRealtimeEndReason(reason = "") {
    // AO68A-HF6R10:
    // Only true user intent or public timebox completion may call /api/realtime/end.
    // Startup cleanup, pre_start reset, pagehide, watchdog, fallback and provider errors
    // must never consume the public quota/cooldown.
    const r = String(reason || "").toLowerCase().trim();
    return (
      r === "client_stop" ||
      r === "toggle_off" ||
      r === "client_stop_fullscreen_clock" ||
      r === "time_limit_frontend" ||
      r === "time_limit_frontend_hard_stop" ||
      r === "backend_cooldown"
    );
  }

  function isManualRealtimeStopReason(reason = "") {
    return isExplicitRealtimeEndReason(reason);
  }


  function isPrematureAutoRealtimeStopReason(reason = "") {
    const r = String(reason || "").toLowerCase();
    if (isManualRealtimeStopReason(r)) return false;
    return (
      r.includes("startup_watchdog") ||
      r.includes("watchdog") ||
      r.includes("no_audio") ||
      r.includes("audio_watchdog") ||
      r.includes("response_timeout") ||
      r.includes("speech") ||
      r.includes("silence") ||
      r.includes("fallback") ||
      r.includes("auto") ||
      r.includes("trigger_failed") ||
      r.includes("mic_ended") ||
      r.includes("dc_closed") ||
      r.includes("pc_disconnected") ||
      r.includes("pc_closed") ||
      r.includes("pc_failed") ||
      r.includes("realtime_error")
    );
  }

  function shouldHoldRealtimeInsteadOfEnding(reason = "", sessionAgeMs = null) {
    const r = String(reason || "").toLowerCase();
    const age = Number(sessionAgeMs);
    if (!Number.isFinite(age)) return false;
    if (age >= 30000) return false;
    if (isManualRealtimeStopReason(r)) return false;
    return isPrematureAutoRealtimeStopReason(r) || Boolean(r);
  }

  function clearRealtimeResponseTimeout() {
    if (rtcResponseTimeoutRef.current) {
      try { clearTimeout(rtcResponseTimeoutRef.current); } catch {}
      rtcResponseTimeoutRef.current = null;
    }
  }

  function clearRealtimeAutoResponseFallback() {
    if (rtcAutoResponseFallbackTimerRef.current) {
      try { clearTimeout(rtcAutoResponseFallbackTimerRef.current); } catch {}
      rtcAutoResponseFallbackTimerRef.current = null;
    }
  }

  function scheduleRealtimeAutoResponseFallback(transcript = "", source = "transcript_final") {
    const clean = String(transcript || "").trim();
    if (!clean) return;

    clearRealtimeAutoResponseFallback();
    rtcLastTranscriptForAutoResponseRef.current = clean;

    rtcAutoResponseFallbackTimerRef.current = setTimeout(() => {
      try {
        if (!realtimeModeRef.current) return;
        if (!rtcSessionIdRef.current) return;
        if (rtcResponseInFlightRef.current) {
          const hasRecentServerResponse = Boolean(
            rtcLastResponseCreatedAtRef.current &&
            (Date.now() - Number(rtcLastResponseCreatedAtRef.current || 0)) < 2500
          );
          if (hasRecentServerResponse) return;

          logRealtimeStep("ao01_hf6r17:clearing_stale_inflight_before_forced_audio_response", {
            source,
            sessionAgeMs: getRealtimeSessionAgeMs(),
            marker: ORKIO_AO66R_HF4_BUILD_MARKER,
          });
          rtcResponseInFlightRef.current = false;
          rtcLastResponseCreatedAtRef.current = 0;
          clearRealtimeResponseTimeout();
        }

        const dc = rtcDcRef.current;
        if (!dc || dc.readyState !== "open") {
          logRealtimeStep("ao66r_hf4:auto_response_fallback_skipped_dc_closed", {
            source,
            readyState: dc?.readyState || null,
            marker: ORKIO_AO66R_HF4_BUILD_MARKER,
          });
          return;
        }

        const latest = String(rtcLastFinalTranscriptRef.current || "").trim();
        if (!latest || latest !== rtcLastTranscriptForAutoResponseRef.current) return;

        logRealtimeStep("ao66r_hf4:auto_response_fallback_trigger", {
          source,
          transcriptLen: latest.length,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });

        triggerRealtimeResponse("auto_fallback_after_transcript");
      } catch (err) {
        logRealtimeStep("ao66r_hf4:auto_response_fallback_failed", {
          source,
          message: err?.message || null,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } finally {
        rtcAutoResponseFallbackTimerRef.current = null;
      }
    }, 450);
  }


function clearRealtimeIdleFollowup() {
  if (rtcIdleFollowupTimerRef.current) {
    try { clearTimeout(rtcIdleFollowupTimerRef.current); } catch {}
    rtcIdleFollowupTimerRef.current = null;
  }
}

function markRealtimeUserActivity() {
  rtcLastUserActivityAtRef.current = Date.now();
  rtcIdleFollowupSentRef.current = false;
  clearRealtimeIdleFollowup();
}

function scheduleRealtimeIdleFollowup() {
  clearRealtimeIdleFollowup();
  if (!REALTIME_IDLE_FOLLOWUP_ENABLED) return;
  if (!realtimeModeRef.current) return;

  const assistantAgentId = destSingle || null;
  const displayName = resolveRealtimeIdleDisplayName(user);
  rtcIdleFollowupTimerRef.current = setTimeout(async () => {
    try {
      if (!realtimeModeRef.current) return;
      if (rtcIdleFollowupSentRef.current) return;
      const idleFor = Date.now() - (rtcLastUserActivityAtRef.current || 0);
      if (idleFor < REALTIME_IDLE_FOLLOWUP_MS) return;

      rtcIdleFollowupSentRef.current = true;
      const prompt = displayName
        ? `${displayName}, você ainda está online? Estou aqui caso queira continuar.`
        : "Você ainda está comigo? Estou aqui caso queira continuar.";

      const mid = `rtc_idle_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      setMessages((prev) => prev.concat([{
        id: mid,
        role: "assistant",
        content: prompt,
        agent_id: assistantAgentId ? String(assistantAgentId) : null,
        agent_name: "Orkio",
        created_at: Math.floor(Date.now()/1000),
      }]));
      queueRealtimeEvent({ event_type: 'response.final', role: 'assistant', content: prompt, is_final: true, meta: { source: 'idle_followup' } });

      try {
        await playTts(prompt, assistantAgentId, { forceAuto: true });
      } catch (err) {
        console.warn("[Realtime] idle follow-up tts failed", err);
      }
    } catch (err) {
      console.warn("[Realtime] idle follow-up failed", err);
    }
  }, REALTIME_IDLE_FOLLOWUP_MS);
}


  async function activateSilentRealtimeFallback(reason = "realtime_fallback", options = {}) {
    const shouldDisarm = options?.disarm !== false;
    const reasonText = String(reason || "realtime_fallback");
    const sessionAgeMs = getRealtimeSessionAgeMs();

    // AO66A-HF3:
    // During the first seconds of a Realtime call, browser/WebRTC callbacks can
    // report "no audio", "dc closed", "mic ended" or fallback conditions before
    // the model has enough time to produce audio. Do not convert those early
    // signals into /api/realtime/end. Keep the timebox alive and wait for either
    // a manual stop, TTL expiration, or a real post-warmup failure.
    if (shouldHoldRealtimeInsteadOfEnding(reasonText, sessionAgeMs)) {
      try {
        console.warn("REALTIME_FALLBACK_HELD_EARLY", {
          reason: reasonText,
          sessionId: rtcSessionIdRef.current || null,
          sessionAgeMs,
          shouldDisarm,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } catch {}
      logRealtimeStep("ao66a_hf3:fallback_held_early", {
        reason: reasonText,
        sessionAgeMs,
        shouldDisarm,
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
      setV2vPhase("listening");
      updateRealtimePremiumStatus("listening", "Realtime ativo. Aguardando áudio ou transcrição.");
      setUploadStatus("⚡ Realtime ativo. Mantive a sessão aberta para aguardar a voz.");
      setTimeout(() => setUploadStatus(""), 2500);
      return;
    }

    if (rtcFallbackActiveRef.current && shouldDisarm) return;
    rtcFallbackActiveRef.current = true;
    clearRealtimeResponseTimeout();
    clearRealtimeIdleFollowup();
    logRealtimeStep("fallback:activate", { reason: reasonText, shouldDisarm });
    try { await stopRealtime(reasonText); } catch {}
    if (shouldDisarm) {
      setRealtimeMode(false);
      realtimeModeRef.current = false;
      setV2vPhase("fallback");
      setUploadStatus("Realtime fallback active.");
      setTimeout(() => setUploadStatus(""), 1200);
      try {
        setVoiceMode(true);
        voiceModeRef.current = true;
        if (!micEnabledRef.current) startMic();
      } catch {}
    } else {
      setV2vPhase("error");
      setUploadStatus(`❌ Realtime diagnostic: ${reasonText}`);
      setTimeout(() => setUploadStatus(""), 2500);
    }
  }

  async function guardAndMaybeBlockRealtimeTranscript(raw) {
    const message = (raw || "").toString().trim();
    if (!message) return false;
    try {
      const res = await guardRealtimeTranscript({ thread_id: rtcThreadIdRef.current || threadId || null, message });
      const payload = res?.data || {};
      if (!payload?.blocked) return false;
      setRtcReadyToRespond(false);
      rtcLastFinalTranscriptRef.current = "";
      queueRealtimeEvent({ event_type: "response.final", role: "assistant", content: payload.reply || "", is_final: true, meta: { source: "server_guard" } });
      commitRealtimeAssistantFinal(payload.reply || "", { source: "server_guard" });
      return true;
    } catch (err) {
      console.warn("[Realtime] guard check failed", err);
      return false;
    }
  }

  // ORKIO_AO60H_REALTIME_MOBILE_AUDIO_TRANSCRIPT_LIFECYCLE
  function clearRealtimeAudioWatchdog() {
    if (rtcAudioWatchdogRef.current) {
      try { clearInterval(rtcAudioWatchdogRef.current); } catch {}
      rtcAudioWatchdogRef.current = null;
    }
  }

  function ensureRealtimeAudioOutput(reason = "repair") {
    try {
      const audioEl = rtcAudioElRef.current;
      if (!audioEl) return false;

      try { audioEl.autoplay = true; } catch {}
      try { audioEl.playsInline = true; } catch {}
      try { audioEl.muted = false; } catch {}
      try { audioEl.volume = 1; } catch {}
      try { audioEl.setAttribute("playsinline", ""); } catch {}
      try { audioEl.setAttribute("webkit-playsinline", ""); } catch {}

      if (rtcRemoteStreamRef.current && audioEl.srcObject !== rtcRemoteStreamRef.current) {
        try { audioEl.srcObject = rtcRemoteStreamRef.current; } catch {}
      }

      if (!audioEl.isConnected && typeof document !== "undefined" && document.body) {
        try {
          audioEl.style.display = "none";
          document.body.appendChild(audioEl);
        } catch {}
      }

      const shouldPlay = Boolean(audioEl.srcObject) && (audioEl.paused || Number(audioEl.volume || 0) < 0.95 || audioEl.muted);
      if (shouldPlay) {
        const p = audioEl.play?.();
        if (p && typeof p.catch === "function") {
          p.catch((err) => {
            logRealtimeStep("audio:play_blocked", {
              reason,
              message: err?.message || null,
              visibility: typeof document !== "undefined" ? document.visibilityState : null,
            });
          });
        }
      }

      logRealtimeStep("audio:output_repaired", {
        reason,
        paused: !!audioEl.paused,
        muted: !!audioEl.muted,
        volume: Number(audioEl.volume || 0),
        connected: !!audioEl.isConnected,
        hasStream: !!audioEl.srcObject,
      });
      return true;
    } catch (err) {
      logRealtimeStep("audio:repair_failed", { reason, message: err?.message || null });
      return false;
    }
  }

  function flushRealtimePartialTranscript(reason = "partial_flush") {
    try {
      if (rtcAssistantFinalCommittedRef.current) return false;
      const textFinal = (rtcTextBufRef.current || "").trim();
      const audioFinal = (rtcAudioTranscriptBufRef.current || "").trim();
      const finalText = textFinal || audioFinal;
      if (!finalText) return false;
      logRealtimeStep("runtime:partial_transcript_flushed", {
        reason,
        source: textFinal ? "text_buffer" : "audio_transcript_buffer",
        finalText,
      });
      commitRealtimeAssistantFinal(finalText, { source: reason });
      rtcTextBufRef.current = "";
      rtcAudioTranscriptBufRef.current = "";
      return true;
    } catch (err) {
      logRealtimeStep("runtime:partial_transcript_flush_failed", { reason, message: err?.message || null });
      return false;
    }
  }

  function startRealtimeAudioWatchdog() {
    clearRealtimeAudioWatchdog();
    rtcAudioWatchdogRef.current = setInterval(() => {
      try {
        if (!realtimeModeRef.current || !rtcSessionIdRef.current) return;
        ensureRealtimeAudioOutput("watchdog");
      } catch {}
    }, 2500);
  }

  function isRealtimeDocumentVisible() {
    try {
      if (typeof document === "undefined") return true;
      return document.visibilityState !== "hidden";
    } catch {
      return true;
    }
  }

  async function requestRealtimeWakeLock(reason = "realtime_active") {
    try {
      if (typeof navigator === "undefined" || !navigator.wakeLock?.request) {
        logRealtimeStep("mobile:wake_lock_not_supported", { reason });
        return false;
      }

      if (!isRealtimeDocumentVisible()) {
        logRealtimeStep("mobile:wake_lock_deferred_hidden", { reason });
        return false;
      }

      const existing = rtcWakeLockRef.current;
      if (existing && existing.released !== true) {
        logRealtimeStep("mobile:wake_lock_already_active", { reason });
        return true;
      }

      const lock = await navigator.wakeLock.request("screen");
      rtcWakeLockRef.current = lock;

      try {
        lock.addEventListener?.("release", () => {
          logRealtimeStep("mobile:wake_lock_released", {
            reason,
            wanted: Boolean(rtcWakeLockWantedRef.current),
            realtime: Boolean(realtimeModeRef.current || rtcSessionIdRef.current || rtcConnectingRef.current),
            visibility: typeof document !== "undefined" ? document.visibilityState : null,
          });

          // Reacquire when release was caused by transient browser/OS behavior while Realtime remains foreground-active.
          if (
            rtcWakeLockWantedRef.current &&
            (realtimeModeRef.current || rtcSessionIdRef.current || rtcConnectingRef.current) &&
            isRealtimeDocumentVisible()
          ) {
            setTimeout(() => {
              try { void requestRealtimeWakeLock("release_reacquire"); } catch {}
            }, 600);
          }
        });
      } catch {}

      logRealtimeStep("mobile:wake_lock_acquired", { reason });
      return true;
    } catch (err) {
      logRealtimeStep("mobile:wake_lock_unavailable", { reason, message: err?.message || null });
      return false;
    }
  }

  function clearRealtimeWakeLockGuard(reason = "wake_guard_clear") {
    try {
      if (rtcWakeLockGuardTimerRef.current) {
        clearInterval(rtcWakeLockGuardTimerRef.current);
        rtcWakeLockGuardTimerRef.current = null;
      }
      logRealtimeStep("mobile:wake_lock_guard_cleared", { reason });
    } catch {}
  }

  function startRealtimeWakeLockGuard(reason = "realtime_active") {
    try {
      rtcWakeLockWantedRef.current = true;
      void requestRealtimeWakeLock(reason);

      clearRealtimeWakeLockGuard("restart");
      rtcWakeLockGuardTimerRef.current = setInterval(() => {
        try {
          if (!rtcWakeLockWantedRef.current) return;
          if (!(realtimeModeRef.current || rtcSessionIdRef.current || rtcConnectingRef.current)) return;
          if (!isRealtimeDocumentVisible()) return;
          const lock = rtcWakeLockRef.current;
          if (!lock || lock.released === true) {
            void requestRealtimeWakeLock("guard_tick_reacquire");
          }
        } catch {}
      }, 30000);

      logRealtimeStep("mobile:wake_lock_guard_started", { reason });
    } catch {}
  }

  async function releaseRealtimeWakeLock(reason = "realtime_stop") {
    try {
      rtcWakeLockWantedRef.current = false;
      clearRealtimeWakeLockGuard(reason);
      const lock = rtcWakeLockRef.current;
      rtcWakeLockRef.current = null;
      if (lock) await lock.release?.();
      logRealtimeStep("mobile:wake_lock_release_requested", { reason });
    } catch {}
  }

  // ORKIO_AO60I_REALTIME_TIMEBOX_COOLDOWN_COUNTER
  function formatRealtimeCountdown(totalSeconds) {
    const safe = Math.max(0, Math.ceil(Number(totalSeconds || 0)));
    const mm = String(Math.floor(safe / 60)).padStart(2, "0");
    const ss = String(safe % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  function formatRealtimeDurationLabel(totalSeconds) {
    const safe = Math.max(1, Math.ceil(Number(totalSeconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS)));
    if (safe < 60) return `${safe} segundo${safe === 1 ? "" : "s"}`;
    const minutes = Math.floor(safe / 60);
    const seconds = safe % 60;
    if (!seconds) return `${minutes} minuto${minutes === 1 ? "" : "s"}`;
    return `${minutes} minuto${minutes === 1 ? "" : "s"} e ${seconds} segundo${seconds === 1 ? "" : "s"}`;
  }

  function resolveRealtimeStartTimeboxSeconds(startPayload = null) {
    // AO61A-HF3: backend remaining_seconds is the runtime source of truth for resumed sessions.
    try {
      const timebox = startPayload?.timebox || {};
      const remainingSeconds = Number(timebox?.remaining_seconds);
      const maxSeconds = Number(timebox?.max_seconds);
      const policyRemaining = Number(rtcTimeboxPolicyRef.current?.remainingSeconds);
      const policyMax = Number(rtcTimeboxPolicyRef.current?.maxSeconds);

      const candidates = [remainingSeconds, policyRemaining, maxSeconds, policyMax, REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS];
      for (const candidate of candidates) {
        if (Number.isFinite(candidate) && candidate > 0) return Math.max(1, Math.ceil(candidate));
      }
    } catch {}
    return REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS;
  }

  function shouldShowRealtimeCounter() {
    return Boolean(
      SUMMIT_VOICE_MODE === "realtime"
      && (
        rtcTimeboxRemaining !== null
        || rtcCooldownRemaining > 0
        || realtimeMode
        || rtcPremiumStatus
      )
    );
  }

  function getRealtimeCounterLabel() {
    if (rtcCooldownRemaining > 0 && !realtimeMode) {
      return `🕒 ${formatRealtimeCountdown(rtcCooldownRemaining)}`;
    }
    if (rtcTimeboxRemaining !== null) {
      return `⏳ ${formatRealtimeCountdown(rtcTimeboxRemaining)}`;
    }
    if (realtimeMode) {
      return `⏳ ${formatRealtimeCountdown(rtcTimeboxPolicyRef.current?.maxSeconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS)}`;
    }
    return "";
  }

  function getRealtimeFixedCounterTitle() {
    if (rtcCooldownRemaining > 0 && !realtimeMode) return "🕒 Cooldown";
    if (rtcTimeboxRemaining !== null || realtimeMode) return "🎙️ Realtime";
    return "Realtime";
  }

  function getRealtimeFixedCounterSubtitle() {
    if (rtcCooldownRemaining > 0 && !realtimeMode) return "O chat por texto continua disponível.";
    if (rtcPremiumStatusDetail) return rtcPremiumStatusDetail;
    if (rtcPremiumStatus) return getRealtimePremiumStatusLabel();
    if (realtimeMode) return "Ouvindo com tela ativa.";
    return "";
  }

  function updateRealtimePremiumStatus(status = null, detail = "") {
    // AO61A_REALTIME_PREMIUM_UX_COOLDOWN_TRANSCRIPTION_LOCK
    try { setRtcPremiumStatus(status || null); } catch {}
    try { setRtcPremiumStatusDetail(String(detail || "")); } catch {}
  }

  // AO66A_REALTIME_FULLSCREEN_CLOCK_TRANSCRIPT_SUMMARY
  // AO64D-HF1: Summary lifecycle moved to useRealtimeTranscriptSummary.
  // Keep these thin wrappers so the existing Realtime/WebRTC flow remains untouched.
  function normalizeRealtimeTranscriptText(value) {
    return realtimeSummary.normalizeText(value);
  }

  function resetRealtimeTranscriptSession(reason = "reset") {
    return realtimeSummary.reset(reason);
  }

  function appendRealtimeTranscriptTurn(role, content, meta = {}) {
    return realtimeSummary.appendTurn(role, content, meta);
  }

  function buildRealtimeTranscriptSummary(reason = "ended", extra = {}) {
    return realtimeSummary.build(reason, extra);
  }

  function publishRealtimeTranscriptSummary(reason = "ended", extra = {}) {
    return realtimeSummary.publish(reason, extra);
  }

  function getRealtimePremiumStatusLabel() {
    if (rtcCooldownRemaining > 0 && !realtimeMode) {
      return `🕒 Voz disponível novamente em ${formatRealtimeCountdown(rtcCooldownRemaining)}`;
    }
    if (rtcPremiumStatus === "connecting") return "🎙️ Conectando...";
    if (rtcPremiumStatus === "listening") return "🎙️ Ouvindo...";
    if (rtcPremiumStatus === "transcribing") return "📝 Transcrição ativa";
    if (rtcPremiumStatus === "responding") return "🔊 Orkio respondendo...";
    if (rtcPremiumStatus === "ending") return "⚠️ Encerrando em breve...";
    if (rtcPremiumStatus === "cooldown") {
      return `🕒 Voz disponível novamente em ${formatRealtimeCountdown(rtcCooldownRemaining || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS)}`;
    }
    if (realtimeMode) return "🎙️ Ouvindo...";
    return "";
  }

  function isRealtimeTimeboxLimitedUser() {
    // AO64D-HF5: hard timebox/cooldown removed for all users.
    // Usage duration may still be shown as advisory elsewhere, but it must not block or stop Realtime.
    if (REALTIME_FRONTEND_HARD_TIMEBOX_ENABLED !== true) return false;

    // AO01-HF6R16 — Admin/superadmin and backend-declared bypass never use public beta timebox/cooldown.
    if (canAccessAdmin || rtcAdminTimeboxBypassRef.current === true || rtcAdminTimeboxBypass === true) return false;
    return rtcBackendTimeboxLimitedRef.current === true || rtcBackendTimeboxLimited === true;
  }

  function clearRealtimeTimeboxTimer(options = {}) {
    try {
      if (rtcTimeboxTimerRef.current) clearInterval(rtcTimeboxTimerRef.current);
    } catch {}
    try {
      if (rtcTimeboxHardStopTimerRef.current) clearTimeout(rtcTimeboxHardStopTimerRef.current);
    } catch {}
    rtcTimeboxTimerRef.current = null;
    rtcTimeboxHardStopTimerRef.current = null;
    rtcTimeboxDeadlineRef.current = 0;
    if (!options?.preserveDisplay) setRtcTimeboxRemaining(null);
  }

  function clearRealtimeCooldownTimer() {
    try {
      if (rtcCooldownTimerRef.current) clearInterval(rtcCooldownTimerRef.current);
    } catch {}
    rtcCooldownTimerRef.current = null;
  }

  function startRealtimeCooldown(seconds = REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS, reason = "cooldown") {
    // AO64D-HF5_NO_HARD_TIMEBOX_ESG_FRONTEND
    // Cooldown is no longer a hard client-side state. Keep cleanup only.
    if (REALTIME_FRONTEND_HARD_TIMEBOX_ENABLED !== true) {
      try { clearRealtimeCooldownTimer(); } catch {}
      try { rtcCooldownUntilRef.current = 0; } catch {}
      try { setRtcCooldownRemaining(0); } catch {}
      try { updateRealtimePremiumStatus(null, ""); } catch {}
      logRealtimeStep("ao64d_hf5:cooldown_suppressed_advisory_only", { reason, seconds });
      return 0;
    }

    // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
    // If the backend returns 429/Retry-After, the UI must enter cooldown even when
    // the local cached user object is stale or incorrectly looks like admin.
    const duration = Math.max(1, Math.ceil(Number(seconds || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS)));
    const until = Date.now() + duration * 1000;
    rtcCooldownUntilRef.current = until;

    clearRealtimeCooldownTimer();
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((rtcCooldownUntilRef.current - Date.now()) / 1000));
      setRtcCooldownRemaining(remaining);
      if (remaining > 0) {
        updateRealtimePremiumStatus("cooldown", `O chat por texto continua disponível. Liberação em ${formatRealtimeCountdown(remaining)}.`);
      }
      if (remaining <= 0) {
        clearRealtimeCooldownTimer();
        rtcCooldownUntilRef.current = 0;
        updateRealtimePremiumStatus(null, "");
      }
    };

    tick();
    rtcCooldownTimerRef.current = setInterval(tick, 1000);
    logRealtimeStep("timebox:cooldown_started", { reason, seconds: duration, marker: ORKIO_AO61A_BUILD_MARKER });
  }

  // ORKIO_AO60K_HF5_FRONTEND_MOBILE_REALTIME_RESTART_TRANSCRIPT_FIX
  function clearRealtimeStartupWatchdog() {
    try {
      if (rtcStartupWatchdogTimerRef.current) clearTimeout(rtcStartupWatchdogTimerRef.current);
    } catch {}
    rtcStartupWatchdogTimerRef.current = null;
  }

  function clearRealtimeActivationProbe() {
    try {
      if (rtcActivationProbeTimerRef.current) clearTimeout(rtcActivationProbeTimerRef.current);
    } catch {}
    rtcActivationProbeTimerRef.current = null;
  }

  function hardResetRealtimeClientState(reason = "hard_reset") {
    logRealtimeStep("hf5:hard_reset_begin", { reason, sessionId: rtcSessionIdRef.current || null });

    try { clearRealtimeResponseTimeout(); } catch {}
    try { clearRealtimeAutoResponseFallback(); } catch {}
    try { clearRealtimeIdleFollowup(); } catch {}
    try { clearRealtimeAudioWatchdog(); } catch {}
    try { clearRealtimeStartupWatchdog(); } catch {}
    try { clearRealtimeActivationProbe(); } catch {}
    try { clearRealtimeTimeboxTimer(); } catch {}
    try { rtcConversationStartedRef.current = false; } catch {}
    try { rtcPendingTimeboxSecondsRef.current = null; } catch {}
    try { clearRealtimeLivePoll(); } catch {}
    try {
      if (rtcFlushTimerRef.current) {
        clearInterval(rtcFlushTimerRef.current);
        rtcFlushTimerRef.current = null;
      }
    } catch {}

    try {
      const dc = rtcDcRef.current;
      rtcDcRef.current = null;
      if (dc) {
        try { dc.onopen = null; } catch {}
        try { dc.onmessage = null; } catch {}
        try { dc.onerror = null; } catch {}
        try { dc.onclose = null; } catch {}
        try { dc.close?.(); } catch {}
      }
    } catch {}

    try {
      const pc = rtcPcRef.current;
      rtcPcRef.current = null;
      if (pc) {
        try { pc.ontrack = null; } catch {}
        try { pc.onconnectionstatechange = null; } catch {}
        try { pc.oniceconnectionstatechange = null; } catch {}
        try { pc.getSenders?.().forEach((sender) => { try { sender.track?.stop?.(); } catch {} }); } catch {}
        try { pc.getReceivers?.().forEach((receiver) => { try { receiver.track?.stop?.(); } catch {} }); } catch {}
        try { pc.close?.(); } catch {}
      }
    } catch {}

    try {
      const a = rtcAudioElRef.current;
      rtcAudioElRef.current = null;
      rtcRemoteStreamRef.current = null;
      if (a) {
        try { a.pause?.(); } catch {}
        try { a.srcObject = null; } catch {}
        try { if (a.isConnected) a.remove?.(); } catch {}
      }
    } catch {}

    try {
      const processing = rtcAudioProcessingRef.current;
      rtcAudioProcessingRef.current = null;
      if (processing) {
        try { processing.destination?.stream?.getTracks?.().forEach((t) => { try { t.stop?.(); } catch {} }); } catch {}
        try { processing.rawStream?.getTracks?.().forEach((t) => { try { t.stop?.(); } catch {} }); } catch {}
        try { processing.ctx?.close?.(); } catch {}
      }
    } catch {}

    try { rtcEventQueueRef.current = []; } catch {}
    try { rtcSeenBackendResponseIdsRef.current = new Set(); } catch {}
    try { rtcTextBufRef.current = ""; } catch {}
    try { rtcAudioTranscriptBufRef.current = ""; } catch {}
    try { rtcLastFinalTranscriptRef.current = ""; } catch {}
    try { rtcLastAssistantFinalRef.current = ""; } catch {}
    try { rtcAssistantFinalCommittedRef.current = false; } catch {}
    try { rtcAssistantFinalMessageIdRef.current = null; } catch {}
    try { rtcAssistantFinalTextRef.current = ""; } catch {}
    try { rtcAssistantPendingFinalTextRef.current = ""; } catch {}
    try { rtcAssistantPendingFinalSourceRef.current = ""; } catch {}
    try { if (rtcAssistantPendingFinalTimerRef.current) clearTimeout(rtcAssistantPendingFinalTimerRef.current); rtcAssistantPendingFinalTimerRef.current = null; } catch {}
    try { if (rtcTimeboxHardStopTimerRef.current) clearTimeout(rtcTimeboxHardStopTimerRef.current); rtcTimeboxHardStopTimerRef.current = null; rtcTimeboxDeadlineRef.current = 0; } catch {}
    try { clearRealtimePendingAutoStop(); } catch {}
    try { rtcSessionStartedAtRef.current = 0; } catch {}
    try { rtcLastStopReasonRef.current = ""; } catch {}
    try { rtcResponseInFlightRef.current = false; } catch {}
    try { rtcLastResponseCreatedAtRef.current = 0; } catch {}
    try { rtcActivationProbeSentRef.current = false; } catch {}
    try { rtcFallbackActiveRef.current = false; } catch {}
    try { rtcLivePollSessionIdRef.current = null; } catch {}
    try { setRtcReadyToRespond(false); } catch {}
    try { setRtcPunctStatus(null); } catch {}

    logRealtimeStep("hf5:hard_reset_done", { reason });
  }

  function startRealtimeStartupWatchdog(sessionId, reason = "start") {
    clearRealtimeStartupWatchdog();
    if (!sessionId) return;
    rtcStartupWatchdogTimerRef.current = setTimeout(() => {
      try {
        if (!realtimeModeRef.current) return;
        if (rtcSessionIdRef.current !== sessionId) return;

        const dcReady = rtcDcRef.current?.readyState === "open";
        const pcState = String(rtcPcRef.current?.connectionState || rtcPcRef.current?.iceConnectionState || "").toLowerCase();
        if (dcReady) return;

        logRealtimeStep("ao66r_hf4:startup_watchdog_datachannel_not_ready", {
          sessionId,
          reason,
          pcState,
          ageMs: getRealtimeSessionAgeMs(),
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
        updateRealtimePremiumStatus("connecting", "Ainda estabilizando a conexão de voz. Não encerrei a sessão automaticamente.");
        setUploadStatus("⚡ A voz ainda está estabilizando. Aguarde alguns segundos ou toque em Encerrar se quiser cancelar.");
        setTimeout(() => setUploadStatus(""), 4500);
        // AO66A-HF2: do not auto-end at the old 15s watchdog point.
        // The user may be on mobile/PWA and the datachannel can settle late.
        return;
      } catch {}
    }, 15000);
  }

  function extractRealtimeRetryAfterSeconds(err) {
    // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
    // Accept all common API error shapes used by apiFetch/fetch wrappers and CDNs.
    const candidates = [
      err?.retry_after_seconds,
      err?.retryAfter,
      err?.retry_after,
      err?.retryAfterSeconds,
      err?.data?.retry_after_seconds,
      err?.data?.retryAfter,
      err?.data?.retry_after,
      err?.data?.detail?.retry_after_seconds,
      err?.data?.detail?.retryAfter,
      err?.detail?.retry_after_seconds,
      err?.detail?.retryAfter,
      err?.payload?.retry_after_seconds,
      err?.payload?.retryAfter,
      err?.response?.data?.retry_after_seconds,
      err?.response?.data?.detail?.retry_after_seconds,
      err?.response?.data?.detail?.retryAfter,
      err?.headers?.["Retry-After"],
      err?.headers?.["retry-after"],
      err?.response?.headers?.["Retry-After"],
      err?.response?.headers?.["retry-after"],
    ];
    for (const value of candidates) {
      const n = Number(value);
      if (Number.isFinite(n) && n > 0) return Math.ceil(n);
    }

    try {
      const raw = [
        err?.message,
        err?.userMessage,
        typeof err?.detail === "string" ? err.detail : "",
        typeof err?.data === "string" ? err.data : "",
        typeof err?.payload === "string" ? err.payload : "",
      ].filter(Boolean).join(" ");
      const jsonMatch = raw.match(/\{[\s\S]*\}/);
      const parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : (raw.trim().startsWith("{") ? JSON.parse(raw) : null);
      const n = Number(
        parsed?.retry_after_seconds ||
        parsed?.retryAfter ||
        parsed?.detail?.retry_after_seconds ||
        parsed?.detail?.retryAfter ||
        parsed?.data?.retry_after_seconds ||
        parsed?.data?.retryAfter
      );
      if (Number.isFinite(n) && n > 0) return Math.ceil(n);
    } catch {}

    return null;
  }

  function isRealtimeCooldownOrRateLimitError(err) {
    // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
    const rawParts = [
      err?.code,
      err?.status,
      err?.statusText,
      err?.name,
      err?.message,
      err?.userMessage,
      err?.detail,
      err?.data,
      err?.payload,
      err?.error,
    ];

    let raw = "";
    try {
      raw = rawParts.map((part) => {
        if (part === null || part === undefined) return "";
        if (typeof part === "string") return part;
        if (typeof part === "number" || typeof part === "boolean") return String(part);
        return JSON.stringify(part);
      }).filter(Boolean).join(" | ").toLowerCase();
    } catch {
      raw = String(err?.message || err || "").toLowerCase();
    }

    return Boolean(
      extractRealtimeRetryAfterSeconds(err) ||
      err?.status === 429 ||
      err?.response?.status === 429 ||
      err?.code === "RATE_LIMITED" ||
      err?.code === "REALTIME_COOLDOWN_ACTIVE" ||
      err?.isRateLimited === true ||
      raw.includes("429") ||
      raw.includes("rate_limited") ||
      raw.includes("rate limited") ||
      raw.includes("too many requests") ||
      raw.includes("realtime_cooldown_active") ||
      raw.includes("cooldown")
    );
  }

  function applyRealtimeCooldownFromError(err, reason = "backend_cooldown_or_rate_limit") {
    // AO01-HF6R16: admin/billing errors must not be converted into public beta cooldown.
    const rawCooldownMessage = String(err?.message || err?.userMessage || err?.payload?.message || err?.payload?.detail || err?.detail || "").toLowerCase();
    if (
      rawCooldownMessage.includes("insufficient_quota") ||
      rawCooldownMessage.includes("current quota") ||
      rawCooldownMessage.includes("billing") ||
      rawCooldownMessage.includes("exceeded your current quota")
    ) {
      try { clearRealtimeTimeboxTimer(); } catch {}
      try { setRtcCooldownRemaining(0); } catch {}
      try { rtcCooldownUntilRef.current = 0; } catch {}
      try { setV2vPhase("error"); } catch {}
      const billingMessage = "Realtime indisponível por quota/billing da OpenAI. Faça recarga ou ajuste de billing antes de novo teste. O chat por texto continua disponível.";
      try { updateRealtimePremiumStatus("error", billingMessage); } catch {}
      try { setV2vError(billingMessage); } catch {}
      try { setUploadStatus(`⚠️ ${billingMessage}`); setTimeout(() => setUploadStatus(""), 6000); } catch {}
      return 0;
    }
    if (canAccessAdmin || rtcAdminTimeboxBypassRef.current === true) {
      try { clearRealtimeTimeboxTimer(); } catch {}
      try { setRtcCooldownRemaining(0); } catch {}
      try { rtcCooldownUntilRef.current = 0; } catch {}
      try { setV2vPhase("error"); } catch {}
      const msg = normalizeUserFacingRuntimeMessage(err, "realtime");
      try { updateRealtimePremiumStatus("error", msg); } catch {}
      try { setV2vError(msg); } catch {}
      try { setUploadStatus(`⚠️ ${msg}`); setTimeout(() => setUploadStatus(""), 4500); } catch {}
      return 0;
    }

    // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
    const waitSeconds = Math.max(
      1,
      Math.ceil(Number(extractRealtimeRetryAfterSeconds(err) || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS))
    );
    rtcBackendTimeboxLimitedRef.current = true;
    try { setRtcBackendTimeboxLimited(true); } catch {}
    try { clearRealtimeTimeboxTimer(); } catch {}
    try { startRealtimeCooldown(waitSeconds, reason); } catch {}
    const label = formatRealtimeCountdown(waitSeconds);

    try { setRealtimeMode(false); } catch {}
    realtimeModeRef.current = false;
    try { setRtcReadyToRespond(false); } catch {}
    try { setV2vPhase("cooldown"); } catch {}
    try { updateRealtimePremiumStatus("cooldown", `O chat por texto continua disponível. Liberação em ${label}.`); } catch {}
    try { setV2vError(`A voz em tempo real estará disponível novamente em ${label}. O chat por texto continua disponível.`); } catch {}
    try { setUploadStatus(`⏳ Voz disponível novamente em ${label}. O chat por texto continua disponível.`); } catch {}
    try { setTimeout(() => setUploadStatus(""), 4500); } catch {}
    try { logRealtimeStep("timebox:cooldown_applied_from_error", { reason, waitSeconds }); } catch {}
    return waitSeconds;
  }



  function startRealtimeTimebox(seconds = REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS, options = {}) {
    const force = Boolean(options?.force);
    const source = String(options?.source || "unknown");

    // AO64D-HF5_NO_HARD_TIMEBOX_ESG_FRONTEND
    // The clock/timebox is advisory-only now. Do not start timers, warnings, cooldowns or hard-stop.
    if (REALTIME_FRONTEND_HARD_TIMEBOX_ENABLED !== true) {
      clearRealtimeTimeboxTimer();
      try { setRtcTimeboxRemaining(null); } catch {}
      try { rtcTimeboxDeadlineRef.current = 0; } catch {}
      logRealtimeStep("ao64d_hf5:timebox_suppressed_advisory_only", { seconds, force, source });
      return;
    }

    if (!force && !isRealtimeTimeboxLimitedUser() && rtcBackendTimeboxLimitedRef.current !== true) return;
    clearRealtimeTimeboxTimer();

    const maxSeconds = Math.max(1, Math.ceil(Number(seconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS)));
    try { rtcTimeboxPolicyRef.current = { ...(rtcTimeboxPolicyRef.current || {}), remainingSeconds: maxSeconds }; } catch {}
    const startedAt = Date.now();
    const endsAt = startedAt + maxSeconds * 1000;
    rtcTimeboxDeadlineRef.current = endsAt;
    try {
      if (rtcTimeboxHardStopTimerRef.current) clearTimeout(rtcTimeboxHardStopTimerRef.current);
      rtcTimeboxHardStopTimerRef.current = setTimeout(() => {
        try {
          if (!rtcSessionIdRef.current) return;
          console.log("REALTIME_TIMEBOX_HARD_STOP", {
            marker: ORKIO_AO61A_HF4_BUILD_MARKER,
            sessionId: rtcSessionIdRef.current || null,
            maxSeconds,
            source,
          });
        } catch {}
        try { void stopRealtime("time_limit_frontend_hard_stop"); } catch {}
      }, Math.max(1, maxSeconds * 1000 + 350));
    } catch {}
    let warned15 = false;
    let warned10 = false;

    const tick = () => {
      const remaining = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setRtcTimeboxRemaining(remaining);

      if (remaining > 15 && !rtcResponseInFlightRef.current) {
        updateRealtimePremiumStatus("listening", "📝 Transcrição ativa");
      }

      if (remaining <= 15 && remaining > 10 && !warned15) {
        warned15 = true;
        updateRealtimePremiumStatus("ending", "⚠️ Esta sessão será encerrada em 15 segundos.");
        setUploadStatus("⚠️ Esta sessão será encerrada em 15 segundos.");
        setTimeout(() => setUploadStatus(""), 2500);
      }

      if (remaining <= 10 && remaining > 0 && !warned10) {
        warned10 = true;
        updateRealtimePremiumStatus("ending", "⚠️ Encerrando em breve.");
        setUploadStatus("⚠️ Encerrando em breve. O chat por texto continuará disponível.");
        setTimeout(() => setUploadStatus(""), 2500);
      }

      if (remaining <= 0) {
        clearRealtimeTimeboxTimer();
        logRealtimeStep("timebox:limit_reached", { maxSeconds, marker: ORKIO_AO61A_BUILD_MARKER });
        setRealtimeMode(false);
        realtimeModeRef.current = false;
        setV2vPhase("cooldown");
        const cooldownSeconds = Math.max(1, Math.ceil(Number(rtcTimeboxPolicyRef.current?.cooldownSeconds || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS)));
        const cooldownLabel = formatRealtimeCountdown(cooldownSeconds);
        const cooldownMessage = `A sessão de voz foi encerrada. Ela estará disponível novamente em ${cooldownLabel}. O chat por texto continua disponível.`;
        setV2vError(cooldownMessage);
        updateRealtimePremiumStatus("cooldown", cooldownMessage);
        setUploadStatus(`⏳ ${cooldownMessage}`);
        setTimeout(() => setUploadStatus(""), 4500);
        try {
          console.log("REALTIME_TIMEBOX_AUTO_STOP", {
            marker: ORKIO_AO61A_BUILD_MARKER,
            hf3Marker: ORKIO_AO61A_HF3_BUILD_MARKER,
            hf4Marker: ORKIO_AO61A_HF4_BUILD_MARKER,
            source,
            previousMarker: ORKIO_AO60K_HF5B_BUILD_MARKER,
            remaining,
            maxSeconds,
            cooldownSeconds,
            sessionId: rtcSessionIdRef.current || null,
          });
        } catch {}
        void stopRealtime("time_limit_frontend");
      }
    };

    tick();
    rtcTimeboxTimerRef.current = setInterval(tick, 1000);
    logRealtimeStep("timebox:started", { seconds: maxSeconds, marker: ORKIO_AO61A_BUILD_MARKER, hf3Marker: ORKIO_AO61A_HF3_BUILD_MARKER, hf4Marker: ORKIO_AO61A_HF4_BUILD_MARKER, source, deadline: rtcTimeboxDeadlineRef.current });
  }

  function startRealtimeConversationTimeboxIfNeeded(source = "assistant_response_done", secondsOverride = null) {
    try {
      if (rtcConversationStartedRef.current) return false;
      if (rtcOverlayForceClosed) return false;
      const limited = isRealtimeTimeboxLimitedUser() || rtcBackendTimeboxLimitedRef.current === true;
      if (!limited) return false;
      const pending = Number(secondsOverride || rtcPendingTimeboxSecondsRef.current || rtcTimeboxPolicyRef.current?.remainingSeconds || rtcTimeboxPolicyRef.current?.maxSeconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS);
      const seconds = Math.max(1, Math.ceil(pending || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS));
      rtcConversationStartedRef.current = true;
      rtcPendingTimeboxSecondsRef.current = null;
      console.log("REALTIME_TIMEBOX_STARTED_AFTER_ASSISTANT_INTRO", {
        marker: "AO66R_HF6_TIMEBOX_AFTER_FIRST_ASSISTANT_RESPONSE",
        source,
        seconds,
        sessionId: rtcSessionIdRef.current || null,
      });
      startRealtimeTimebox(seconds, { force: true, source });
      updateRealtimePremiumStatus("listening", `📝 Transcrição ativa — ${formatRealtimeCountdown(seconds)} disponíveis.`);
      return true;
    } catch (err) {
      try { console.warn("REALTIME_TIMEBOX_DELAYED_START_FAILED", err); } catch {}
      return false;
    }
  }

  function sendRealtimeClientEvent(dc, payload, reason = "client_event") {
    try {
      if (!dc || dc.readyState !== "open") {
        logRealtimeStep("ao66r:send_skip_dc_not_open", {
          reason,
          readyState: dc?.readyState || null,
          type: payload?.type || null,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
        return false;
      }

      const eventId = payload?.event_id || `evt_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      const finalPayload = { event_id: eventId, ...(payload || {}) };

      try {
        console.log("REALTIME_CLIENT_EVENT", {
          reason,
          type: finalPayload.type,
          event_id: eventId,
          response_modalities: finalPayload?.response?.output_modalities || null,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } catch {}

      dc.send(JSON.stringify(finalPayload));
      try { queueRealtimeTelemetry("client_event_sent", { reason, type: finalPayload.type, event_id: eventId }); } catch {}
      logRealtimeStep("ao66r:client_event_sent", {
        reason,
        type: finalPayload.type,
        event_id: eventId,
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
      return true;
    } catch (err) {
      logRealtimeStep("ao66r:client_event_failed", {
        reason,
        type: payload?.type || null,
        message: err?.message || null,
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
      return false;
    }
  }

  function requestRealtimeSpokenResponse(dc, {
    reason = "activation",
    instructions = "",
    inputText = "",
    conversationItem = false,
  } = {}) {
    const cleanInstructions = String(instructions || "").trim();
    const responseInstructions = cleanInstructions || buildRealtimeVoiceInstruction(rtcLanguageProfileRef.current);
    const cleanInput = String(inputText || "").trim();
    const voice = coerceVoiceId(rtcVoiceRef.current || ORKIO_CANONICAL_VOICE_ID || ORKIO_DEFAULT_VOICE_ID);

    if (conversationItem && cleanInput) {
      sendRealtimeClientEvent(dc, {
        type: "conversation.item.create",
        item: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: cleanInput }],
        },
      }, `${reason}:conversation_item`);
    }

    rtcResponseInFlightRef.current = true;
    clearRealtimeResponseTimeout();
    rtcResponseTimeoutRef.current = setTimeout(() => {
      try {
        if (!realtimeModeRef.current || !rtcSessionIdRef.current) return;
        if (rtcLastResponseCreatedAtRef.current) return;
        logRealtimeStep("ao66r:response_create_no_server_response_yet", {
          reason,
          sessionAgeMs: getRealtimeSessionAgeMs(),
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
        updateRealtimePremiumStatus("listening", "Realtime conectado. Aguardando resposta de áudio.");
      } catch {}
    }, 6000);

    queueRealtimeTelemetry("response_create_attempt", {
      reason,
      conversationItem: Boolean(conversationItem),
      hasInputText: Boolean(cleanInput),
      hasInstructions: Boolean(cleanInstructions),
      voice,
    });

    const ok = sendRealtimeClientEvent(dc, {
      type: "response.create",
      response: {
        // AO64D-HF5_RESPONSE_CREATE_GA_SAFE:
        // Do not send response.modalities. Provider rejects it with:
        // "Unknown parameter: 'response.modalities'".
        output_modalities: ["audio"],
        audio: {
          output: {
            voice,
          },
        },
        instructions: responseInstructions,
        metadata: {
          source: "orkio_web",
          reason,
          marker: "AO64D-HF5_RESPONSE_CREATE_GA_SAFE",
        },
      },
    }, `${reason}:response_create`);

    if (ok) {
      try {
        console.log("REALTIME_RESPONSE_CREATE_SENT", {
          reason,
          hasInstructions: Boolean(cleanInstructions),
          hasInputText: Boolean(cleanInput),
          conversationItem: Boolean(conversationItem),
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } catch {}
    } else {
      rtcResponseInFlightRef.current = false;
      clearRealtimeResponseTimeout();
    }

    return ok;
  }

  function scheduleRealtimeActivationProbe(dc, source = "data_channel_open") {
    clearRealtimeActivationProbe();
    rtcActivationProbeSentRef.current = false;

    rtcActivationProbeTimerRef.current = setTimeout(() => {
      try {
        if (!realtimeModeRef.current || !rtcSessionIdRef.current) return;
        const currentDc = rtcDcRef.current || dc;
        if (!currentDc || currentDc.readyState !== "open") return;
        if (rtcLastResponseCreatedAtRef.current) return;
        if (rtcResponseInFlightRef.current) return;
        if (rtcActivationProbeSentRef.current) return;

        rtcActivationProbeSentRef.current = true;
        logRealtimeStep("ao66r:activation_probe_trigger", {
          source,
          sessionAgeMs: getRealtimeSessionAgeMs(),
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });

        const probe = buildRealtimeActivationProbeInstruction(rtcLanguageProfileRef.current);
        requestRealtimeSpokenResponse(currentDc, {
          reason: "activation_probe",
          conversationItem: true,
          inputText: probe.inputText,
          instructions: probe.instructions,
        });
      } catch (err) {
        logRealtimeStep("ao66r:activation_probe_failed", {
          source,
          message: err?.message || null,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } finally {
        rtcActivationProbeTimerRef.current = null;
      }
    }, 1200);
  }

  function announceRealtimeTimeboxStart(dc, seconds = REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS) {
    if (!dc || dc.readyState !== "open") return false;

    const maxSeconds = Math.max(1, Math.ceil(Number(seconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS)));
    const durationLabel = formatRealtimeDurationLabel(maxSeconds);
    const lang = normalizeRealtimeLanguageProfile(rtcLanguageProfileRef.current);

    const announcement =
      lang === "en"
        ? (
          isRealtimeTimeboxLimitedUser()
            ? `Efatà. Orkio is live in real time. We have up to ${durationLabel}. I will ask one short question at a time. What would you like to start with?`
            : "Efatà. Orkio is live in real time. You are in an unrestricted admin session. I will ask one short question at a time. What would you like to start with?"
        )
        : lang === "es"
          ? (
            isRealtimeTimeboxLimitedUser()
              ? `Efatà. Orkio está en tiempo real. Tenemos hasta ${durationLabel}. Haré una pregunta corta por vez. ¿Por dónde quieres empezar?`
              : "Efatà. Orkio está en tiempo real. Estás en una sesión de administrador sin límite público. Haré una pregunta corta por vez. ¿Por dónde quieres empezar?"
          )
          : (
            isRealtimeTimeboxLimitedUser()
              ? `Efatà. Orkio em tempo real. Temos até ${durationLabel}. Vou fazer uma pergunta curta por vez. Por onde você quer começar?`
              : "Efatà. Orkio em tempo real. Você está em uma sessão admin sem limite público. Vou fazer uma pergunta curta por vez. Por onde você quer começar?"
          );

    const activationInput =
      lang === "en"
        ? "Start this real-time voice session now with a short greeting and one opening question."
        : lang === "es"
          ? "Inicia ahora esta sesión de voz en tiempo real con un saludo breve y una pregunta inicial."
          : "Inicie agora esta sessão de voz em tempo real com uma saudação curta e uma pergunta inicial.";

    logRealtimeStep("ao68a_hf6r8:start_announcement_requested", {
      seconds: maxSeconds,
      durationLabel,
      languageProfile: lang,
      limited: Boolean(isRealtimeTimeboxLimitedUser()),
    });

    return requestRealtimeSpokenResponse(dc, {
      reason: "start_announcement",
      conversationItem: true,
      inputText: activationInput,
      instructions: announcement,
    });
  }

    function markRealtimePausedForBackground(reason = "mobile_background") {
    try {
      setV2vPhase("error");
      setV2vError(
        "Realtime pausado porque o PWA foi para segundo plano ou a tela foi bloqueada. Toque no ⚡ para reconectar."
      );
      setUploadStatus("⚡ Realtime pausado. Toque no ⚡ para reconectar.");
      setTimeout(() => setUploadStatus(""), 3500);
      logRealtimeStep("mobile:background_pause", { reason });
    } catch {}
  }

  async function startRealtime() {
    if (rtcConnectingRef.current) {
      console.warn("[Realtime] start skipped: already connecting");
      logRealtimeStep("start:skip_connecting");
      return;
    }

    if (isRealtimeTimeboxLimitedUser() && rtcCooldownRemaining > 0) {
      const label = formatRealtimeCountdown(rtcCooldownRemaining);
      logRealtimeStep("start:blocked_by_local_cooldown", { remaining_seconds: rtcCooldownRemaining });
      setRealtimeMode(false);
      realtimeModeRef.current = false;
      setV2vPhase("cooldown");
      updateRealtimePremiumStatus("cooldown", `O chat por texto continua disponível. Liberação em ${label}.`);
      setV2vError(`A voz em tempo real estará disponível novamente em ${label}. O chat por texto continua disponível.`);
      setUploadStatus(`⏳ Voz disponível novamente em ${label}. O chat por texto continua disponível.`);
      setTimeout(() => setUploadStatus(""), 3500);
      return;
    }

    rtcConnectingRef.current = true;
    try { rtcConversationStartedRef.current = false; } catch {}
    try { rtcPendingTimeboxSecondsRef.current = null; } catch {}
    try { setRtcOverlayForceClosed(false); } catch {}
    updateRealtimePremiumStatus("connecting", "Preparando microfone e sessão de voz.");
    try { setV2vPhase("connecting"); } catch {}
    try { console.log(ORKIO_AO61A_BUILD_MARKER, { event: "start_begin" }); console.log(ORKIO_AO61A_HF3_BUILD_MARKER, { event: "start_begin" }); console.log(ORKIO_AO61A_HF4_BUILD_MARKER, { event: "start_begin" }); } catch {}
    const startNonce = ++rtcStartNonceRef.current;

    try {
      try { console.log("REALTIME_START_BEGIN", { threadId, destSingle, sessionId: rtcSessionIdRef.current || null }); } catch {}
      logRealtimeStep('start:begin', { threadId, destSingle, summitRuntimeMode: summitRuntimeModeRef.current, summitLanguageProfile: summitLanguageProfileRef.current });
      setV2vError(null);
      setV2vPhase('connecting');
      setUploadStatus('⚡ Conectando Realtime (WebRTC)...');

      const realtimeBrowserPreflight = getRealtimeBrowserPreflight();
      logRealtimeStep("start:browser_preflight", realtimeBrowserPreflight);
      if (!realtimeBrowserPreflight.ok) {
        throw buildRealtimeDiagnosticError(
          String(realtimeBrowserPreflight.reason || "realtime_browser_preflight_failed").toUpperCase(),
          realtimePreflightMessage(realtimeBrowserPreflight.reason),
          realtimeBrowserPreflight
        );
      }

      // ORKIO_AO60J_REALTIME_FOREGROUND_WAKE_GUARD
      // Acquire as early as possible after user gesture/preflight so the phone does not auto-lock during setup.
      startRealtimeWakeLockGuard("start_preflight_ok");

      // ORKIO_AO60K_HF5_FRONTEND_MOBILE_REALTIME_RESTART_TRANSCRIPT_FIX
      // Always hard-reset stale mobile/WebRTC state before a new session.
      // If a backend session id exists, close it first without starting local cooldown:
      // the new /start response remains the source of truth.
      if (rtcSessionIdRef.current) {
        // AO68A-HF6R10:
        // Do not call stopRealtime() during pre-start cleanup.
        // It sends /api/realtime/end and turns failed warmups into consumed public quota.
        logRealtimeStep("ao68a_hf6r10:pre_start_local_cleanup_no_backend_end", {
          previousSessionId: rtcSessionIdRef.current || null,
          startNonce,
        });
        try { clearRealtimeResponseTimeout(); } catch {}
        try { clearRealtimeActivationProbe(); } catch {}
        try { clearRealtimeAutoResponseFallback(); } catch {}
        try { clearRealtimeStartupWatchdog(); } catch {}
        try { clearRealtimeAudioWatchdog(); } catch {}
        try { clearRealtimeIdleFollowup(); } catch {}
        try { clearRealtimeTimeboxTimer(); } catch {}
        try { clearRealtimeLivePoll(); } catch {}
      }
      hardResetRealtimeClientState("pre_start", { startNonce, noBackendEnd: true });

      resetRealtimeTranscriptSession("realtime_start");

      try { setRtcAuditEvents([]); } catch {}
      try { setRtcPunctStatus(null); } catch {}
      try { setSummitSessionScore(null); } catch {}


      const agentIdToSend = resolveHostAgentId(); // host agent depends on current routing mode
      const ORKIO_ENV = (typeof window !== "undefined" && window.__ORKIO_ENV__) ? window.__ORKIO_ENV__ : {};
      const envVoice = (ORKIO_ENV.VITE_REALTIME_VOICE || import.meta.env.VITE_REALTIME_VOICE || "").trim();
      const rtModel = (ORKIO_ENV.VITE_REALTIME_MODEL || import.meta.env.VITE_REALTIME_MODEL || "gpt-realtime-mini").trim();
      const effectiveRealtimeTtlSeconds = isRealtimeTimeboxLimitedUser()
        ? REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS
        : 3600;
      const magicEnabled = (ORKIO_ENV.VITE_REALTIME_MAGICWORDS || import.meta.env.VITE_REALTIME_MAGICWORDS || "true").toString().trim().toLowerCase() !== "false";
      rtcMagicEnabledRef.current = magicEnabled;

      // Voice priority: agent.voice_id (Admin) > env default > fallback Orkio warmth preset
      const selectedAgentObj = (agents || []).find(a => String(a.id) === String(agentIdToSend));
      const agentVoice = ((selectedAgentObj?.voice_id || selectedAgentObj?.voice || selectedAgentObj?.tts_voice || selectedAgentObj?.voiceId || "")).toString().trim();
      const rtVoice = coerceVoiceId(agentVoice || envVoice || ORKIO_DEFAULT_VOICE_ID);
      rtcVoiceRef.current = rtVoice;

      // AO68A-HF5: explicit Summit/platform mode + onboarding language propagation.
      // Before HF5, language_profile was only sent in Summit mode. Normal Realtime stayed on env/auto.
      const runtimeMode = summitRuntimeModeRef.current === "summit" ? "summit" : "platform";
      const onboardingLanguage = getUserOnboardingLanguage(user, onboardingForm);
      const languageProfile = normalizeRealtimeLanguageProfile(
        runtimeMode === "summit"
          ? (summitLanguageProfileRef.current || onboardingLanguage || "auto")
          : (onboardingLanguage || summitLanguageProfileRef.current || "auto")
      );
      rtcLanguageProfileRef.current = languageProfile;

      const realtimeStartPayload = {
        agent_id: agentIdToSend,
        thread_id: threadId || null,
        voice: rtVoice,
        model: rtModel,
        ttl_seconds: effectiveRealtimeTtlSeconds,
        language_profile: languageProfile,
        language: languageProfile,
      };

      const start = runtimeMode === "summit"
        ? await startSummitSession({
            ...realtimeStartPayload,
            mode: "summit",
            response_profile: "stage",
          })
        : await startRealtimeSession({
            ...realtimeStartPayload,
            mode: "platform",
            response_profile: "natural",
          });

      logRealtimeStep("start:language_profile_resolved", {
        runtimeMode,
        onboardingLanguage,
        languageProfile,
      });
      logRealtimeStep('start:session_ok', start);
      // ORKIO_AO60K_HF5B_FRONTEND_ENDED_AT_SECONDS_TIMEBOX_VERIFY
      // Runtime proof: confirms the active bundle received backend timebox policy.
      try {
        console.log("REALTIME_TIMEBOX_POLICY", {
          marker: ORKIO_AO60K_HF5B_BUILD_MARKER,
          ao61aMarker: ORKIO_AO61A_BUILD_MARKER,
          timebox: start?.timebox || null,
          canAccessAdmin: Boolean(canAccessAdmin),
          runtimeMode: summitRuntimeModeRef.current,
        });
      } catch {}
      // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
  // Harden 429/cooldown UX so Realtime never stays visually active after backend blocks /start.
  // ORKIO_AO60K_HF1_RUNTIME_TIMEBOX_SYNC
      // Backend is the source of truth. If backend says this session is limited,
      // force frontend counter/stop/cooldown even if the cached local user object
      // temporarily looks like admin/superadmin.
      try {
        const timebox = start?.timebox || {};
        const maxSeconds = Number(timebox?.max_seconds);
        const remainingSeconds = Number(timebox?.remaining_seconds);
        const cooldownSeconds = Number(timebox?.cooldown_seconds);
        const backendBypass = String(
          timebox?.bypass ||
          start?.bypass ||
          start?.timebox_bypass ||
          ""
        ).trim().toLowerCase();
        const adminBypassByBackend = backendBypass === "admin" || timebox?.admin_bypass === true;
        const limitedByBackend = (
          timebox?.limited === true ||
          String(timebox?.limited || "").trim().toLowerCase() === "true" ||
          (Number.isFinite(remainingSeconds) && remainingSeconds > 0) ||
          (Number.isFinite(maxSeconds) && maxSeconds > 0) ||
          (Number.isFinite(cooldownSeconds) && cooldownSeconds > 0)
        );
        const effectiveAdminBypass = Boolean(canAccessAdmin || adminBypassByBackend);
        const effectiveLimitedByBackend = (
          REALTIME_FRONTEND_HARD_TIMEBOX_ENABLED === true
            ? (effectiveAdminBypass ? false : Boolean(limitedByBackend))
            : false
        );
        rtcAdminTimeboxBypassRef.current = effectiveAdminBypass;
        setRtcAdminTimeboxBypass(effectiveAdminBypass);
        rtcBackendTimeboxLimitedRef.current = effectiveLimitedByBackend;
        setRtcBackendTimeboxLimited(effectiveLimitedByBackend);
        if (effectiveLimitedByBackend || isRealtimeTimeboxLimitedUser()) {
          rtcTimeboxPolicyRef.current = {
            maxSeconds: Number.isFinite(maxSeconds) && maxSeconds > 0 ? Math.ceil(maxSeconds) : REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS,
            remainingSeconds: Number.isFinite(remainingSeconds) && remainingSeconds > 0 ? Math.ceil(remainingSeconds) : null,
            cooldownSeconds: Number.isFinite(cooldownSeconds) && cooldownSeconds > 0 ? Math.ceil(cooldownSeconds) : REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS,
          };
          setRtcTimeboxRemaining(rtcTimeboxPolicyRef.current.remainingSeconds || rtcTimeboxPolicyRef.current.maxSeconds);
          logRealtimeStep("timebox:backend_policy_synced", {
            limited: Boolean(effectiveLimitedByBackend),
            maxSeconds: rtcTimeboxPolicyRef.current.maxSeconds,
            remainingSeconds: rtcTimeboxPolicyRef.current.remainingSeconds,
            cooldownSeconds: rtcTimeboxPolicyRef.current.cooldownSeconds,
            hf3Marker: ORKIO_AO61A_HF3_BUILD_MARKER,
          });
        } else {
          rtcTimeboxPolicyRef.current = null;
          setRtcTimeboxRemaining(null);
          clearRealtimeTimeboxTimer();
          try { setRtcCooldownRemaining(0); } catch {}
          try { rtcCooldownUntilRef.current = 0; } catch {}
          logRealtimeStep("timebox:admin_bypass_synced", {
            canAccessAdmin: Boolean(canAccessAdmin),
            adminBypassByBackend: Boolean(adminBypassByBackend),
            effectiveAdminBypass: Boolean(effectiveAdminBypass),
            limitedByBackend: Boolean(limitedByBackend),
            ttlSeconds: effectiveRealtimeTtlSeconds,
          });
        }
      } catch {}
      const EPHEMERAL_KEY = start?.client_secret?.value || start?.client_secret_value || start?.value || null;
      if (!EPHEMERAL_KEY) {
        logRealtimeStep('start:ephemeral_missing', start);
        throw new Error('Realtime token vazio');
      }
      logRealtimeStep('start:ephemeral_ok', { session_id: start?.session_id || null, thread_id: start?.thread_id || null });

      rtcSessionIdRef.current = start?.session_id || null;
      rtcSessionStartedAtRef.current = Date.now();
      clearRealtimePendingAutoStop();
      try { console.log("REALTIME_SESSION_STARTED", { sessionId: start?.session_id || null, threadId: start?.thread_id || threadId || null, marker: ORKIO_AO66R_HF4_BUILD_MARKER }); } catch {}
      setLastRealtimeSessionId(start?.session_id || null);
      rtcThreadIdRef.current = start?.thread_id || threadId || null;

      // ORKIO_AO60K_HF5_FRONTEND_MOBILE_REALTIME_RESTART_TRANSCRIPT_FIX
      // Show the visual timer immediately after /start 200 + backend timebox policy.
      // Do not wait for DataChannel.open; mobile can take longer and users must see the clock.
      try {
        const immediateTimeboxSeconds = resolveRealtimeStartTimeboxSeconds(start);
        try {
          console.log("REALTIME_TIMEBOX_STARTING", {
            marker: ORKIO_AO61A_BUILD_MARKER,
            hf3Marker: ORKIO_AO61A_HF3_BUILD_MARKER,
            previousMarker: ORKIO_AO60K_HF5B_BUILD_MARKER,
            immediateTimeboxSeconds,
            timebox: start?.timebox || null,
            policy: rtcTimeboxPolicyRef.current || null,
            backendTimeboxLimited: Boolean(rtcBackendTimeboxLimitedRef.current),
          });
        } catch {}
        // AO68A-HF6R8:
        // Public users see the clock after /start 200.
        // Admin/superadmin sessions remain live without public hard-stop.
        if (isRealtimeTimeboxLimitedUser()) {
          rtcPendingTimeboxSecondsRef.current = immediateTimeboxSeconds;
          setRtcTimeboxRemaining(immediateTimeboxSeconds);
          startRealtimeTimebox(immediateTimeboxSeconds, {
            force: true,
            source: "after_start_200_public_clock_open",
          });
          updateRealtimePremiumStatus("connecting", "Relógio aberto. Orkio fará a saudação inicial por voz.");
        } else {
          rtcPendingTimeboxSecondsRef.current = null;
          clearRealtimeTimeboxTimer();
          setRtcTimeboxRemaining(null);
          updateRealtimePremiumStatus("connecting", "Realtime ao vivo sem limite público. Orkio fará a saudação inicial por voz.");
        }
        startRealtimeStartupWatchdog(rtcSessionIdRef.current, "after_start_200");
      } catch {}
      // AO01_REALTIME_THREAD_FOCUS_GUARD:
      // Realtime pode receber thread_id do backend, mas não pode roubar
      // o foco de uma conversa já ativa/escolhida pelo usuário.
      if (start?.thread_id && !threadId && !activeThreadIdRef.current) {
        try { activateThread(start.thread_id, { clearMessages: true }); } catch {}
      }

      rtcEventQueueRef.current = [];
      rtcSeenBackendResponseIdsRef.current = new Set();
      if (rtcFlushTimerRef.current) { try { clearInterval(rtcFlushTimerRef.current); } catch {} }
      rtcFlushTimerRef.current = setInterval(() => { try { flushRealtimeEvents(); } catch {} }, 400);
      startRealtimeLivePoll();

      const pc = new RTCPeerConnection();
      rtcPcRef.current = pc;

      // AO01-HF6R17_REALTIME_AUDIO_OUTPUT_NEGOTIATION
      // Explicitly ask WebRTC to receive assistant audio. Relying only on the
      // microphone sender may leave the provider free to complete text events
      // without delivering a playable remote audio track.
      try {
        pc.addTransceiver("audio", { direction: "recvonly" });
        logRealtimeStep("audio:recvonly_transceiver_added");
      } catch (err) {
        logRealtimeStep("audio:recvonly_transceiver_failed", { message: err?.message || null });
      }

      // Remote audio output
      const audioEl = document.createElement('audio');
      audioEl.autoplay = true;
      audioEl.playsInline = true;
      audioEl.muted = false;
      audioEl.volume = 1;
      try { audioEl.controls = false; } catch {}
      try { audioEl.preload = "auto"; } catch {}
      try { audioEl.setAttribute("playsinline", ""); } catch {}
      try { audioEl.setAttribute("webkit-playsinline", ""); } catch {}
      try {
        audioEl.style.display = "none";
        document.body.appendChild(audioEl);
      } catch {}
      rtcAudioElRef.current = audioEl;

      pc.ontrack = (e) => {
        try {
          let remoteStream = e.streams?.[0] || rtcRemoteStreamRef.current || null;
          if (!remoteStream && e.track) {
            remoteStream = new MediaStream();
          }
          if (remoteStream && e.track && !remoteStream.getTracks?.().some((t) => t.id === e.track.id)) {
            try { remoteStream.addTrack(e.track); } catch {}
          }
          rtcRemoteStreamRef.current = remoteStream || null;
          if (rtcRemoteStreamRef.current && audioEl.srcObject !== rtcRemoteStreamRef.current) {
            audioEl.srcObject = rtcRemoteStreamRef.current;
          }
          logRealtimeStep("audio:ontrack", {
            kind: e.track?.kind || null,
            readyState: e.track?.readyState || null,
            streams: e.streams?.length || 0,
            remoteTracks: rtcRemoteStreamRef.current?.getTracks?.().length || 0,
          });
          ensureRealtimeAudioOutput("ontrack");
        } catch (err) {
          logRealtimeStep("audio:ontrack_failed", { message: err?.message || null });
        }
      };

      // Mic input
      let realtimeMicPermissionState = null;
      try {
        if (navigator?.permissions?.query) {
          const permissionStatus = await navigator.permissions.query({ name: "microphone" });
          realtimeMicPermissionState = permissionStatus?.state || null;
          logRealtimeStep("start:mic_permission_state", { state: realtimeMicPermissionState });
          if (realtimeMicPermissionState === "denied") {
            throw buildRealtimeDiagnosticError(
              "MIC_PERMISSION_DENIED",
              "O microfone está bloqueado para este PWA. Libere a permissão de microfone nas configurações do navegador/app e tente novamente.",
              { permissionState: realtimeMicPermissionState }
            );
          }
        }
      } catch (permissionErr) {
        if (permissionErr?.code === "MIC_PERMISSION_DENIED") throw permissionErr;
        logRealtimeStep("start:mic_permission_probe_unavailable", { message: permissionErr?.message || null });
      }

      logRealtimeStep('start:request_mic');
      const micConstraints = {
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          sampleRate: 16000,
        },
        video: false,
      };
      let ms;
      try {
        ms = await navigator.mediaDevices.getUserMedia(micConstraints);
      } catch (micPrimaryErr) {
        logRealtimeStep("start:mic_primary_failed", {
          name: micPrimaryErr?.name || null,
          message: micPrimaryErr?.message || null,
          permissionState: realtimeMicPermissionState,
        });
        try {
          ms = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
          logRealtimeStep("start:mic_fallback_ok");
        } catch (micFallbackErr) {
          logRealtimeStep("start:mic_fallback_failed", {
            name: micFallbackErr?.name || null,
            message: micFallbackErr?.message || null,
            permissionState: realtimeMicPermissionState,
          });
          const denied = String(micFallbackErr?.name || micPrimaryErr?.name || "").toLowerCase().includes("notallowed");
          throw buildRealtimeDiagnosticError(
            denied ? "MIC_PERMISSION_DENIED" : "MIC_GET_USER_MEDIA_FAILED",
            denied
              ? "O microfone está bloqueado para este PWA. Libere a permissão de microfone nas configurações do navegador/app e tente novamente."
              : "Não consegui capturar o áudio do microfone neste dispositivo. Tente novamente, revise as permissões ou continue por texto.",
            {
              primaryName: micPrimaryErr?.name || null,
              primaryMessage: micPrimaryErr?.message || null,
              fallbackName: micFallbackErr?.name || null,
              fallbackMessage: micFallbackErr?.message || null,
              permissionState: realtimeMicPermissionState,
            }
          );
        }
      }
      const rawTrack = ms.getAudioTracks?.()[0] || ms.getTracks?.()[0] || null;
      if (!rawTrack) throw new Error("Microfone indisponível");

      let outboundStream = ms;
      let outboundTrack = rawTrack;

      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx({ sampleRate: 16000, latencyHint: "interactive" });
          const source = ctx.createMediaStreamSource(ms);
          const gainNode = ctx.createGain();
          gainNode.gain.value = 0.75;
          const destination = ctx.createMediaStreamDestination();
          source.connect(gainNode);
          gainNode.connect(destination);
          const processedTrack = destination.stream.getAudioTracks?.()[0] || null;
          if (processedTrack) {
            outboundStream = destination.stream;
            outboundTrack = processedTrack;
            rtcAudioProcessingRef.current = { ctx, source, gainNode, destination, rawStream: ms };
          } else {
            try { ctx.close?.(); } catch {}
          }
        }
      } catch (audioErr) {
        console.warn("[Realtime] mic processing chain unavailable, using raw track", audioErr);
      }

      logRealtimeStep('start:mic_ok', { label: outboundTrack?.label || null, readyState: outboundTrack?.readyState || null });
      queueRealtimeTelemetry('mic_ok', { label: outboundTrack?.label || null, readyState: outboundTrack?.readyState || null });
      outboundTrack.onended = () => {
        try {
          logRealtimeStep("mic:ended");
          if (realtimeModeRef.current) {
            void activateSilentRealtimeFallback("mic_ended");
          }
        } catch {}
      };
      pc.addTrack(outboundTrack, outboundStream);

      // Events channel
      const dc = pc.createDataChannel('oai-events');
      rtcDcRef.current = dc;

      pc.onconnectionstatechange = () => {
        const state = pc.connectionState || "unknown";
        logRealtimeStep("pc:connection_state", { state });
        queueRealtimeTelemetry("pc_connection_state", { state, iceState: pc.iceConnectionState || null, signalingState: pc.signalingState || null });
        if (state === "failed" || state === "disconnected" || state === "closed") {
          flushRealtimePartialTranscript(`pc_${state}_partial_flush`);
          setV2vError(`Realtime connection ${state}`);
          if (realtimeModeRef.current) void activateSilentRealtimeFallback(`pc_${state}`);
        } else if (state === "connected") {
          ensureRealtimeAudioOutput("pc_connected");
        }
      };

      dc.addEventListener("close", () => {
        logRealtimeStep("dc:close");
        queueRealtimeTelemetry("datachannel_close", { readyState: dc.readyState || null });
        flushRealtimePartialTranscript("dc_close_partial_flush");
        rtcResponseInFlightRef.current = false;
        if (realtimeModeRef.current) {
          setV2vPhase("error");
          setV2vError("Realtime channel closed");
          void activateSilentRealtimeFallback("dc_closed");
        }
      });

      dc.addEventListener("error", (err) => {
        console.warn("[Realtime] datachannel error", err);
        logRealtimeStep("dc:error", { message: err?.message || null });
        queueRealtimeTelemetry("datachannel_error", { message: err?.message || null, readyState: dc.readyState || null });
      });

            dc.addEventListener('open', () => {
        queueRealtimeTelemetry("datachannel_open", { readyState: dc.readyState || null, pcState: pc.connectionState || null, iceState: pc.iceConnectionState || null });
        setV2vPhase('listening');
        updateRealtimePremiumStatus("listening", "📝 Transcrição ativa");

        const activeTimeboxSeconds = isRealtimeTimeboxLimitedUser()
          ? Math.max(
              1,
              Math.ceil(Number(start?.timebox?.max_seconds || rtcTimeboxPolicyRef.current?.maxSeconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS))
            )
          : 3600;

        if (isRealtimeTimeboxLimitedUser()) {
          const durationLabel = formatRealtimeDurationLabel(activeTimeboxSeconds);
          const cooldownSeconds = Math.max(
            1,
            Math.ceil(Number(rtcTimeboxPolicyRef.current?.cooldownSeconds || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS))
          );
          const cooldownLabel = formatRealtimeDurationLabel(cooldownSeconds);
          setUploadStatus(`⚡ Orkio em tempo real — até ${durationLabel}. Depois, nova voz em ${cooldownLabel}. Texto liberado.`);
          setTimeout(() => setUploadStatus(''), 3500);
          if (!rtcPendingTimeboxSecondsRef.current) {
            rtcPendingTimeboxSecondsRef.current = resolveRealtimeStartTimeboxSeconds({ timebox: rtcTimeboxPolicyRef.current });
          }
          setRtcTimeboxRemaining(rtcPendingTimeboxSecondsRef.current || activeTimeboxSeconds);
        } else {
          setUploadStatus('⚡ Realtime admin ativo — sem limite público.');
          setTimeout(() => setUploadStatus(''), 1500);
          rtcPendingTimeboxSecondsRef.current = null;
          clearRealtimeTimeboxTimer();
          setRtcTimeboxRemaining(null);
        }

        startRealtimeAudioWatchdog();
        clearRealtimeStartupWatchdog();
        startRealtimeWakeLockGuard("data_channel_open");
        ensureRealtimeAudioOutput("data_channel_open");

        // AO68A-HF6R8 — Realtime transcription follows onboarding language and keeps audio response armed.
        try {
          const envLang = String(
            window.__ORKIO_ENV__?.VITE_REALTIME_TRANSCRIBE_LANGUAGE ||
            import.meta.env.VITE_REALTIME_TRANSCRIBE_LANGUAGE ||
            ""
          ).trim();

          const preferredLang = normalizeRealtimeLanguageProfile(
            rtcLanguageProfileRef.current ||
            (summitRuntimeModeRef.current === "summit" ? summitLanguageProfileRef.current : "") ||
            envLang ||
            "auto"
          );

          const langHint = resolveRealtimeTranscriptionLanguage(preferredLang);
          const transcriptionModel = String(
            window.__ORKIO_ENV__?.VITE_REALTIME_TRANSCRIBE_MODEL ||
            import.meta.env.VITE_REALTIME_TRANSCRIBE_MODEL ||
            "gpt-4o-mini-transcribe"
          ).trim() || "gpt-4o-mini-transcribe";

          const transcription = { model: transcriptionModel };
          if (langHint) transcription.language = langHint;

          const realtimeInstructions =
            preferredLang === "en"
              ? "You are Orkio in real time. Start by speaking first. Keep the conversation focused on the user's last clear answer. Ask one short question at a time. If the audio is unclear, ask the user to repeat."
              : preferredLang === "es"
                ? "Eres Orkio en tiempo real. Empieza hablando primero. Mantén la conversación enfocada en la última respuesta clara del usuario. Haz una pregunta corta por vez. Si el audio no está claro, pide que el usuario repita."
                : preferredLang === "pt"
                  ? "Você é Orkio em tempo real. Comece falando primeiro. Mantenha a conversa focada na última resposta clara do usuário. Faça uma pergunta curta por vez. Se o áudio estiver confuso, peça para o usuário repetir."
                  : "You are Orkio in real time. Start by speaking first. Answer in the same language the user is using. Keep the conversation focused and ask one short question at a time.";

          try {
            console.log("REALTIME_TRANSCRIPTION_LANGUAGE", {
              marker: "AO68A-HF6R8_REALTIME_RESPONSE_CREATE_AUDIO_ARMING",
              envLang,
              preferredLang,
              langHint,
              transcriptionModel,
              vadThreshold: REALTIME_SERVER_VAD_THRESHOLD,
              vadSilenceMs: REALTIME_SERVER_VAD_SILENCE_MS,
              vadPrefixMs: REALTIME_SERVER_VAD_PREFIX_MS,
            });
          } catch {}

          sendRealtimeClientEvent(dc, {
            type: "session.update",
            session: {
              type: "realtime",
              // AO64D-HF5_RESPONSE_CREATE_GA_SAFE:
              // Do not send session.modalities. Use output_modalities only.
              output_modalities: ["audio"],
              audio: {
                input: {
                  transcription,
                  turn_detection: {
                    type: "server_vad",
                    threshold: REALTIME_SERVER_VAD_THRESHOLD,
                    silence_duration_ms: REALTIME_SERVER_VAD_SILENCE_MS,
                    prefix_padding_ms: REALTIME_SERVER_VAD_PREFIX_MS,
                    create_response: true,
                    interrupt_response: true
                  }
                },
                output: {
                  voice: rtcVoiceRef.current
                }
              },
              instructions: realtimeInstructions
            }
          }, "session_update_audio_vad");
        } catch (err) {
          logRealtimeStep("runtime:transcription_language_update_failed", { message: err?.message || null });
        }

        // AO66R: send a proof-of-audio greeting and, if the provider does not emit
        // response.created quickly, send one fallback conversation item + response.create.
        // This separates "session/call opened" from "audio response actually activated".
        const greetingSent = announceRealtimeTimeboxStart(dc, activeTimeboxSeconds);
        queueRealtimeTelemetry("greeting_sent", { sent: Boolean(greetingSent), activeTimeboxSeconds });
        scheduleRealtimeActivationProbe(dc, "data_channel_open");
      });

      dc.addEventListener('message', (e) => {
        try {
          const ev = JSON.parse(e.data);

          try {
            const eventTypeForLog = String(ev?.type || "");
            console.log("REALTIME_SERVER_EVENT", {
              type: eventTypeForLog,
              response_id: ev?.response?.id || ev?.response_id || null,
              item_id: ev?.item?.id || ev?.item_id || null,
              marker: ORKIO_AO66R_HF4_BUILD_MARKER,
            });
          } catch {}

          try {
            const eventType = String(ev?.type || "");
            const assistantFinalEvent = (
              eventType === "response.output_text.done" ||
              eventType === "response.output_audio_transcript.done" ||
              eventType === "response.audio_transcript.done" ||
              eventType === "response.audio_transcript.final" ||
              eventType === "response.text.done" ||
              eventType === "response.done"
            );
            if (assistantFinalEvent) {
              const extractedAssistantText = extractRealtimeAssistantTextFromEvent(ev);
              console.log("REALTIME_ASSISTANT_TRANSCRIPT_EVENT", {
                marker: ORKIO_AO61A_HF3_BUILD_MARKER,
                hf4Marker: ORKIO_AO61A_HF4_BUILD_MARKER,
                type: eventType,
                hasText: Boolean(extractedAssistantText),
                length: extractedAssistantText.length,
              });
              if (extractedAssistantText) {
                clearRealtimeResponseTimeout();
                clearRealtimeAutoResponseFallback();
                if (eventType === "response.done") rtcResponseInFlightRef.current = false;
                scheduleRealtimeAssistantFinalCommit(extractedAssistantText, { source: eventType, delayMs: eventType === "response.done" ? 150 : 1100 });
              }
            }
          } catch {}

                    // Turn arming + optional Magic Words (B3)
          // server_vad + create_response=true is the source of truth.
          // We do not auto-fire response.create on final transcript here; we wait for the server
          // to emit the response events, while still allowing optional manual / magic-word triggers
          // when explicitly requested by the user.
          if (ev?.type === 'conversation.item.input_audio_transcription.completed') {
            const raw = (ev?.transcript || ev?.text || ev?.result?.transcript || '').toString();
            try {
              console.log("REALTIME_USER_FINAL_TRANSCRIPT", {
                transcript: raw,
                length: raw.length,
                marker: ORKIO_AO66R_HF4_BUILD_MARKER,
              });
            } catch {}
            updateRealtimePremiumStatus("transcribing", "📝 Transcrição ativa");
            queueRealtimeEvent({ event_type: 'transcript.final', role: 'user', content: raw, is_final: true });
            try {} catch {}
            rtcLastFinalTranscriptRef.current = raw;
            appendRealtimeTranscriptTurn("user", raw, { source: "input_audio_transcription.completed" });
            markRealtimeUserActivity();

            Promise.resolve(guardAndMaybeBlockRealtimeTranscript(raw)).then((blocked) => {
              if (blocked) return;
              setRtcReadyToRespond(!!raw.trim());
              const norm = raw.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
              const endsWithCmd = (s, cmd) => s === cmd || s.endsWith(' ' + cmd);
              const isMagic = endsWithCmd(norm, 'continue') || endsWithCmd(norm, 'please') || endsWithCmd(norm, 'prossiga') || endsWithCmd(norm, 'por favor');
              if (rtcMagicEnabledRef.current && isMagic) {
                try {
                  if (rtcLastMagicRef.current !== norm) {
                    rtcLastMagicRef.current = norm;
                    triggerRealtimeResponse("magic");
                  }
                } catch (err) {
                  console.warn('[Realtime] magic trigger failed', err);
                }
              } else if (raw.trim()) {
                // AO01-HF6R18:
                // Public-beta/timeboxed users do not run the backend multi-agent turn
                // (see AO60G_REALTIME_MULTI_AGENT_SUPPRESSED), so they must not depend
                // only on server_vad.create_response. In production evidence, Remshire
                // users reached input_audio_transcription.completed but no response.*
                // audio events followed, while Admin worked through the unrestricted
                // agent/backend path. For limited sessions, force exactly one client
                // response.create immediately after the final transcript.
                setRtcReadyToRespond(true);
                const shouldForceLimitedAudio = isRealtimeTimeboxLimitedUser();
                logRealtimeStep('ao01_hf6r18:final_transcript_response_policy', {
                  limited: Boolean(shouldForceLimitedAudio),
                  transcriptLen: raw.length,
                  responseInFlight: Boolean(rtcResponseInFlightRef.current),
                  marker: ORKIO_AO66R_HF4_BUILD_MARKER,
                });
                if (shouldForceLimitedAudio) {
                  try {
                    triggerRealtimeResponse("public_beta_force_audio_after_final_transcript");
                  } catch (err) {
                    logRealtimeStep('ao01_hf6r18:public_beta_force_audio_failed', {
                      message: err?.message || null,
                      marker: ORKIO_AO66R_HF4_BUILD_MARKER,
                    });
                    scheduleRealtimeAutoResponseFallback(raw, "public_beta_force_audio_retry");
                  }
                } else {
                  // Admin/unlimited sessions preserve the existing behavior to avoid
                  // duplicating backend multi-agent responses such as Chris/Orion.
                  scheduleRealtimeAutoResponseFallback(raw, "input_audio_transcription.completed_force_audio");
                }
              }
            });
          }
// Basic telemetry + optional live captions
          if ((ev?.type === 'response.text.delta' || ev?.type === 'response.output_text.delta') && ev?.delta) {
            clearRealtimeResponseTimeout();
            rtcTextBufRef.current += ev.delta;
          }
          if (ev?.type === 'response.created') {
            queueRealtimeTelemetry("session_activated", { source: "response.created", response_id: ev?.response?.id || ev?.response_id || null });
            try {
              console.log("REALTIME_ASSISTANT_RESPONSE_RECEIVED", {
                type: ev?.type,
                response_id: ev?.response?.id || ev?.response_id || null,
                marker: ORKIO_AO66R_HF4_BUILD_MARKER,
              });
            } catch {}
            clearRealtimeResponseTimeout();
            clearRealtimeActivationProbe();
            clearRealtimeAutoResponseFallback();
            rtcLastResponseCreatedAtRef.current = Date.now();
            rtcActivationProbeSentRef.current = false;
            rtcResponseInFlightRef.current = true;
            setV2vPhase('responding');
            updateRealtimePremiumStatus("responding", "Orkio está respondendo por voz.");
            rtcTextBufRef.current = '';
            rtcAudioTranscriptBufRef.current = '';
            rtcLastAssistantFinalRef.current = '';
            rtcAssistantFinalCommittedRef.current = false;
            rtcAssistantFinalMessageIdRef.current = null;
            rtcAssistantFinalTextRef.current = "";
            rtcAssistantPendingFinalTextRef.current = "";
            rtcAssistantPendingFinalSourceRef.current = "";
            clearRealtimeAssistantPendingFinalTimer();
          }
          if (ev?.type === 'response.output_item.added') {
            clearRealtimeResponseTimeout();
          }
          if (ev?.type === 'response.content_part.added') {
            clearRealtimeResponseTimeout();
          }
          if (ev?.type === 'response.text.done') {
            clearRealtimeResponseTimeout();
            rtcResponseInFlightRef.current = false;
            const t = (rtcTextBufRef.current || '').trim();
            rtcTextBufRef.current = '';
            rtcAudioTranscriptBufRef.current = '';
            if (t) {
              logRealtimeStep('runtime:response_finalized_pending', { source: 'response.text.done', finalText: t, marker: ORKIO_AO61A_HF4_BUILD_MARKER });
              scheduleRealtimeAssistantFinalCommit(t, { source: 'response.text.done', delayMs: 1100 });
            }
          }
          // Audio transcript (when model outputs audio without text)
          if (ev?.type === 'response.audio.delta' || ev?.type === 'response.output_audio.delta') {
            queueRealtimeTelemetry("assistant_audio_started", { source: ev?.type || "response.audio.delta" });
            clearRealtimeResponseTimeout();
            try { ensureRealtimeAudioOutput("response_audio_delta"); } catch {}
          }
          if ((ev?.type === 'response.audio_transcript.delta' || ev?.type === 'response.output_audio_transcript.delta') && ev?.delta) {
            clearRealtimeResponseTimeout();
            rtcAudioTranscriptBufRef.current = (rtcAudioTranscriptBufRef.current || '') + ev.delta;
            try {
              const preview = (rtcAudioTranscriptBufRef.current || "").trim();
              if (preview) {
                setUploadStatus(`🔊 Orkio: ${preview.slice(-90)}`);
              }
            } catch {}
          }
          if (ev?.type === 'response.audio_transcript.done' || ev?.type === 'response.audio_transcript.final') {
            clearRealtimeResponseTimeout();
            rtcResponseInFlightRef.current = false;
            const at = ((rtcAudioTranscriptBufRef.current || '') + (ev?.transcript || '')).trim();
            rtcAudioTranscriptBufRef.current = '';
            if (at) {
              logRealtimeStep('runtime:response_finalized_pending', { source: 'response.audio_transcript', finalText: at, marker: ORKIO_AO61A_HF4_BUILD_MARKER });
              scheduleRealtimeAssistantFinalCommit(at, { source: 'response.audio_transcript', delayMs: 1100 });
            }
          }

          if (ev?.type === 'response.output_item.done') {
            clearRealtimeResponseTimeout();
            logRealtimeStep('runtime:response_output_item_done', {
              item_id: ev?.item?.id || ev?.item_id || null,
            });
          }

          if (ev?.type === 'response.done') {
            clearRealtimeResponseTimeout();
            clearRealtimeActivationProbe();
            clearRealtimeAutoResponseFallback();
            rtcResponseInFlightRef.current = false;
            startRealtimeConversationTimeboxIfNeeded("response.done_first_assistant_completed");
            if (!rtcConversationStartedRef.current) updateRealtimePremiumStatus("listening", "📝 Transcrição ativa");

            const textFinal = (rtcTextBufRef.current || '').trim();
            const audioFinal = ((rtcAudioTranscriptBufRef.current || '') + (ev?.transcript || '')).trim();
            const pendingFinal = (rtcAssistantPendingFinalTextRef.current || '').trim();
            const extractedFinal = extractRealtimeAssistantTextFromEvent(ev);
            const finalText = pickLongerRealtimeAssistantText(textFinal, audioFinal, pendingFinal, extractedFinal);

            rtcTextBufRef.current = '';
            rtcAudioTranscriptBufRef.current = '';
            rtcAssistantPendingFinalTextRef.current = '';
            rtcAssistantPendingFinalSourceRef.current = '';
            clearRealtimeAssistantPendingFinalTimer();

            if (finalText) {
              logRealtimeStep('runtime:response_finalized', {
                source: 'response.done:longest',
                finalText,
                marker: ORKIO_AO61A_HF4_BUILD_MARKER,
                textLen: textFinal.length,
                audioLen: audioFinal.length,
                pendingLen: pendingFinal.length,
                extractedLen: extractedFinal.length,
              });
              commitRealtimeAssistantFinal(finalText, { source: 'response.done:longest' });
            } else {
              logRealtimeStep('runtime:response_done_without_text', {
                source: 'response.done',
                textBuf: textFinal.length,
                audioTranscriptBuf: audioFinal.length,
                pendingBuf: pendingFinal.length,
              });
            }
          }

          if (ev?.type === 'error') {
            clearRealtimeResponseTimeout();
            clearRealtimeAutoResponseFallback();
            rtcResponseInFlightRef.current = false;
            console.warn('[Realtime] error', ev);
            logRealtimeStep('runtime:error_event', ev);
            setV2vError(normalizeUserFacingRuntimeMessage(ev?.error?.message || 'Erro Realtime', 'realtime'));
            setV2vPhase('error');
            void activateSilentRealtimeFallback('realtime_error', { disarm: false });
          }
        } catch (err) {
          console.warn('[Realtime] DataChannel handler error', err, e?.data);
          logRealtimeStep('runtime:message_handler_error', {
            message: err?.message || null,
            raw: e?.data || null,
          });
        }
      });

      // SDP handshake
      logRealtimeStep('start:create_offer');
      queueRealtimeTelemetry("offer_create_start", { pcState: pc.connectionState || null, iceState: pc.iceConnectionState || null });
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      logRealtimeStep('start:local_description_set', { sdpLength: offer?.sdp?.length || 0 });
      queueRealtimeTelemetry("local_description_set", { sdpLength: offer?.sdp?.length || 0, signalingState: pc.signalingState || null });

      const sdpAbortController = new AbortController();
      const sdpTimeout = setTimeout(() => {
        try { sdpAbortController.abort(); } catch {}
      }, 20000);

      let sdpResponse;
      try {
        queueRealtimeTelemetry("sdp_fetch_start", { endpoint: "https://api.openai.com/v1/realtime/calls", model: start?.model || null });
        sdpResponse = await fetch('https://api.openai.com/v1/realtime/calls', {
          method: 'POST',
          body: offer.sdp,
          signal: sdpAbortController.signal,
          headers: {
            Authorization: `Bearer ${EPHEMERAL_KEY}`,
            'Content-Type': 'application/sdp',
          },
        });
      } catch (sdpFetchErr) {
        logRealtimeStep("start:sdp_fetch_failed", {
          name: sdpFetchErr?.name || null,
          message: sdpFetchErr?.message || null,
        });
        queueRealtimeTelemetry("sdp_fetch_failed", { name: sdpFetchErr?.name || null, message: sdpFetchErr?.message || null, aborted: sdpFetchErr?.name === "AbortError" });
        throw buildRealtimeDiagnosticError(
          "REALTIME_SDP_FETCH_FAILED",
          "Não consegui concluir a conexão de voz em tempo real com o provedor agora. O chat continua disponível por texto.",
          {
            name: sdpFetchErr?.name || null,
            message: sdpFetchErr?.message || null,
            aborted: sdpFetchErr?.name === "AbortError",
          }
        );
      } finally {
        try { clearTimeout(sdpTimeout); } catch {}
      }

      const sdpText = await sdpResponse.text().catch(() => '');
      if (!sdpResponse.ok) {
        logRealtimeStep('start:sdp_error', { status: sdpResponse.status, body: sdpText || sdpResponse.statusText });
        queueRealtimeTelemetry("sdp_error", { status: sdpResponse.status, body: String(sdpText || sdpResponse.statusText || "").slice(0, 800) });
        throw new Error(`SDP handshake falhou (${sdpResponse.status}): ${sdpText || sdpResponse.statusText}`);
      }

      logRealtimeStep('start:sdp_ok', { answerLength: sdpText.length });
      queueRealtimeTelemetry("sdp_ok", { answerLength: sdpText.length, status: sdpResponse.status });
      const answer = { type: 'answer', sdp: sdpText };
      await pc.setRemoteDescription(answer);
      queueRealtimeTelemetry("remote_description_set", { signalingState: pc.signalingState || null, pcState: pc.connectionState || null, iceState: pc.iceConnectionState || null });
      logRealtimeStep('start:ready', { sessionId: start?.session_id || null, threadId: start?.thread_id || threadId || null });

    } catch (e) {
      console.error('[Realtime] startRealtime error', e);
      queueRealtimeTelemetry("start_catch", { code: e?.code || null, status: e?.status || null, message: e?.message || null, userMessage: e?.userMessage || null });
      logRealtimeStep('start:catch', {
        code: e?.code || null,
        status: e?.status || null,
        url: e?.url || null,
        userMessage: e?.userMessage || null,
        message: e?.message || 'Falha ao iniciar Realtime',
        stack: e?.stack || null,
        sessionId: rtcSessionIdRef.current || null,
        threadId: rtcThreadIdRef.current || threadId || null,
      });
      setV2vPhase('error');
      if (isRealtimeCooldownOrRateLimitError(e)) {
        // AO68A-HF6R9:
        // /start cooldown must not trigger stopRealtime(), because stopRealtime() calls
        // /api/realtime/end and can close/recount an already warming session.
        const waitSeconds = applyRealtimeCooldownFromError(e, "start_blocked_by_cooldown");
        clearRealtimeResponseTimeout();
        clearRealtimeActivationProbe();
        clearRealtimeAutoResponseFallback();
        clearRealtimeStartupWatchdog();
        rtcConnectingRef.current = false;
        const label = formatRealtimeCountdown(waitSeconds);
        setRealtimeMode(false);
        realtimeModeRef.current = false;
        setV2vPhase("cooldown");
        setV2vError(`A voz em tempo real estará disponível novamente em ${label}. O chat por texto continua disponível.`);
        updateRealtimePremiumStatus("cooldown", `O chat por texto continua disponível. Liberação em ${label}.`);
        return;
      }
      const friendlyRealtimeError = normalizeUserFacingRuntimeMessage(
        [
          e?.code,
          e?.status ? `status_${e.status}` : "",
          e?.userMessage,
          e?.message,
        ].filter(Boolean).join(" | ") || "Falha ao iniciar Realtime",
        "realtime"
      );
      setV2vError(friendlyRealtimeError);
      setUploadStatus("❌ Realtime indisponível. Você pode continuar por texto.");
      setTimeout(() => setUploadStatus(""), 3500);

      // AO68A-HF6R8: do not call /api/realtime/end immediately after initial
      // browser/WebRTC/SDP failure. Keep the backend evidence intact and avoid
      // killing a session that may still be stabilizing on mobile/PWA.
      logRealtimeStep("ao68a_hf6r8:start_error_no_early_end", {
        code: e?.code || null,
        status: e?.status || null,
        message: e?.message || null,
        sessionId: rtcSessionIdRef.current || null,
      });
      hardResetRealtimeClientState("start_error_local_reset_only");
    } finally {
      rtcConnectingRef.current = false;
    }
  }

  
  function triggerRealtimeResponse(reason = "manual") {
    try {
      const dc = rtcDcRef.current;
      if (!dc || dc.readyState !== "open") {
        throw new Error("DataChannel não está aberto");
      }
      if (rtcResponseInFlightRef.current) {
        logRealtimeStep("response:skip_inflight", { reason });
        return;
      }
      const lastTranscript = (rtcLastFinalTranscriptRef.current || "").trim();
      if (!lastTranscript) {
        logRealtimeStep("response:skip_empty", { reason });
        return;
      }
      rtcResponseInFlightRef.current = true;
      clearRealtimeResponseTimeout();
      clearRealtimeActivationProbe();
      clearRealtimeAutoResponseFallback();
      clearRealtimeIdleFollowup();
      rtcResponseTimeoutRef.current = setTimeout(() => {
        setUploadStatus("⌛ Realtime ainda processando...");
        setTimeout(() => setUploadStatus(""), 1200);
      }, 7000);
      requestRealtimeSpokenResponse(dc, {
        reason,
        conversationItem: true,
        inputText: lastTranscript,
        instructions: buildRealtimeVoiceInstruction(
          rtcLanguageProfileRef.current,
          lastTranscript
        ),
      });
      setRtcReadyToRespond(false);
      setV2vPhase("responding");
      setUploadStatus(reason === "magic" ? "✨ Command received — responding..." : reason === "auto_vad" ? "🎙️ Speech detected — responding..." : "▶️ Responding...");
      setTimeout(() => setUploadStatus(""), 1500);
    } catch (e) {
      rtcResponseInFlightRef.current = false;
      console.warn("[Realtime] triggerRealtimeResponse failed", e);
      logRealtimeStep("ao66a_hf3:trigger_response_failed_no_auto_end", {
        message: e?.message || null,
        sessionAgeMs: getRealtimeSessionAgeMs(),
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
      setUploadStatus("⚡ Não consegui disparar a resposta ainda. Mantive o Realtime aberto.");
      setTimeout(() => setUploadStatus(""), 2200);
      if (!shouldHoldRealtimeInsteadOfEnding("trigger_failed", getRealtimeSessionAgeMs())) {
        void activateSilentRealtimeFallback("trigger_failed");
      }
    }
  }


  // PATCH0100_27A: Realtime event logging (batched, non-blocking)
  function queueRealtimeEvent({ event_type, role, content = null, is_final = false, meta = null } = {}) {
    const sid = rtcSessionIdRef.current;
    if (!sid) return;
    rtcEventQueueRef.current.push({
      session_id: sid,
      client_event_id: (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID() : (`ce-${Date.now()}-${Math.random().toString(36).slice(2,10)}`),
      event_type,
      role,
      content,
      created_at: Math.floor(Date.now()/1000),
      is_final,
      meta,
    });
    try {
      if (is_final && (content || '').toString().trim()) {
        const item = {
          session_id: sid,
          event_type,
          role,
          content: (content || '').toString(),
          transcript_punct: null,
          created_at: Math.floor(Date.now()/1000),
        };
        setRtcAuditEvents(prev => prev.concat([item]));
      }
    } catch {}
  }

  async function flushRealtimeEvents() {
    const sid = rtcSessionIdRef.current;
    if (!sid) return;
    const q = rtcEventQueueRef.current || [];
    if (!q.length) return;
    // Take a snapshot to avoid races
    rtcEventQueueRef.current = [];
    try {
      await postRealtimeEventsBatch({ session_id: sid, events: q });
    } catch (err) {
      // On failure, put events back to try later (best-effort)
      rtcEventQueueRef.current = q.concat(rtcEventQueueRef.current || []);
      console.warn('[Realtime] events batch failed', err);
    }
  }

  // AO01-HF6R13 — WebRTC handshake telemetry bridge.
  // Backend logs showed /api/realtime/start 200 and polling, but no events:batch.
  // This helper writes every browser/WebRTC phase to /api/realtime/events:batch
  // so the next log proves where activation stops: mic, offer, SDP, remote answer,
  // DataChannel open/close/error, response.create or local catch.
  function queueRealtimeTelemetry(eventName, meta = {}) {
    try {
      const name = String(eventName || "").trim();
      if (!name) return;
      queueRealtimeEvent({
        event_type: name.startsWith("telemetry.") ? name : `telemetry.${name}`,
        role: "system",
        content: "",
        is_final: false,
        meta: {
          ...(meta && typeof meta === "object" ? meta : {}),
          ao01_hf6r13: true,
          session_age_ms: getRealtimeSessionAgeMs(),
          client_ts_ms: Date.now(),
        },
      });
      setTimeout(() => {
        try { void flushRealtimeEvents(); } catch {}
      }, 0);
    } catch (err) {
      try {
        console.warn("[Realtime] telemetry bridge failed", eventName, err);
      } catch {}
    }
  }



  function clearRealtimeLivePoll() {
    if (rtcLivePollTimerRef.current) {
      try { clearInterval(rtcLivePollTimerRef.current); } catch {}
      rtcLivePollTimerRef.current = null;
    }
  }

  function safeParseRealtimeMeta(meta) {
    if (!meta) return {};
    if (typeof meta === "object") return meta;
    try { return JSON.parse(meta); } catch { return {}; }
  }

  async function handleBackendRealtimeAssistantResponses(payload) {
    const sid = rtcSessionIdRef.current;
    if (!sid) return;

    const events = Array.isArray(payload?.events) ? payload.events : [];
    if (events.length) {
      setRtcAuditEvents(events);
    }

    const candidateEvents = events.filter((ev) => {
      const eventType = String(ev?.event_type || "").trim();
      const speakerType = String(ev?.speaker_type || ev?.role || "").trim().toLowerCase();
      return (
        (eventType === "response.final" || eventType === "transcript.final")
        && speakerType === "agent"
      );
    });

    for (const ev of candidateEvents) {
      const evId = String(ev?.id || "");
      if (!evId || rtcSeenBackendResponseIdsRef.current.has(evId)) continue;

      const meta = safeParseRealtimeMeta(ev?.meta);
      const content =
        String(
          ev?.transcript_punct ||
          ev?.transcript_raw ||
          ev?.content ||
          ""
        ).trim();

      if (!content) continue;

      rtcSeenBackendResponseIdsRef.current.add(evId);

      const agentName = String(ev?.agent_name || meta?.agent_name || "Orkio").trim() || "Orkio";
      const agentId = ev?.agent_id || ev?.speaker_id || meta?.agent_id || null;
      const resolvedVoice = resolveAgentVoice({
        agent_name: agentName,
        voice_id: ev?.voice_id || meta?.voice_id || null,
      });

      setMessages((prev) => {
        const exists = (prev || []).some((m) => String(m?.id || "") === evId);
        if (exists) return prev;
        return (prev || []).concat([{
          id: evId,
          role: "assistant",
          content,
          agent_id: agentId ? String(agentId) : null,
          agent_name: agentName,
          voice_id: resolvedVoice,
          created_at: Math.floor(Date.now() / 1000),
        }]);
      });

      setUploadStatus(`📝 ${agentName}: ${content.slice(0, 80)}${content.length > 80 ? '…' : ''}`);
      setTimeout(() => setUploadStatus(''), 2200);

      try {
        await playTts(content, agentId, {
          forceAuto: true,
          messageId: null,
          traceId: v2vTraceRef.current || null,
          voiceOverride: resolvedVoice,
        });
      } catch (err) {
        console.warn("[Realtime] backend response TTS failed", err);
      }
    }
  }

  function startRealtimeLivePoll() {
    clearRealtimeLivePoll();
    const sid = rtcSessionIdRef.current;
    if (!sid) return;

    rtcLivePollSessionIdRef.current = sid;

    const pollOnce = async () => {
      try {
        if (!realtimeModeRef.current || !rtcSessionIdRef.current) return;
        if (rtcSessionIdRef.current !== sid || rtcLivePollSessionIdRef.current !== sid) {
          logRealtimeStep("hf5:live_poll_stale_session_stopped", {
            pollSid: sid,
            currentSid: rtcSessionIdRef.current || null,
            livePollSid: rtcLivePollSessionIdRef.current || null,
          });
          clearRealtimeLivePoll();
          return;
        }
        const data = await getRealtimeSession({ session_id: sid, finals_only: true });
        await handleBackendRealtimeAssistantResponses(data || {});
      } catch (err) {
        console.warn("[Realtime] live poll failed", err);
      }
    };

    void pollOnce();
    rtcLivePollTimerRef.current = setInterval(() => { void pollOnce(); }, 1400);
    logRealtimeStep("hf5:live_poll_started", { sessionId: sid });
  }

  // PATCH0100_27_2B: finalize session on server + poll punctuated finals (best-effort)
  async function finalizeRealtimeSession(reason = 'client_stop') {
    const sid = rtcSessionIdRef.current;
    if (!sid) return;
    // stop timers
    if (rtcFlushTimerRef.current) { try { clearInterval(rtcFlushTimerRef.current); } catch {} rtcFlushTimerRef.current = null; }
    clearRealtimeLivePoll();
    // flush pending events
    try { await flushRealtimeEvents(); } catch {}
    // end session (best-effort)
    try { await endRealtimeSession({ session_id: sid, ended_at: Math.floor(Date.now() / 1000), meta: { reason } }); } catch {}

    // poll for punct updates (best-effort, bounded)
    try {
      setRtcPunctStatus('pending');
      const started = Date.now();
      const deadlineMs = 15000;
      let last = null;
      while (Date.now() - started < deadlineMs) {
        try {
          const data = await getRealtimeSession({ session_id: sid, finals_only: true });
          last = data;
          if (data?.events) {
            setRtcAuditEvents(data.events);
          }
          await handleBackendRealtimeAssistantResponses(data || {});
          if (data?.punct?.done) {
            setRtcPunctStatus('done');
            return;
          }
        } catch {}
        await new Promise(r => setTimeout(r, 900));
      }
      // timeout but still set last snapshot
      if (last?.events) setRtcAuditEvents(last.events);
      setRtcPunctStatus('timeout');
    } catch {
      setRtcPunctStatus('timeout');
    }
  }

  function normalizeRealtimeAssistantText(rawText) {
    return (rawText || "").toString().replace(/\s+/g, " ").trim();
  }

  function pickLongerRealtimeAssistantText(...texts) {
    let best = "";
    for (const t of texts) {
      const s = normalizeRealtimeAssistantText(t);
      if (s.length > best.length) best = s;
    }
    return best;
  }

  function clearRealtimeAssistantPendingFinalTimer() {
    try {
      if (rtcAssistantPendingFinalTimerRef.current) clearTimeout(rtcAssistantPendingFinalTimerRef.current);
    } catch {}
    rtcAssistantPendingFinalTimerRef.current = null;
  }

  function scheduleRealtimeAssistantFinalCommit(rawText, { source = "unknown", delayMs = 900 } = {}) {
    const candidate = normalizeRealtimeAssistantText(rawText);
    if (!candidate) return;
    const currentPending = normalizeRealtimeAssistantText(rtcAssistantPendingFinalTextRef.current || "");
    if (candidate.length >= currentPending.length) {
      rtcAssistantPendingFinalTextRef.current = candidate;
      rtcAssistantPendingFinalSourceRef.current = source;
    }
    clearRealtimeAssistantPendingFinalTimer();
    rtcAssistantPendingFinalTimerRef.current = setTimeout(() => {
      const pending = normalizeRealtimeAssistantText(rtcAssistantPendingFinalTextRef.current || "");
      const pendingSource = rtcAssistantPendingFinalSourceRef.current || source;
      rtcAssistantPendingFinalTextRef.current = "";
      rtcAssistantPendingFinalSourceRef.current = "";
      if (pending) commitRealtimeAssistantFinal(pending, { source: pendingSource });
    }, Math.max(150, Number(delayMs) || 900));
  }

  function extractRealtimeAssistantTextFromEvent(ev) {
    try {
      if (!ev || typeof ev !== "object") return "";
      const candidates = [
        ev.transcript,
        ev.text,
        ev.output_text,
        ev?.response?.output_text,
        ev?.item?.content?.[0]?.text,
        ev?.item?.content?.[0]?.transcript,
        ev?.content?.[0]?.text,
        ev?.content?.[0]?.transcript,
      ];
      for (const c of candidates) {
        const s = (c || "").toString().trim();
        if (s) return s;
      }

      const output = Array.isArray(ev?.response?.output) ? ev.response.output : [];
      for (const item of output) {
        const content = Array.isArray(item?.content) ? item.content : [];
        for (const part of content) {
          const s = (part?.text || part?.transcript || part?.audio_transcript || "").toString().trim();
          if (s) return s;
        }
      }
    } catch {}
    return "";
  }

  function commitRealtimeAssistantFinal(rawText, { source = 'unknown' } = {}) {
    const finalText = normalizeRealtimeAssistantText(rawText);
    if (!finalText) return;
    const dedupeKey = finalText
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();

    const previousText = normalizeRealtimeAssistantText(rtcAssistantFinalTextRef.current || "");
    const previousDedupe = previousText
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();

    if (rtcLastAssistantFinalRef.current === dedupeKey && finalText.length <= previousText.length) return;

    // HF4: allow a later, longer assistant transcript to upgrade the previously committed partial text.
    const existingMessageId = rtcAssistantFinalMessageIdRef.current;
    const isMeaningfulUpgrade = Boolean(
      rtcAssistantFinalCommittedRef.current
      && existingMessageId
      && finalText.length > Math.max(previousText.length + 12, Math.floor(previousText.length * 1.12))
      && dedupeKey !== previousDedupe
    );

    if (rtcAssistantFinalCommittedRef.current && !isMeaningfulUpgrade) {
      return;
    }

    rtcLastAssistantFinalRef.current = dedupeKey;
    rtcAssistantFinalCommittedRef.current = true;
    rtcAssistantFinalTextRef.current = finalText;
    appendRealtimeTranscriptTurn("assistant", finalText, { source });

    queueRealtimeEvent({ event_type: 'response.final', role: 'assistant', content: finalText, is_final: true, meta: { source, hf4: true, upgraded: isMeaningfulUpgrade } });

    try {
      const selectedAgentObj2 = (agents || []).find(a => String(a.id) === String(destSingle || ""));
      // AO64D-HF5_PUBLIC_REALTIME_SPEAKER_ORKIO
      // Runtime source labels like "response.done:longest" are telemetry, not public speaker names.
      const agentName2 = "Orkio";
      const agentId2 = selectedAgentObj2?.id || (destSingle || null);

      if (isMeaningfulUpgrade && existingMessageId) {
        setMessages((prev) => (prev || []).map((m) => (
          String(m?.id) === String(existingMessageId)
            ? { ...m, content: finalText, updated_at: Math.floor(Date.now() / 1000), meta: { ...(m?.meta || {}), realtime_transcript_upgraded: true } }
            : m
        )));
      } else {
        const mid = `rtc_ass_${Date.now()}_${Math.random().toString(16).slice(2)}`;
        rtcAssistantFinalMessageIdRef.current = mid;
        setMessages((prev) => prev.concat([{
          id: mid,
          role: "assistant",
          content: finalText,
          agent_id: agentId2 ? String(agentId2) : null,
          agent_name: agentName2,
          created_at: Math.floor(Date.now()/1000),
          meta: { realtime_assistant_transcript: true, source },
        }]));
      }
    } catch {}

    try {
      console.log("REALTIME_ASSISTANT_TRANSCRIPT_COMMIT", {
        marker: ORKIO_AO61A_HF4_BUILD_MARKER,
        source,
        length: finalText.length,
        upgraded: isMeaningfulUpgrade,
      });
    } catch {}

    // AO66R-HF4: if native Realtime audio does not play but assistant text arrived,
    // use the already validated classic TTS pipeline as a safe voice fallback.
    try {
      const selectedAgentObj3 = (agents || []).find(a => String(a.id) === String(destSingle || ""));
      const agentId3 = selectedAgentObj3?.id || (destSingle || null);
      console.log("REALTIME_TTS_FALLBACK_REQUESTED", {
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        source,
        length: finalText.length,
      });
      Promise.resolve(playTts(finalText, agentId3, { forceAuto: true }))
        .then(() => {
          try { console.log("REALTIME_TTS_FALLBACK_PLAYED", { marker: ORKIO_AO66R_HF4_BUILD_MARKER }); } catch {}
        })
        .catch((err) => {
          try { console.warn("REALTIME_TTS_FALLBACK_FAILED", err); } catch {}
        });
    } catch (err) {
      try { console.warn("REALTIME_TTS_FALLBACK_EXCEPTION", err); } catch {}
    }

    setUploadStatus('📝 ' + finalText.slice(0, 80) + (finalText.length > 80 ? '…' : ''));
    setTimeout(() => setUploadStatus(''), 2500);
    setTimeout(() => { try { scheduleRealtimeIdleFollowup(); } catch {} }, REALTIME_REARM_AFTER_ASSISTANT_MS);
  }

  async function downloadRealtimeAta() {
    try {
      const sid = rtcSessionIdRef.current;
      if (!sid) {
        setUploadStatus('ℹ️ Nenhuma sessão Realtime disponível para exportar relatório.');
        setTimeout(() => setUploadStatus(''), 2000);
        return;
      }
      const blob = await downloadRealtimeAtaFile({ session_id: sid });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `orkio-ata-${sid}.txt`;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      try { URL.revokeObjectURL(url); } catch {}
      setUploadStatus('⬇️ Baixando relatório executivo da sessão...');
      setTimeout(() => setUploadStatus(''), 1800);
    } catch (e) {
      console.error('[Realtime] download report failed', e);
      setUploadStatus('❌ Falha ao baixar ata.');
      setTimeout(() => setUploadStatus(''), 2000);
    }
  }

async function stopRealtime(reason = 'client_stop') {
    const sid = rtcSessionIdRef.current;
    const reasonTextEarly = String(reason || "client_stop");
    const sessionAgeMs = getRealtimeSessionAgeMs();

    let allowBackendEnd = isExplicitRealtimeEndReason(reasonTextEarly);

    // AO01-HF6R11_REALTIME_WARMUP_BACKEND_END_GATE:
    // A backend realtime session must NOT be ended/consumed while the WebRTC
    // activation is still warming up. Logs showed /api/realtime/start 200 followed
    // by /api/realtime/end 200 in ~0-2s, before any DataChannel/server event/audio.
    // That turns a failed activation into public cooldown.
    //
    // Session creation is not activation. Only a real conversation/audio event should
    // allow backend finalization. While rtcConversationStartedRef is still false,
    // suppress /api/realtime/end for early explicit UI toggles, page/app races,
    // hydration double-clicks, and mobile/PWA lifecycle glitches.
    const realtimeWarmupEndSuppressed = Boolean(
      sid &&
      allowBackendEnd &&
      !rtcConversationStartedRef.current &&
      Number.isFinite(Number(sessionAgeMs)) &&
      Number(sessionAgeMs) >= 0 &&
      Number(sessionAgeMs) < 180000
    );

    if (realtimeWarmupEndSuppressed) {
      allowBackendEnd = false;
      try {
        console.warn("AO01_HF6R11_REALTIME_BACKEND_END_SUPPRESSED_WARMUP", {
          reason: reasonTextEarly,
          sessionId: sid,
          sessionAgeMs,
          conversationStarted: Boolean(rtcConversationStartedRef.current),
        });
      } catch {}
      logRealtimeStep("ao01_hf6r11:backend_end_suppressed_warmup", {
        reason: reasonTextEarly,
        sessionId: sid,
        sessionAgeMs,
      });
    }

    // AO66R-HF3: UI must never remain hostage to network/WebRTC cleanup.
    // For manual stop, close overlay immediately and open summary shell even if transcript is empty.
    const isManualStopEarly = isManualRealtimeStopReason(reasonTextEarly);
    if (isManualStopEarly) {
      try { setRtcOverlayForceClosed(true); } catch {}
      try { console.log("REALTIME_MANUAL_END", { reason: reasonTextEarly, sessionId: sid, marker: ORKIO_AO66R_HF4_BUILD_MARKER }); } catch {}
      try { clearRealtimePendingAutoStop(); } catch {}
      try { clearRealtimeTimeboxTimer(); } catch {}
      try { setRealtimeMode(false); } catch {}
      try { realtimeModeRef.current = false; } catch {}
      try { setRtcTimeboxRemaining(null); } catch {}
      try { setRtcReadyToRespond(false); } catch {}
      try { setV2vPhase(null); } catch {}
      try { updateRealtimePremiumStatus(null, ""); } catch {}
      try { console.log("REALTIME_OVERLAY_CLOSED", { reason: reasonTextEarly, sessionId: sid, marker: ORKIO_AO66R_HF4_BUILD_MARKER }); } catch {}
      try {
        publishRealtimeTranscriptSummary(reasonTextEarly, { sessionId: sid, source: "stopRealtime_manual_immediate", forceOpen: true });
        console.log("REALTIME_SUMMARY_OPENED", { reason: reasonTextEarly, sessionId: sid, marker: ORKIO_AO66R_HF4_BUILD_MARKER });
      } catch {}
    }
    const minAutoStopMs = 30000;
    const isPrematureAutoStop = Boolean(
      sid &&
      !allowBackendEnd &&
      shouldHoldRealtimeInsteadOfEnding(reasonTextEarly, sessionAgeMs)
    );

    try {
      console.log("REALTIME_END_REQUESTED", {
        reason: reasonTextEarly,
        sessionId: sid,
        sessionAgeMs,
        prematureAutoStopBlocked: isPrematureAutoStop,
        allowBackendEnd,
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
    } catch {}

    if (isPrematureAutoStop) {
      clearRealtimePendingAutoStop();
      rtcLastStopReasonRef.current = reasonTextEarly;
      updateRealtimePremiumStatus("listening", "Realtime ativo. Aguardando áudio ou transcrição.");
      setUploadStatus("⚡ Mantendo a sessão de voz aberta. O timer continua ativo.");
      setTimeout(() => setUploadStatus(""), 2500);
      try {
        console.warn("REALTIME_END_BLOCKED_PREMATURE_HELD", {
          reason: reasonTextEarly,
          sessionId: sid,
          sessionAgeMs,
          minAutoStopMs,
          marker: ORKIO_AO66R_HF4_BUILD_MARKER,
        });
      } catch {}
      logRealtimeStep("ao66a_hf3:end_blocked_premature_held", {
        reason: reasonTextEarly,
        sessionAgeMs,
        minAutoStopMs,
        marker: ORKIO_AO66R_HF4_BUILD_MARKER,
      });
      return;
    }

    if (isManualRealtimeStopReason(reasonTextEarly)) {
      clearRealtimePendingAutoStop();
    }

    try { updateRealtimePremiumStatus("ending", "Encerrando sessão de voz com segurança."); } catch {}
    try {
      console.log("REALTIME_STOP_REASON", reasonTextEarly, { sessionId: sid, sessionAgeMs, marker: ORKIO_AO66R_HF4_BUILD_MARKER });
    } catch {}

    if (rtcStopInFlightRef.current) {
      logRealtimeStep("ao66r_hf4:stop_skip_inflight_ui_already_closed", { reason, sessionId: sid || null });
      try { setRtcOverlayForceClosed(true); } catch {}
      try { setRealtimeMode(false); } catch {}
      try { realtimeModeRef.current = false; } catch {}
      try { setRtcTimeboxRemaining(null); } catch {}
      try { publishRealtimeTranscriptSummary(reasonTextEarly, { sessionId: sid, source: "stopRealtime_inflight", forceOpen: true }); } catch {}
      return;
    }

    rtcStopInFlightRef.current = true;
    rtcConnectingRef.current = false;

    try {
      clearRealtimeResponseTimeout();
      clearRealtimeAutoResponseFallback();
      clearRealtimeIdleFollowup();
      clearRealtimeAudioWatchdog();
      clearRealtimeStartupWatchdog();
      clearRealtimePendingAutoStop();
      clearRealtimeTimeboxTimer();
      clearRealtimeLivePoll();
      await releaseRealtimeWakeLock(reason);
      flushRealtimePartialTranscript(`stop_${reason}_partial_flush`);
      rtcFallbackActiveRef.current = false;
      if (rtcFlushTimerRef.current) { try { clearInterval(rtcFlushTimerRef.current); } catch {} rtcFlushTimerRef.current = null; }

      try {
        if (sid) {
          await flushRealtimeEvents();

          if (allowBackendEnd) {
            await endRealtimeSession({ session_id: sid, ended_at: Math.floor(Date.now() / 1000), meta: { reason, mode: summitRuntimeModeRef.current, hf6r10_explicit_end: true } });
          } else {
            logRealtimeStep("ao68a_hf6r10:backend_end_suppressed", {
              reason: reasonTextEarly,
              sessionId: sid,
              sessionAgeMs,
            });
            try {
              console.warn("REALTIME_BACKEND_END_SUPPRESSED", {
                reason: reasonTextEarly,
                sessionId: sid,
                sessionAgeMs,
                marker: "AO68A-HF6R10_NO_BACKEND_END_ON_WARMUP",
              });
            } catch {}
          }

          try {
            const data = await getRealtimeSession({ session_id: sid, finals_only: true });
            if (data?.events) setRtcAuditEvents(data.events);
            await handleBackendRealtimeAssistantResponses(data || {});
          } catch {}
          try {
            if (summitRuntimeModeRef.current === "summit") {
              const scoreRes = await getSummitSessionScore({ session_id: sid });
              setSummitSessionScore(scoreRes?.data?.score || null);
            }
          } catch {}
        }
      } catch (err) {
        console.warn('[Realtime] stop finalize failed', err);
      }

      publishRealtimeTranscriptSummary(reason, { sessionId: sid, source: "stopRealtime", forceOpen: isManualStopEarly });

      hardResetRealtimeClientState(`stop_${reason}`);

      try { setRealtimeMode(false); } catch {}
      try { realtimeModeRef.current = false; } catch {}
      try { setRtcTimeboxRemaining(null); } catch {}
      try { setRtcReadyToRespond(false); } catch {}
      if (isManualStopEarly) {
        try { publishRealtimeTranscriptSummary(reason, { sessionId: sid, source: "stopRealtime_after_cleanup", forceOpen: true }); } catch {}
      }

      try { rtcSessionIdRef.current = null; } catch {}
      try { rtcSessionStartedAtRef.current = 0; } catch {}
      try { rtcThreadIdRef.current = null; } catch {}
      try { setRtcReadyToRespond(false); } catch {}
      try { setV2vPhase(null); } catch {}

      const reasonText = String(reason || "");
      const shouldStartCooldown =
        Boolean(sid)
        && isRealtimeTimeboxLimitedUser()
        && (
          reasonText.includes("time_limit_frontend")
          || reasonText.includes("backend_cooldown")
        )
        && !reasonText.includes("start_error")
        && !reasonText.includes("start_blocked_by_cooldown")
        && !reasonText.includes("pre_start_hard_reset")
        && !reasonText.includes("startup_watchdog");

      if (shouldStartCooldown) {
        startRealtimeCooldown(rtcTimeboxPolicyRef.current?.cooldownSeconds || REALTIME_PUBLIC_BETA_COOLDOWN_SECONDS, reason);
      } else {
        updateRealtimePremiumStatus(null, "");
      }
    } catch (err) {
      console.warn('[Realtime] stopRealtime hard cleanup failed', err);
      hardResetRealtimeClientState(`stop_exception_${reason}`);
    } finally {
      rtcStopInFlightRef.current = false;
      rtcConnectingRef.current = false;
      if (isManualStopEarly) {
        try { setRtcOverlayForceClosed(true); } catch {}
        try { setRealtimeMode(false); } catch {}
        try { realtimeModeRef.current = false; } catch {}
        try { setRtcTimeboxRemaining(null); } catch {}
        try { setRtcReadyToRespond(false); } catch {}
        try { setV2vPhase(null); } catch {}
        try { updateRealtimePremiumStatus(null, ""); } catch {}
        try { publishRealtimeTranscriptSummary(reasonTextEarly, { sessionId: sid, source: "stopRealtime_finally", forceOpen: true }); } catch {}
      }
      if (!realtimeModeRef.current) {
        try { setRtcTimeboxRemaining(null); } catch {}
      }
    }
  }

  useEffect(() => {
    function handleRealtimeVisibilityChange() {
      try {
        if (!realtimeModeRef.current && !rtcSessionIdRef.current) return;
        const state = typeof document !== "undefined" ? document.visibilityState : "visible";
        logRealtimeStep("mobile:visibility_change", { state });
        if (state === "hidden") {
          rtcLastVisibilityHiddenAtRef.current = Date.now();
          setUploadStatus("⚡ Realtime ativo. Mantenha a tela ligada para preservar voz e transcrição.");
          return;
        }

        if (state === "visible") {
          const hiddenMs = rtcLastVisibilityHiddenAtRef.current ? Date.now() - rtcLastVisibilityHiddenAtRef.current : null;
          rtcLastVisibilityHiddenAtRef.current = null;
          startRealtimeWakeLockGuard("visibility_visible");
          ensureRealtimeAudioOutput("visibility_visible");
          logRealtimeStep("mobile:visibility_restored", { hidden_ms: hiddenMs });
          if (hiddenMs && hiddenMs > 15000 && rtcSessionIdRef.current) {
            setUploadStatus("⚡ Realtime retomado. Se o áudio estiver baixo, toque no ⚡ para reconectar limpo.");
            setTimeout(() => setUploadStatus(""), 3500);
          }
        }
      } catch {}
    }

    function handleRealtimePageHide() {
      try {
        if (!realtimeModeRef.current && !rtcSessionIdRef.current) return;
        // AO68A-HF6R10:
        // Mobile/PWA pagehide must not end backend Realtime sessions.
        // It was creating fake usage and public cooldown during warmup.
        markRealtimePausedForBackground("pagehide_no_backend_end");
        logRealtimeStep("ao68a_hf6r10:pagehide_no_backend_end", {
          sessionId: rtcSessionIdRef.current || null,
          sessionAgeMs: getRealtimeSessionAgeMs(),
        });
      } catch {}
    }

    function handleRealtimeFocus() {
      try {
        if (!realtimeModeRef.current && !rtcSessionIdRef.current) return;
        startRealtimeWakeLockGuard("window_focus");
        ensureRealtimeAudioOutput("window_focus");
      } catch {}
    }

    try { document.addEventListener("visibilitychange", handleRealtimeVisibilityChange); } catch {}
    try { window.addEventListener("focus", handleRealtimeFocus); } catch {}
    try { window.addEventListener("pageshow", handleRealtimeFocus); } catch {}
    try { window.addEventListener("pagehide", handleRealtimePageHide); } catch {}

    return () => {
      try { document.removeEventListener("visibilitychange", handleRealtimeVisibilityChange); } catch {}
      try { window.removeEventListener("focus", handleRealtimeFocus); } catch {}
      try { window.removeEventListener("pageshow", handleRealtimeFocus); } catch {}
      try { window.removeEventListener("pagehide", handleRealtimePageHide); } catch {}
    };
  }, []);


  async function submitStageReview(clarity, naturalness, institutionalFit) {
    const sid = rtcSessionIdRef.current || lastRealtimeSessionId || null;
    const targetSid = sid || lastRealtimeSessionId;
    if (!targetSid) return;
    try {
      setSummitReviewPending(true);
      const res = await submitSummitSessionReview({
        session_id: targetSid,
        clarity,
        naturalness,
        institutional_fit: institutionalFit,
      });
      try {
        const scoreRes = await getSummitSessionScore({ session_id: targetSid });
        setSummitSessionScore(scoreRes?.data?.score || { human_review: res?.data?.review || null });
      } catch {
        setSummitSessionScore((prev) => ({ ...(prev || {}), human_review: res?.data?.review || null }));
      }
      setUploadStatus("✅ Avaliação do Summit registrada.");
      setTimeout(() => setUploadStatus(""), 1800);
    } catch (err) {
      console.warn("[Summit] review failed", err);
    } finally {
      setSummitReviewPending(false);
    }
  }


  function nudgeRealtimeActivation(source = "voice_button_retry") {
    try {
      const sid = rtcSessionIdRef.current || null;
      const dc = rtcDcRef.current || null;
      const dcState = dc?.readyState || null;
      const ageMs = getRealtimeSessionAgeMs();

      logRealtimeStep("ao68a_hf6r9:activation_nudge", {
        source,
        sessionId: sid,
        dcState,
        ageMs,
        connecting: Boolean(rtcConnectingRef.current),
        conversationStarted: Boolean(rtcConversationStartedRef.current),
      });

      if (!sid) return false;

      setRealtimeMode(true);
      realtimeModeRef.current = true;
      setV2vError(null);

      if (dc && dc.readyState === "open") {
        if (
          rtcResponseInFlightRef.current &&
          !rtcLastResponseCreatedAtRef.current &&
          ageMs > 8000
        ) {
          rtcResponseInFlightRef.current = false;
          clearRealtimeResponseTimeout();
        }

        setV2vPhase("listening");
        updateRealtimePremiumStatus("listening", "Realtime ativo. Reenviando saudação de voz.");
        ensureRealtimeAudioOutput(`hf6r9_${source}`);
        announceRealtimeTimeboxStart(
          dc,
          isRealtimeTimeboxLimitedUser()
            ? resolveRealtimeStartTimeboxSeconds({ timebox: rtcTimeboxPolicyRef.current })
            : 3600
        );
        scheduleRealtimeActivationProbe(dc, `hf6r9_${source}`);
        setUploadStatus("⚡ Realtime ativo. Reenviei a ativação de voz sem reiniciar a sessão.");
        setTimeout(() => setUploadStatus(""), 2500);
        return true;
      }

      updateRealtimePremiumStatus("connecting", "Realtime abrindo. Mantive a sessão viva e não reiniciei o cooldown.");
      setV2vPhase("connecting");
      setUploadStatus("⚡ Realtime ainda abrindo. Não clique novamente para reiniciar; estou mantendo a sessão viva.");
      setTimeout(() => setUploadStatus(""), 3500);

      if (sid) {
        startRealtimeStartupWatchdog(sid, `hf6r9_${source}`);
      }

      return true;
    } catch (err) {
      logRealtimeStep("ao68a_hf6r9:activation_nudge_failed", {
        source,
        message: err?.message || null,
      });
      return false;
    }
  }

  function toggleRealtimeMode() {
    if (SUMMIT_VOICE_MODE !== "realtime") return;
    const next = !realtimeMode;

    // AO68A-HF6R9:
    // During warmup, a second tap on the lightning/voice button must NOT be
    // interpreted as "stop". It was ending the just-created backend session,
    // and the next tap fell into public cooldown. Treat it as activation retry.
    if (!next && realtimeMode) {
      const ageMs = getRealtimeSessionAgeMs();
      const warmupActive = Boolean(
        rtcConnectingRef.current ||
        (
          rtcSessionIdRef.current &&
          !rtcConversationStartedRef.current &&
          ageMs >= 0 &&
          ageMs < 180000
        )
      );

      if (warmupActive) {
        const nudged = nudgeRealtimeActivation("second_tap_during_warmup");
        if (nudged) return;
      }
    }

    if (next && rtcSessionIdRef.current && !rtcConversationStartedRef.current) {
      const nudged = nudgeRealtimeActivation("start_tap_existing_session");
      if (nudged) return;
    }

    if (next && isRealtimeTimeboxLimitedUser() && rtcCooldownRemaining > 0) {
      // AO68A-HF6R10:
      // If the browser still has a warming session, retry activation instead of showing cooldown.
      const ageMs = getRealtimeSessionAgeMs();
      if (rtcSessionIdRef.current && !rtcConversationStartedRef.current && ageMs >= 0 && ageMs < 180000) {
        const nudged = nudgeRealtimeActivation("cooldown_tap_existing_warmup_session");
        if (nudged) return;
      }

      const label = formatRealtimeCountdown(rtcCooldownRemaining);
      setV2vPhase("error");
      setV2vError(`A voz em tempo real estará disponível novamente em ${label}. O chat por texto continua disponível.`);
      setUploadStatus(`⏳ Voz disponível novamente em ${label}.`);
      setTimeout(() => setUploadStatus(""), 3500);
      return;
    }

    setRealtimeMode(next);
    realtimeModeRef.current = next;

    if (next) {
      // Disable classic voice mode to avoid mic contention
      if (voiceModeRef.current) {
        setVoiceMode(false);
        voiceModeRef.current = false;
      }
      try { stopMic(); } catch {}
      try { stopTts(); } catch {}
      void Promise.resolve(startRealtime()).catch((err) => {
        // ORKIO_AO60K_HF2_429_COOLDOWN_HARDENING
        console.warn("[Realtime] startRealtime rejected outside internal catch", err);
        if (isRealtimeCooldownOrRateLimitError(err)) {
          applyRealtimeCooldownFromError(err, "toggle_start_rejected_cooldown");
          // AO68A-HF6R9: never call /api/realtime/end only because /start returned cooldown.
          // There may be a still-warming session in the browser or backend.
          setRealtimeMode(false);
          realtimeModeRef.current = false;
          return;
        }
        const friendlyRealtimeError = normalizeUserFacingRuntimeMessage(
          [
            err?.code,
            err?.status ? `status_${err.status}` : "",
            err?.userMessage,
            err?.message,
          ].filter(Boolean).join(" | ") || "Falha ao iniciar Realtime",
          "realtime"
        );
        setRealtimeMode(false);
        realtimeModeRef.current = false;
        setV2vPhase("error");
        setV2vError(friendlyRealtimeError);
        setUploadStatus("❌ Realtime indisponível. Você pode continuar por texto.");
        setTimeout(() => setUploadStatus(""), 3500);
      });
    } else {
      void stopRealtime('toggle_off');
      setV2vPhase(null);
      setV2vError(null);
      setUploadStatus('');
    }
  }

  function stopTts(reason = "manual_stop") {
    // AO65A-HF4/HF5: hard stop must invalidate every pending TTS generation/playback path.
    // This prevents a delayed /api/tts blob, stale Audio callback, or automatic V2V replay from resuming after stop.
    const stoppedMessageId = lastSpokenMessageIdRef.current || null;
    const stoppedText = lastSpokenMsgRef.current || "";

    ttsStopRequestedRef.current = true;
    ttsPlaySeqRef.current += 1;

    const shouldSuppressAuto =
      reason !== "before_new_play" &&
      reason !== "natural_end" &&
      reason !== "tts_error";

    if (shouldSuppressAuto) {
      // HF5/HF6: shield against auto TTS / V2V restarts triggered by stale async callbacks.
      // HF6 keeps a manual-stop latch active until the next real user click.
      const suppressUntil = Date.now() + 10 * 60 * 1000;
      ttsSuppressAutoUntilRef.current = suppressUntil;
      ttsManualStopUntilRef.current = suppressUntil;
      ttsManualStopActiveRef.current = true;
      ttsStoppedMessageIdRef.current = stoppedMessageId;
      ttsStoppedTextRef.current = stoppedText;
    }

    try {
      ttsAbortRef.current?.abort?.();
    } catch (_) {}
    ttsAbortRef.current = null;

    const activeAudio = ttsAudioRef.current;
    ttsAudioRef.current = null;

    if (activeAudio) {
      try {
        activeAudio.onended = null;
        activeAudio.onerror = null;
        activeAudio.onpause = null;
      } catch (_) {}
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (_) {}
      try {
        activeAudio.removeAttribute("src");
        activeAudio.load?.();
      } catch (_) {}
    }

    if (ttsObjectUrlRef.current) {
      try {
        URL.revokeObjectURL(ttsObjectUrlRef.current);
      } catch (_) {}
      ttsObjectUrlRef.current = null;
    }

    try {
      if (micRestartTimeoutRef.current) {
        clearTimeout(micRestartTimeoutRef.current);
        micRestartTimeoutRef.current = null;
      }
    } catch (_) {}

    lastSpokenMessageIdRef.current = null;
    lastSpokenMsgRef.current = "";
    setTtsPlaying(false);
    setTtsPlayingMessageId(null);
    if (v2vPhase === "playing" || v2vPhase === "tts") {
      setV2vPhase(null);
    }
  }

  function resolveUnifiedClassicTtsVoice(voiceOverride = null) {
    // AO65V-FE8: frontend canonical voice lock for classic message TTS.
    // Evidence from DevTools showed /api/tts receiving voice="shimmer".
    // Backend was obeying inp.voice correctly; therefore the browser bundle must
    // stop resolving the Orkio TTS button to the legacy local fallback.
    const ORKIO_ENV = (typeof window !== "undefined" && window.__ORKIO_ENV__) ? window.__ORKIO_ENV__ : {};
    const ORKIO_CANONICAL = coerceVoiceId(ORKIO_CANONICAL_VOICE_ID || "cedar", "cedar");

    const normalizeCandidate = (value) => {
      const raw = String(value || "").trim();
      if (!raw) return "";
      return coerceVoiceId(raw, ORKIO_CANONICAL);
    };

    const envRealtimeVoice = normalizeCandidate(
      ORKIO_ENV.VITE_REALTIME_VOICE ||
      import.meta.env.VITE_REALTIME_VOICE ||
      ""
    );

    const envOrkioVoice = normalizeCandidate(
      ORKIO_ENV.VITE_ORKIO_VOICE_ID ||
      import.meta.env.VITE_ORKIO_VOICE_ID ||
      ""
    );

    const currentRealtimeVoice = normalizeCandidate(rtcVoiceRef.current);
    const explicitOverride = normalizeCandidate(voiceOverride);

    const candidate =
      explicitOverride ||
      currentRealtimeVoice ||
      envRealtimeVoice ||
      envOrkioVoice ||
      ORKIO_CANONICAL;

    // Cedar is the official Orkio voice. If any stale bundle/runtime fallback still
    // produces the previous local default ("shimmer"), canonical Cedar must win.
    const resolvedVoice = candidate === "shimmer" ? ORKIO_CANONICAL : candidate;
    return coerceVoiceId(resolvedVoice, ORKIO_CANONICAL);
  }

  async function playTts(textToSpeak, agentId, opts = {}) {
    // F-01 FIX: desestruturar opts no início da função
    const { forceAuto = false, messageId = null, traceId = null, voiceOverride = null, userInitiated = false } = opts || {};
    if (!textToSpeak || textToSpeak.length < 2) return;

    // AO65A-HF5: after a manual stop, block every non-user-initiated TTS restart.
    // This is stricter than forceAuto because some delayed paths can call playTts() without forceAuto.
    const nowMs = Date.now();
    const suppressUntil = Number(ttsSuppressAutoUntilRef.current || 0);
    const stoppedUntil = Number(ttsManualStopUntilRef.current || 0);
    const sameStoppedMessage = Boolean(messageId && ttsStoppedMessageIdRef.current && String(messageId) === String(ttsStoppedMessageIdRef.current));
    const sameStoppedText = Boolean(!messageId && ttsStoppedTextRef.current && String(textToSpeak || "") === String(ttsStoppedTextRef.current || ""));
    const manualStopActive = Boolean(ttsManualStopActiveRef.current);
    if (!userInitiated && (manualStopActive || nowMs < suppressUntil || (nowMs < stoppedUntil && (sameStoppedMessage || sameStoppedText)))) {
      console.info("[V2V] TTS suppressed after manual stop message_id=%s agent_id=%s userInitiated=%s forceAuto=%s manualStopActive=%s", messageId, agentId, userInitiated, forceAuto, manualStopActive);
      return;
    }

    // AO47B2_FRONTEND_SUPPRESS_CLASSIC_TTS_DURING_REALTIME
    // Realtime já possui áudio nativo. Durante sessão Realtime, nunca chamar /api/tts clássico.
    if (realtimeModeRef.current || rtcSessionIdRef.current) {
      console.info(
        "[AO47B2] classic TTS suppressed during active realtime session session_id=%s thread_id=%s",
        rtcSessionIdRef.current || null,
        threadId || null
      );
      return;
    }

    // AO65A-HF3/HF4: permitir desligar também enquanto o /api/tts ainda está gerando.
    const sameMessageRequested = messageId
      ? messageId === lastSpokenMessageIdRef.current
      : textToSpeak === lastSpokenMsgRef.current;
    if ((ttsPlaying || ttsPlayingMessageId || ttsAudioRef.current || ttsAbortRef.current) && sameMessageRequested) {
      if (userInitiated) {
        stopTts("user_toggle");
      } else {
        console.info("[V2V] duplicate non-user TTS ignored while current audio is active message_id=%s agent_id=%s", messageId, agentId);
      }
      return;
    }

    // Evitar reler a mesma mensagem (idempotência), sem bloquear o stop acima.
    if (messageId && messageId === lastSpokenMessageIdRef.current) return;
    if (!messageId && textToSpeak === lastSpokenMsgRef.current) return;
    lastSpokenMessageIdRef.current = messageId || null;
    lastSpokenMsgRef.current = textToSpeak;

    if (userInitiated) {
      // A fresh click by the user is the only thing allowed to clear the manual stop shield.
      ttsSuppressAutoUntilRef.current = 0;
      ttsManualStopUntilRef.current = 0;
      ttsManualStopActiveRef.current = false;
      ttsStoppedMessageIdRef.current = null;
      ttsStoppedTextRef.current = "";
    }

    // Limpar markdown para fala mais natural
    let clean = textToSpeak
      .replace(/```[\s\S]*?```/g, ' código omitido ')
      .replace(/`[^`]+`/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[#*_~>|]/g, '')
      .replace(/\n{2,}/g, '. ')
      .replace(/\n/g, ' ')
      .trim();
    if (voiceModeRef.current) {
      if (clean.length > 1200) clean = clean.slice(0, 1200);
    } else {
      if (clean.length > 4096) clean = clean.slice(0, 4096);
    }
    if (clean.length < 2) return;

    stopTts("before_new_play");
    // stopTts() marks a stop request; this new play request must clear it.
    ttsStopRequestedRef.current = false;
    const ttsController = new AbortController();
    const playSeq = ++ttsPlaySeqRef.current;
    ttsAbortRef.current = ttsController;

    const isCurrentTtsPlay = () =>
      ttsPlaySeqRef.current === playSeq &&
      ttsAbortRef.current === ttsController &&
      !ttsStopRequestedRef.current &&
      !ttsController.signal.aborted;

    setTtsPlaying(true);
    setTtsPlayingMessageId(messageId || "__manual__");
    setV2vPhase('playing');

    const effectiveTrace = traceId || v2vTraceRef.current || null;
    console.info('[V2V] v2v_play_start trace_id=%s message_id=%s agent_id=%s', effectiveTrace, messageId, agentId);

    try {
      const base = (window.__ORKIO_ENV__?.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/$/, '');
      const apiUrl = base.endsWith('/api') ? base.slice(0, -4) : base;

      const ttsHeaders = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'X-Org-Slug': tenant,
      };
      if (effectiveTrace) ttsHeaders['X-Trace-Id'] = effectiveTrace;

      const ORKIO_ENV = (typeof window !== "undefined" && window.__ORKIO_ENV__) ? window.__ORKIO_ENV__ : {};
      const ttsSpeed = coerceTtsSpeed(
        ORKIO_ENV.VITE_ORKIO_TTS_SPEED || import.meta.env.VITE_ORKIO_TTS_SPEED || ORKIO_DEFAULT_TTS_SPEED
      );
      const unifiedVoice = resolveUnifiedClassicTtsVoice(voiceOverride);

      const res = await fetch(`${apiUrl}/api/tts`, {
        method: 'POST',
        headers: ttsHeaders,
        signal: ttsController.signal,
        // AO65A-HF4: use the same voice profile as Realtime for classic message TTS.
        // This avoids Orkio sounding different between the 🔊 button and Realtime.
        body: JSON.stringify({
          text: clean,
          voice: unifiedVoice,
          speed: ttsSpeed,
          // AO65A-HF5: force backend to honor inp.voice.
          // /api/tts resolves voice as message_id → agent_id → inp.voice → default,
          // so sending message_id/agent_id here can override the Realtime voice.
          agent_id: null,
          message_id: null,
          // AO47B2: defesa adicional para o backend AO47B1 conseguir bloquear se este caminho for chamado.
          thread_id: threadId || null,
        }),
      });

      if (!isCurrentTtsPlay()) {
        return;
      }

      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        if (!isCurrentTtsPlay()) return;
        console.warn('[V2V] v2v_tts_fail trace_id=%s status=%d body=%s', effectiveTrace, res.status, errText.slice(0, 200));
        setTtsPlaying(false);
        setTtsPlayingMessageId(null);
        setV2vPhase('error');
        setV2vError(`TTS falhou (HTTP ${res.status})`);
        if (res.status === 401) {
          alert("Sessão expirada. Faça login novamente.");
          try { localStorage.removeItem("orkio_token"); } catch (_) {}
          window.location.href = "/auth";
        }
        return;
      }

      const blob = await res.blob();

      if (!isCurrentTtsPlay()) {
        return;
      }

      if (!blob || blob.size < 50) {
        console.warn('[V2V] v2v_tts_fail trace_id=%s reason=empty_blob size=%d', effectiveTrace, blob?.size);
        setTtsPlaying(false);
        setTtsPlayingMessageId(null);
        setV2vPhase('error');
        setV2vError('TTS retornou áudio vazio');
        return;
      }

      console.info('[V2V] v2v_tts_ok trace_id=%s bytes=%d voice=%s', effectiveTrace, blob.size, unifiedVoice);
      const url = URL.createObjectURL(blob);

      if (!isCurrentTtsPlay()) {
        try { URL.revokeObjectURL(url); } catch (_) {}
        return;
      }

      ttsObjectUrlRef.current = url;
      const audio = new Audio(url);
      ttsAudioRef.current = audio;

      await new Promise((resolve, reject) => {
        const cleanupCurrentAudio = (nextPhase = null) => {
          try { URL.revokeObjectURL(url); } catch (_) {}
          if (ttsObjectUrlRef.current === url) ttsObjectUrlRef.current = null;
          if (ttsAudioRef.current === audio) ttsAudioRef.current = null;

          // Only the current play is allowed to change visible TTS state.
          // Stale audio callbacks from an older blob must never flip the button or restart UI state.
          if (ttsPlaySeqRef.current === playSeq) {
            setTtsPlaying(false);
            setTtsPlayingMessageId(null);
            setV2vPhase(nextPhase);
          }
        };

        audio.onended = () => {
          if (!isCurrentTtsPlay()) {
            cleanupCurrentAudio(null);
            resolve();
            return;
          }
          console.info('[V2V] v2v_play_end trace_id=%s', effectiveTrace);
          stopTts("natural_end");
          // Reiniciar microfone após fala (ciclo V2V) apenas em voice mode clássico.
          if (voiceModeRef.current && (speechSupported || mediaRecorderSupported) && !micEnabledRef.current) {
            scheduleMicRestart('tts_end', 0);
          }
          resolve();
        };

        audio.onerror = (err) => {
          if (!isCurrentTtsPlay()) {
            cleanupCurrentAudio(null);
            resolve();
            return;
          }
          console.error('[V2V] audio.onerror trace_id=%s', effectiveTrace, err);
          cleanupCurrentAudio('error');
          setV2vError('Erro ao reproduzir áudio');
          reject(new Error('Audio playback error'));
        };

        audio.play().catch(err => {
          if (!isCurrentTtsPlay()) {
            cleanupCurrentAudio(null);
            resolve();
            return;
          }
          // autoplay bloqueado pelo browser — fallback silencioso
          console.warn('[V2V] autoplay blocked trace_id=%s:', effectiveTrace, err?.message);
          cleanupCurrentAudio(null);
          // BUG-01 FIX: reiniciar mic mesmo sem áudio — ciclo V2V não pode morrer aqui
          if (voiceModeRef.current && !micEnabledRef.current) {
            scheduleMicRestart('tts_autoplay_blocked', 300);
          }
          resolve(); // não rejeitar — V2V deve continuar mesmo sem áudio
        });
      });
    } catch (e) {
      if (e?.name === "AbortError" || ttsController.signal.aborted || ttsStopRequestedRef.current) {
        if (ttsAbortRef.current === ttsController) {
          ttsAbortRef.current = null;
        }
        setTtsPlaying(false);
        setTtsPlayingMessageId(null);
        setV2vPhase(null);
        return;
      }
      console.error('[V2V] v2v_tts_fail trace_id=%s error:', effectiveTrace, e);
      if (isCurrentTtsPlay()) {
        setTtsPlaying(false);
        setTtsPlayingMessageId(null);
        setV2vPhase('error');
        setV2vError(e?.message || 'Erro desconhecido no TTS');
      }
    } finally {
      if (ttsAbortRef.current === ttsController) {
        ttsAbortRef.current = null;
      }
    }
  }

  function changeTtsVoice(v) {
    setTtsVoice(v);
    localStorage.setItem('orkio_tts_voice', v);
  }

  // Upload flow
  function onPickFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    e.target.value = "";
    setUploadFileObj(f);
    setUploadScope("thread");
    setUploadAgentIds([]);
    setUploadOpen(true);
  }

  async function confirmUpload() {
    const f = uploadFileObj;
    if (!f) return;
    // PATCH0100_17_ENSURE_THREAD_BEFORE_UPLOAD: uploads need a thread to be visible in chat
    let effectiveThreadId = threadId;
    if (!effectiveThreadId && (uploadScope === "thread" || uploadScope === "institutional")) {
      try {
        const created = await apiFetch("/api/threads", { method: "POST", token, org: tenant, body: { title: "Nova conversa" }});
        effectiveThreadId = created?.data?.id;
        if (effectiveThreadId) activateThread(effectiveThreadId, { clearMessages: true });
      } catch (e) {
        console.warn("could not create thread before upload", e);
      }
    }

    try {
      setUploadProgress(true);
      setUploadStatus("Enviando arquivo...");

      if (uploadScope === "thread") {
        console.info("[Upload] start", { scope: "thread", filename: f?.name, threadId: effectiveThreadId, size: f?.size || null });
        await uploadFile(f, { token, org: tenant, threadId: effectiveThreadId, intent: "chat" });
        setUploadStatus("Arquivo anexado à conversa ✅");
        try { await loadMessages(effectiveThreadId, { force: true, expectedEpoch: activeThreadEpochRef.current }); } catch {}
      } else if (uploadScope === "agents") {
        if (!canAccessAdmin) {
          setUploadStatus("No beta público, arquivos são anexados à conversa com Orkio.");
          await uploadFile(f, { token, org: tenant, threadId: effectiveThreadId, intent: "chat" });
          setUploadStatus("Arquivo anexado à conversa ✅");
          try { await loadMessages(effectiveThreadId, { force: true, expectedEpoch: activeThreadEpochRef.current }); } catch {}
          return;
        }
        console.info("[Upload] start", { scope: "agents", filename: f?.name, agentIds: uploadAgentIds, size: f?.size || null });
        if (!uploadAgentIds.length) {
          alert("Selecione ao menos um agente.");
          return;
        }
        await uploadFile(f, { token, org: tenant, agentIds: uploadAgentIds, intent: "agent" });
        setUploadStatus("Arquivo vinculado aos agentes ✅");
      } else if (uploadScope === "institutional") {
        console.info("[Upload] start", { scope: "institutional", filename: f?.name, threadId: effectiveThreadId, size: f?.size || null });
        const admin = isAdmin(user);
        if (admin) {
          await uploadFile(f, { token, org: tenant, threadId: effectiveThreadId, intent: "institutional", linkAllAgents: true });
          setUploadStatus("Arquivo institucional (global) ✅");
          // STAB: reload com effectiveThreadId para garantir que mensagem system aparece
          try {
            if (effectiveThreadId) await loadMessages(effectiveThreadId, { expectedEpoch: activeThreadEpochRef.current });
          } catch (e) { console.warn("loadMessages after institutional upload failed:", e); }
        } else {
          // B2: request institutionalization; keep accessible in this thread
          await uploadFile(f, { token, org: tenant, threadId: effectiveThreadId, intent: "chat", institutionalRequest: true });
          setUploadStatus("Solicitação enviada ao admin (institucional) ✅");
          try { await loadMessages(effectiveThreadId, { force: true, expectedEpoch: activeThreadEpochRef.current }); } catch {}
        }
      }

      setUploadOpen(false);
      setUploadFileObj(null);
      setTimeout(() => setUploadStatus(""), 2200);
    } catch (e) {
      console.error("upload error", e);
      console.warn("[Upload] failed", {
        scope: uploadScope,
        filename: f?.name || uploadFileObj?.name || null,
        message: e?.message || null,
      });
      setUploadStatus(e?.message || "Falha no upload");
      setTimeout(() => setUploadStatus(""), 2500);
    } finally {
      setUploadProgress(false);
    }
  }

  const styles = {
    layout: {
      display: "flex",
      minHeight: "100dvh",
      background:
        "radial-gradient(1200px 700px at 30% -10%, rgba(124,92,255,0.25), transparent 60%), linear-gradient(180deg, #05060a, #03030a)",
      color: "#fff",
      fontFamily: "system-ui",
    },
    sidebar: {
      width: "330px",
      borderRight: "1px solid rgba(255,255,255,0.08)",
      display: "flex",
      flexDirection: "column",
      padding: "16px",
      gap: "12px",
    },
    brand: { fontSize: "18px", fontWeight: 800, letterSpacing: "-0.02em" },
    badge: {
      display: "inline-flex",
      alignItems: "center",
      gap: "8px",
      padding: "6px 10px",
      borderRadius: "999px",
      fontSize: "12px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.04)",
      color: "rgba(255,255,255,0.8)",
    },
    topRow: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" },
    newThreadBtn: {
      display: "inline-flex",
      alignItems: "center",
      gap: "8px",
      padding: "10px 12px",
      borderRadius: "14px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.05)",
      color: "#fff",
      cursor: "pointer",
    },
    threads: { flex: 1, overflowY: "auto", padding: "0 8px" },
    emptyThreads: { padding: "20px", textAlign: "center", color: "rgba(255,255,255,0.3)", fontSize: "13px" },
    threadItem: {
      display: "flex",
      alignItems: "center",
      gap: "10px",
      width: "100%",
      padding: "12px",
      background: "transparent",
      border: "none",
      borderRadius: "10px",
      color: "rgba(255,255,255,0.7)",
      fontSize: "13px",
      cursor: "pointer",
      textAlign: "left",
      marginBottom: "4px",
    },
    threadItemActive: { background: "rgba(255,255,255,0.1)", color: "#fff" },
    threadTitle: { flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
    threadEditBtn: {
      border: "none",
      background: "transparent",
      color: "rgba(255,255,255,0.55)",
      padding: "4px",
      borderRadius: "8px",
      cursor: "pointer",
    },
    userSection: {
      padding: "16px",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "10px",
    },
    userInfo: { display: "flex", alignItems: "center", gap: "10px" },
    userAvatar: {
      width: "36px",
      height: "36px",
      borderRadius: "50%",
      background: "linear-gradient(135deg, #7c5cff 0%, #35d0ff 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontWeight: 800,
    },
    userDetails: { display: "flex", flexDirection: "column" },
    userName: { fontSize: "13px", fontWeight: 700 },
    userEmail: { fontSize: "12px", color: "rgba(255,255,255,0.55)" },
    userActions: { display: "flex", alignItems: "center", gap: "8px" },
    iconBtn: {
      width: "36px",
      height: "36px",
      borderRadius: "12px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.05)",
      color: "#fff",
      cursor: "pointer",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
    },

    premiumEmptyShell: {
      display: "grid",
      gridTemplateColumns: isMobile ? "1fr" : "minmax(0, 1.55fr) minmax(320px, 400px)",
      gap: isMobile ? "18px" : "24px",
      alignItems: "stretch",
      padding: isMobile ? "8px" : "8px 6px",
    },
    premiumAside: {
      display: "grid",
      gap: "18px",
      alignContent: "start",
    },
    premiumAsideCard: {
      background: "linear-gradient(180deg, rgba(15,23,42,0.98) 0%, rgba(7,11,21,1) 100%)",
      border: "1px solid rgba(148,163,184,0.16)",
      borderRadius: "30px",
      padding: isMobile ? "18px" : "22px",
      boxShadow: "0 30px 80px rgba(2, 6, 23, 0.38)",
    },
    premiumAsideEyebrow: {
      fontSize: "11px",
      letterSpacing: "0.14em",
      textTransform: "uppercase",
      color: "rgba(148,163,184,0.88)",
      marginBottom: "9px",
      fontWeight: 900,
    },
    premiumAsideTitle: {
      fontSize: isMobile ? "18px" : "22px",
      lineHeight: 1.12,
      fontWeight: 900,
      marginBottom: "10px",
      color: "#f8fafc",
    },
    premiumAsideText: {
      fontSize: "14px",
      lineHeight: 1.72,
      color: "rgba(226,232,240,0.82)",
    },
    premiumLogList: {
      display: "grid",
      gap: "10px",
      marginTop: "14px",
    },
    premiumLogItem: {
      display: "flex",
      gap: "10px",
      alignItems: "flex-start",
      padding: "12px 12px",
      borderRadius: "16px",
      border: "1px solid rgba(148,163,184,0.12)",
      background: "rgba(2,6,23,0.34)",
      color: "rgba(241,245,249,0.88)",
      fontSize: "13px",
      lineHeight: 1.55,
    },
    premiumLogDot: {
      width: "8px",
      height: "8px",
      borderRadius: "999px",
      background: "linear-gradient(135deg, #7c3aed, #2563eb)",
      marginTop: "7px",
      flexShrink: 0,
    },
    premiumStatusRow: {
      display: "grid",
      gridTemplateColumns: isMobile ? "1fr" : "repeat(3, minmax(0, 1fr))",
      gap: "10px",
      marginTop: "14px",
    },
    premiumStatusCard: {
      borderRadius: "18px",
      padding: "13px 12px",
      border: "1px solid rgba(148,163,184,0.12)",
      background: "rgba(255,255,255,0.04)",
    },
    premiumStatusLabel: {
      fontSize: "11px",
      textTransform: "uppercase",
      letterSpacing: "0.08em",
      color: "rgba(148,163,184,0.72)",
      marginBottom: "6px",
      fontWeight: 800,
    },
    premiumStatusValue: {
      fontSize: "14px",
      fontWeight: 800,
      color: "#f8fafc",
      lineHeight: 1.3,
    },

    main: { flex: 1, display: "flex", flexDirection: "column" },
    topbar: {
      padding: "16px 18px",
      borderBottom: "1px solid rgba(255,255,255,0.08)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: "10px",
    },
    title: { fontSize: "16px", fontWeight: 900 },
    health: { fontSize: "12px", color: "rgba(255,255,255,0.6)" },
    chatArea: { flex: 1, overflowY: "auto", padding: "16px 18px" },
    messageRow: { display: "flex", marginBottom: "12px" },
    messageBubble: {
      maxWidth: "820px",
      padding: "12px 12px",
      borderRadius: "16px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.04)",
    },
    userBubble: { background: "rgba(124,92,255,0.12)", border: "1px solid rgba(124,92,255,0.25)" },
    agentBubble: { background: "rgba(53,208,255,0.10)", border: "1px solid rgba(53,208,255,0.22)" },
    systemBubble: { background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.18)" },
    bubbleHeaderRow: { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "12px", marginBottom: "6px" },
    bubbleHeaderName: { fontSize: "12px", color: "rgba(255,255,255,0.70)", fontWeight: 900 },
    bubbleHeaderTime: { fontSize: "12px", color: "rgba(255,255,255,0.55)", fontWeight: 700 },
    nameUser: { color: "rgba(196,176,255,0.95)" },
    nameAgent: { color: "rgba(160,240,255,0.95)" },
    nameSystem: { color: "rgba(255,255,255,0.82)" },
    messageContent: { whiteSpace: "pre-wrap", lineHeight: 1.45, fontSize: "14px" },
    messageTime: { marginTop: "8px", fontSize: "11px", color: "rgba(255,255,255,0.55)" },

    uploadStatus: {
      padding: "10px 18px",
      fontSize: "13px",
      color: "rgba(255,255,255,0.85)",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(255,255,255,0.03)",
    },

    realtimeAudit: {
      padding: "10px 18px",
      fontSize: "12px",
      color: "rgba(255,255,255,0.82)",
      borderTop: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(80,160,255,0.06)",
      maxHeight: "220px",
      overflowY: "auto",
    },
    realtimeAuditHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", marginBottom: "8px" },
    realtimeAuditTitle: { fontWeight: 900, letterSpacing: "0.2px" },
    realtimeAuditPill: { padding: "2px 8px", borderRadius: "999px", border: "1px solid rgba(255,255,255,0.16)", background: "rgba(255,255,255,0.05)", fontSize: "11px" },
    realtimeAuditItem: { padding: "8px 10px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.10)", background: "rgba(255,255,255,0.03)", marginBottom: "8px" },
    realtimeAuditMeta: { display: "flex", justifyContent: "space-between", gap: "10px", marginBottom: "6px", opacity: 0.8 },
    realtimeAuditWho: { fontWeight: 900 },
    realtimeAuditText: { whiteSpace: "pre-wrap", lineHeight: 1.45 },


    composerContainer: { position: "sticky", bottom: composerViewportOffset, zIndex: 8, padding: "14px 18px calc(14px + env(safe-area-inset-bottom, 0px))", borderTop: "1px solid rgba(255,255,255,0.08)", background: "rgba(7,9,16,0.96)", backdropFilter: "blur(10px)" },
    composer: {
      display: "flex",
      alignItems: "flex-end",
      gap: "10px",
      padding: "10px",
      borderRadius: "18px",
      border: "1px solid rgba(255,255,255,0.12)",
      background: "rgba(255,255,255,0.04)",
    },
    attachBtn: {
      width: "42px",
      height: "42px",
      borderRadius: "14px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.05)",
      color: "#fff",
      cursor: "pointer",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      opacity: uploadProgress ? 0.6 : 1,
    },
    textarea: {
      flex: 1,
      minHeight: "42px",
      maxHeight: "180px",
      resize: "none",
      background: "transparent",
      border: "none",
      outline: "none",
      color: "#fff",
      fontSize: "14px",
      lineHeight: 1.4,
      padding: "10px 8px",
    },
    micBtn: {
      width: "42px",
      height: "42px",
      borderRadius: "14px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: micEnabled ? "rgba(53,208,255,0.15)" : "rgba(255,255,255,0.05)",
      color: "#fff",
      cursor: speechSupported ? "pointer" : "not-allowed",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      opacity: speechSupported ? 1 : 0.6,
    },
    sendBtn: {
      width: "42px",
      height: "42px",
      borderRadius: "14px",
      border: "1px solid rgba(255,255,255,0.1)",
      background: "rgba(255,255,255,0.05)",
      color: "#fff",
      cursor: "pointer",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      opacity: sending ? 0.6 : 1,
    },
    select: {
      padding: "8px 10px",
      borderRadius: "12px",
      border: "1px solid rgba(255,255,255,0.12)",
      background: "rgba(255,255,255,0.05)",
      color: "#fff",
      fontSize: "12px",
    },
    modalBack: {
      position: "fixed",
      inset: 0,
      background: "rgba(0,0,0,0.55)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 50,
      padding: "16px",
    },
    modal: {
      width: "min(720px, 96vw)",
      borderRadius: "18px",
      border: "1px solid rgba(255,255,255,0.12)",
      background: "rgba(12,12,20,0.96)",
      padding: "16px",
    },
    modalTitle: { fontSize: "14px", fontWeight: 900 },
    radioRow: { display: "flex", gap: "10px", alignItems: "center", marginTop: "10px", color: "rgba(255,255,255,0.85)" },
    modalActions: { display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "14px" },
    btn: { border: "1px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.06)", color: "#fff", padding: "10px 12px", borderRadius: "14px", cursor: "pointer" },
    btnPrimary: { background: "rgba(124,92,255,0.22)", border: "1px solid rgba(124,92,255,0.35)", fontWeight: 800 },
    checkGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px", marginTop: "10px" },
    checkItem: { display: "flex", gap: "8px", alignItems: "center", padding: "8px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)" },
    hint: { fontSize: "12px", color: "rgba(255,255,255,0.6)", marginTop: "6px" },
  };

  function handleOnboardingComplete(nextUser) {
    const refreshedToken = nextUser?.access_token || token;
    const mergedUser = {
      ...(user || {}),
      ...(nextUser || {}),
      org_slug: nextUser?.org_slug || user?.org_slug || tenant,
      role: nextUser?.role || user?.role || "user",
      approved_at: nextUser?.approved_at ?? user?.approved_at ?? null,
      usage_tier: nextUser?.usage_tier ?? user?.usage_tier ?? null,
      signup_source: nextUser?.signup_source ?? user?.signup_source ?? null,
      signup_code_label: nextUser?.signup_code_label ?? user?.signup_code_label ?? null,
      product_scope: nextUser?.product_scope ?? user?.product_scope ?? null,
      onboarding_completed: true,
    };

    mergedUser.is_admin = hasAdminAccess(mergedUser);
    mergedUser.admin = mergedUser.is_admin === true;

    setUser(mergedUser);

    try {
      setSession({
        token: refreshedToken,
        user: mergedUser,
        tenant: mergedUser?.org_slug || tenant,
      });
      setToken(refreshedToken);
    } catch {}

    setOnboardingOpen(false);
    setOnboardingStatus("");
    setUploadStatus("✅ Onboarding concluído.");
    setTimeout(() => setUploadStatus(""), 1800);
  }

  const onboardingGateRequired = Boolean(
    token &&
    onboardingChecked &&
    onboardingOpen &&
    !showTermsModal &&
    user &&
    !user?.onboarding_completed
  );

  if (onboardingGateRequired) {
    return (
      <>
        <PWAInstallPrompt />
        <OnboardingModal
          user={user}
          onComplete={handleOnboardingComplete}
        />
      </>
    );
  }

  const meName = user?.name || user?.email || "Você";

  // ORKIO_AO57C_PUBLIC_BETA_ORKIO_ONLY_WEB_V3
  // UX layer only. Backend AO57B remains the authority for actual access control.
  // ORKIO_AO60F_HF4_NON_ADMIN_REALTIME_ORKIO_ONLY
  // During public beta, every non-admin user, including EFATAH777 and AMCHAMRSORKIO,
  // uses Orkio-only Realtime. Admin keeps full agent access for testing/release governance.
  const publicBetaOrkioOnly = !canAccessAdmin;
  const isOrkioAgent = (agent) => {
    const raw = [
      agent?.name,
      agent?.slug,
      agent?.id,
      agent?.label,
    ].filter(Boolean).join(" ").toLowerCase();
    return raw.includes("orkio");
  };
  const visibleAgents = publicBetaOrkioOnly ? agents.filter(isOrkioAgent) : agents;
  const effectiveDestMode = publicBetaOrkioOnly ? "single" : destMode;

  const pendingApprovedPatchExecution = findPendingApprovedPatchExecution(messages);

  const realtimeOverlayActive = Boolean(
    !rtcOverlayForceClosed
    && SUMMIT_VOICE_MODE === "realtime"
    && (
      realtimeMode
      || rtcTimeboxRemaining !== null
      || v2vPhase === "connecting"
      || rtcPremiumStatus === "connecting"
      || rtcPremiumStatus === "listening"
      || rtcPremiumStatus === "transcribing"
      || rtcPremiumStatus === "responding"
      || rtcPremiumStatus === "ending"
    )
    && rtcPremiumStatus !== "cooldown"
  );
  const realtimeOverlayMaxSeconds = Math.max(
    1,
    Math.ceil(Number(rtcTimeboxPolicyRef.current?.maxSeconds || REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS))
  );
  const realtimeOverlayRemainingSeconds = rtcTimeboxRemaining !== null
    ? rtcTimeboxRemaining
    : realtimeOverlayMaxSeconds;
  const realtimeOverlayStatusLabel = getRealtimePremiumStatusLabel();
  const realtimeOverlayDetail = rtcPremiumStatusDetail || (realtimeMode ? "Conversa em tempo real ativa." : "");

  if (!onboardingChecked && !bootstrapFailOpen) {
    return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "#0f1115", color: "#fff", fontFamily: "system-ui" }}>Carregando sua experiência...</div>;
  }

  return (
    <>
    <PWAInstallPrompt />
    <RealtimeTimeboxOverlay
      active={false}
      remainingSeconds={realtimeOverlayRemainingSeconds}
      maxSeconds={realtimeOverlayMaxSeconds}
      status={rtcPremiumStatus || (realtimeMode ? "listening" : null)}
      statusLabel={realtimeOverlayStatusLabel}
      detail={realtimeOverlayDetail}
      voiceLabel="Orkio em tempo real"
      onStop={() => {
        // AO01-HF6R15_REALTIME_OVERLAY_TAP_SHIELD:
        // The fullscreen/timebox overlay can appear immediately after /api/realtime/start.
        // On mobile/PWA, the same tap used to start Realtime may hit the overlay stop control
        // before DataChannel/audio activation. That produced:
        //   client_stop_fullscreen_clock -> transcript_summary_forced_empty -> dc:close
        // Guard early warmup from destructive stop. Real manual stop still works after activation
        // or after the first warmup seconds.
        const sessionAgeMs = getRealtimeSessionAgeMs();

        if (canAccessAdmin || rtcAdminTimeboxBypassRef.current === true || rtcAdminTimeboxBypass === true) {
          try {
            logRealtimeStep("ao01_hf6r16:overlay_stop_ignored_admin_bypass", {
              sessionId: rtcSessionIdRef.current || null,
              sessionAgeMs,
              reason: "client_stop_fullscreen_clock",
            });
          } catch {}
          try { setRtcOverlayForceClosed(true); } catch {}
          try { setRtcTimeboxRemaining(null); } catch {}
          try { clearRealtimeTimeboxTimer(); } catch {}
          try { updateRealtimePremiumStatus("listening", "Realtime admin ativo, sem timebox público."); } catch {}
          return;
        }

        const earlyWarmupOverlayStop = Boolean(
          rtcSessionIdRef.current &&
          !rtcConversationStartedRef.current &&
          Number.isFinite(Number(sessionAgeMs)) &&
          Number(sessionAgeMs) >= 0 &&
          Number(sessionAgeMs) < 12000
        );

        try {
          console.log("REALTIME_MANUAL_END_CLICK", {
            marker: ORKIO_AO66R_HF4_BUILD_MARKER,
            sessionId: rtcSessionIdRef.current || null,
            sessionAgeMs,
            earlyWarmupOverlayStop,
          });
        } catch {}

        if (earlyWarmupOverlayStop) {
          try {
            logRealtimeStep("ao01_hf6r15:overlay_stop_ignored_warmup", {
              sessionId: rtcSessionIdRef.current || null,
              sessionAgeMs,
              reason: "client_stop_fullscreen_clock",
            });
          } catch {}
          try {
            queueRealtimeTelemetry("overlay_stop_ignored_warmup", {
              sessionAgeMs,
              reason: "client_stop_fullscreen_clock",
            });
          } catch {}
          try { setRtcOverlayForceClosed(false); } catch {}
          try { setRealtimeMode(true); } catch {}
          try { realtimeModeRef.current = true; } catch {}
          try { setV2vPhase("connecting"); } catch {}
          try { updateRealtimePremiumStatus("connecting", "Realtime conectando. Mantive a sessão aberta para concluir o áudio."); } catch {}
          try {
            setUploadStatus("⚡ Mantive o Realtime aberto. Aguarde a conexão de voz concluir.");
            setTimeout(() => setUploadStatus(""), 2500);
          } catch {}
          return;
        }

        try { setRtcOverlayForceClosed(true); } catch {}
        try { setRealtimeMode(false); } catch {}
        try { realtimeModeRef.current = false; } catch {}
        try { setRtcTimeboxRemaining(null); } catch {}
        try { setRtcReadyToRespond(false); } catch {}
        try { setV2vPhase(null); } catch {}
        try { updateRealtimePremiumStatus(null, ""); } catch {}
        void stopRealtime("client_stop_fullscreen_clock");
      }}
    />
    <RealtimeTranscriptSummary
      open={realtimeTranscriptSummaryOpen}
      summary={realtimeTranscriptSummary}
      onClose={() => setRealtimeTranscriptSummaryOpen(false)}
    />
    {bootstrapFailOpen && (
      <div style={{ position: "fixed", top: "12px", left: "50%", transform: "translateX(-50%)", zIndex: 120, padding: "10px 14px", borderRadius: "12px", border: "1px solid rgba(251,191,36,0.35)", background: "rgba(120,53,15,0.92)", color: "#fde68a", fontSize: "12px", fontWeight: 700, boxShadow: "0 12px 28px rgba(0,0,0,0.28)" }}>
        Console liberado em modo fail-open. O bootstrap inicial demorou mais que o esperado.
      </div>
    )}
    {showTermsModal && (
      <TermsModal onAccepted={async () => {
        setShowTermsModal(false);
        const resolvedTermsVersion = await fetchCurrentTermsVersion();
        const acceptedAt = Math.floor(Date.now() / 1000);
        // Update local user object + React state to avoid stale gate after acceptance
        const u = getUser();
        if (u) {
          const nextUser = { ...u, terms_accepted_at: acceptedAt, terms_version: resolvedTermsVersion };
          localStorage.setItem("orkio_user", JSON.stringify(nextUser));
          setUser(nextUser);
          if (!nextUser?.onboarding_completed) setOnboardingOpen(true);
        } else {
          setUser((prev) => (prev ? { ...prev, terms_accepted_at: acceptedAt, terms_version: resolvedTermsVersion } : prev));
        }
      }} />
    )}

{onboardingOpen && !showTermsModal && (
      <OnboardingModal
        user={user}
        onComplete={(nextUser) => {
          const refreshedToken = nextUser?.access_token || token;
          const mergedUser = {
            ...(user || {}),
            ...(nextUser || {}),
            org_slug: nextUser?.org_slug || user?.org_slug || tenant,
            role: nextUser?.role || user?.role || "user",
            approved_at: nextUser?.approved_at ?? user?.approved_at ?? null,
            usage_tier: nextUser?.usage_tier ?? user?.usage_tier ?? null,
            signup_source: nextUser?.signup_source ?? user?.signup_source ?? null,
            signup_code_label: nextUser?.signup_code_label ?? user?.signup_code_label ?? null,
            product_scope: nextUser?.product_scope ?? user?.product_scope ?? null,
            onboarding_completed: true,
          };
          mergedUser.is_admin = hasAdminAccess(mergedUser);
          mergedUser.admin = mergedUser.is_admin === true;
          setUser(mergedUser);
          try {
            setSession({
              token: refreshedToken,
              user: mergedUser,
              tenant: mergedUser?.org_slug || tenant,
            });
            setToken(refreshedToken);
          } catch {}
          setOnboardingOpen(false);
          setOnboardingStatus("");
          setUploadStatus("✅ Onboarding concluído.");
          setTimeout(() => setUploadStatus(""), 1800);
        }}
      />
    )}
    <div style={styles.layout}>
      {isMobile && mobileSidebarOpen ? (
        <div
          onClick={() => setMobileSidebarOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 39,
            background: "rgba(2,6,14,0.62)",
            backdropFilter: "blur(4px)",
          }}
        />
      ) : null}
      {/* Sidebar */}
      <div style={{ ...styles.sidebar, display: (!isMobile || mobileSidebarOpen) ? "flex" : "none", position: isMobile ? "fixed" : styles.sidebar.position, inset: isMobile ? "0 auto 0 0" : "auto", width: isMobile ? "min(88vw, 360px)" : styles.sidebar.width, zIndex: isMobile ? 40 : styles.sidebar.zIndex, boxShadow: isMobile ? "0 24px 80px rgba(0,0,0,0.45)" : styles.sidebar.boxShadow, borderRight: isMobile ? "1px solid rgba(255,255,255,0.08)" : styles.sidebar.borderRight }}>
        <div style={styles.topRow}>
          <div>
            <div style={styles.brand}>Orkio</div>
            <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={styles.badge}>org: {tenant}</span>
              <span style={styles.badge}>{health === "ok" ? "ready" : health}</span>
            </div>
          </div>

          <button style={styles.newThreadBtn} onClick={() => { createThread(); if (isMobile) setMobileSidebarOpen(false); }} title="Nova conversa">
            <IconPlus /> Novo
          </button>
        </div>

        <div style={styles.threads}>
          {threads.length === 0 ? (
            <div style={styles.emptyThreads}>Nenhuma conversa ainda.</div>
          ) : (
            threads.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  const nextId = String(t?.id || "");
                  if (nextId && nextId !== String(activeThreadIdRef.current || threadId || "")) {
                    activateThread(nextId, { clearMessages: true, persist: true, lockMs: 15000 });
                    if (isMobile) setMobileSidebarOpen(false);
                  }
                }}
                style={{
                  ...styles.threadItem,
                  ...(t.id === threadId ? styles.threadItemActive : {}),
                }}
              >
                <IconMessage />
                <span style={styles.threadTitle}>{t.title}</span>
                <button
                  style={styles.threadEditBtn}
                  onClick={(e) => { e.stopPropagation(); renameThread(t.id); }}
                  title="Renomear conversa"
                >
                  <IconEdit />
                </button>
                <button
                  style={styles.threadEditBtn}
                  onClick={(e) => { e.stopPropagation(); deleteThread(t.id); }}
                  title="Deletar conversa"
                >
                  <IconTrash />
                </button>
              </button>
            ))
          )}
        </div>

        <div style={styles.userSection}>
          <div style={styles.userInfo}>
            <div style={styles.userAvatar}>{meName.charAt(0).toUpperCase()}</div>
            <div style={styles.userDetails}>
              <div style={styles.userName}>{user?.name || "Usuário"}</div>
              <div style={styles.userEmail}>{user?.email || ""}</div>
            </div>
          </div>

          <div style={styles.userActions}>
            {WALLET_UI_ENABLED ? (
              <button style={styles.iconBtn} onClick={() => nav("/wallet")} title={walletLowBalance ? "Recarregar wallet" : "Wallet & usage"}>
                💳
              </button>
            ) : null}
            {canAccessAdmin && (
              <button style={styles.iconBtn} onClick={() => nav("/admin")} title="Admin Console">
                <IconSettings />
              </button>
            )}
            {!user?.onboarding_completed ? (
              <button
                style={styles.iconBtn}
                onClick={() => setOnboardingOpen(true)}
                title="Completar cadastro"
              >
                ✨
              </button>
            ) : null}
            <button style={styles.iconBtn} onClick={doLogout} title="Sair">
              <IconLogout />
            </button>
          </div>
        </div>
      </div>

      {/* Main */}
      <div style={styles.main}>
        <div style={{ ...styles.topbar, padding: isMobile ? "12px 14px" : styles.topbar.padding }}>
          <div>
            <div style={{ ...styles.title, display: isMobile ? "none" : undefined }}>{threads.find((t) => t.id === threadId)?.title || "Conversa"}</div>
            <div style={{ ...styles.health, display: isMobile ? "none" : undefined }}>
              {publicBetaOrkioOnly
                ? "Destino: Orkio • beta público"
                : `Destino: ${destMode === "team" ? "Team" : destMode === "single" ? "Agente" : "Multi"} • @Team / @Orkio / @Chris${canAccessAdmin ? " / @Orion" : ""}`}
            </div>
            {isMobile ? (
              <div
                style={{
                  marginTop: isMobile ? 0 : 12,
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    try { void loadThreads({ preserveThreadId: String(activeThreadIdRef.current || threadId || "") }); } catch {}
                    setMobileSidebarOpen(true);
                  }}
                  style={{
                    minHeight: 42,
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.14)",
                    background: "rgba(255,255,255,0.08)",
                    color: "#fff",
                    fontWeight: 900,
                    letterSpacing: "-0.01em",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    padding: "0 14px",
                    boxShadow: "0 12px 32px rgba(0,0,0,0.22)",
                    backdropFilter: "blur(12px)",
                  }}
                  aria-label="Abrir conversas"
                  title="Abrir conversas"
                >
                  <IconMessage />
                  Conversas
                </button>

                <button
                  type="button"
                  onClick={() => { void createThread(); }}
                  style={{
                    minHeight: 42,
                    borderRadius: 16,
                    border: "1px solid rgba(255,255,255,0.16)",
                    background: "linear-gradient(135deg, rgba(139,92,246,0.78), rgba(245,158,11,0.54))",
                    color: "#fff",
                    fontWeight: 950,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    padding: "0 14px",
                    boxShadow: "0 12px 32px rgba(0,0,0,0.24)",
                  }}
                  aria-label="Criar nova conversa"
                  title="Nova conversa"
                >
                  <IconPlus />
                  Nova
                </button>
              </div>
            ) : null}
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: isMobile ? "wrap" : "nowrap", justifyContent: "flex-end" }}>
            {isMobile ? (
              <>
                <button
                  type="button"
                  onClick={() => setMobileSidebarOpen((v) => !v)}
                  style={{
                    border: "1px solid rgba(255,255,255,0.14)",
                    background: "rgba(255,255,255,0.08)",
                    color: "#fff",
                    minHeight: 40,
                    padding: "8px 12px",
                    borderRadius: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                  title="Abrir conversas"
                >
                  ☰ Chats
                </button>
                <button
                  type="button"
                  onClick={createThread}
                  style={{
                    border: "1px solid rgba(255,255,255,0.14)",
                    background: "linear-gradient(90deg, rgba(124,92,255,0.32), rgba(255,211,110,0.18))",
                    color: "#fff",
                    minHeight: 40,
                    padding: "8px 12px",
                    borderRadius: 12,
                    fontWeight: 800,
                    cursor: "pointer",
                  }}
                  title="Nova conversa"
                >
                  ＋ Novo
                </button>
              </>
            ) : null}
            {isMobile ? (
              <button
                type="button"
                onClick={doLogout}
                style={{
                  border: "1px solid rgba(255,255,255,0.14)",
                  background: "rgba(255,255,255,0.08)",
                  color: "#fff",
                  minHeight: 40,
                  padding: "8px 12px",
                  borderRadius: 12,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
                title="Sair"
              >
                Sair
              </button>
            ) : null}
            {!publicBetaOrkioOnly ? (
              <>
                <select
                  style={styles.select}
                  value={destMode}
                  onChange={(e) => {
                    const nextMode = String(e.target.value || "team").trim().toLowerCase();
                    setDestMode(["team", "single", "multi"].includes(nextMode) ? nextMode : "team");
                  }}
                >
                  <option value="team">Team</option>
                  <option value="single">1 agente</option>
                  <option value="multi">Multi Agentes</option>
                </select>

                {effectiveDestMode === "single" ? (
                  <select style={styles.select} value={destSingle} onChange={(e) => setDestSingle(e.target.value)}>
                    {visibleAgents.map(a => <option key={a.id} value={a.id}>{formatAgentOptionLabel(a)}</option>)}
                  </select>
                ) : null}

                {effectiveDestMode === "multi" && !isMobile ? (
                  <select style={styles.select} value={String(destMulti.length || 0)} onChange={() => {}}>
                    <option value={String(destMulti.length || 0)}>
                      {destMulti.length ? `${destMulti.length} agentes selecionados` : "Selecionar no envio..."}
                    </option>
                  </select>
                ) : null}
              </>
            ) : (
              <div
                style={{
                  ...styles.select,
                  minHeight: 34,
                  display: "inline-flex",
                  alignItems: "center",
                  fontWeight: 900,
                  color: "rgba(255,255,255,0.88)",
                }}
                title="Beta público: Orkio-only"
              >
                Orkio
              </div>
            )}
          </div>
        </div>

        {(!publicBetaOrkioOnly && (activeRuntimeAgent || runtimeHandoffLabel || agentCapabilities)) ? (
          <div
            style={{
              margin: isMobile ? "10px 12px 0" : "12px 16px 0",
              padding: "10px 12px",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.035)",
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
              color: "rgba(255,255,255,0.82)",
              fontSize: 12,
            }}
          >
            {activeRuntimeAgent ? (
              <span style={{ fontWeight: 800 }}>
                {formatActiveAgentRuntime(activeRuntimeAgent)}
              </span>
            ) : null}
            {runtimeHandoffLabel ? (
              <span style={{ color: "rgba(255,255,255,0.68)" }}>{runtimeHandoffLabel}</span>
            ) : null}
            {agentCapabilities ? (
              <span style={{ marginLeft: "auto", color: "rgba(255,255,255,0.68)" }}>
                GitHub: {formatGithubRuntimeStatus(agentCapabilities)}
              </span>
            ) : null}
          </div>
        ) : null}

        {WALLET_UI_ENABLED ? (

        <div
          style={{
            margin: isMobile ? "10px 12px 0" : "12px 16px 0",
            borderRadius: 18,
            border: walletLowBalance ? "1px solid rgba(251,191,36,0.28)" : "1px solid rgba(255,255,255,0.08)",
            background: walletLowBalance ? "linear-gradient(135deg, rgba(120,53,15,0.28), rgba(30,41,59,0.72))" : "rgba(255,255,255,0.04)",
            padding: isMobile ? "12px" : "14px 16px",
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase", color: walletLowBalance ? "#fbbf24" : "rgba(103,232,249,0.88)" }}>
                Wallet
              </span>
              {walletActivePlanName ? (
                <span style={{ fontSize: 12, color: "rgba(255,255,255,0.72)" }}>
                  Plano ativo: {walletActivePlanName}
                </span>
              ) : (
                <span style={{ fontSize: 12, color: "rgba(255,255,255,0.58)" }}>
                  Acesso orientado por wallet
                </span>
              )}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "baseline" }}>
              <div style={{ fontSize: isMobile ? 22 : 24, fontWeight: 900 }}>{fmtUsd(walletBalanceUsd)}</div>
              <div style={{ fontSize: 13, color: walletLowBalance ? "#fde68a" : "rgba(255,255,255,0.64)" }}>
                {walletLowBalance
                  ? `Saldo baixo. Recomendado manter acima de ${fmtUsd(walletLowBalanceThresholdUsd)}.`
                  : walletAutoRechargeEnabled
                  ? "Auto-recharge ativo."
                  : "Saldo pronto para uso."}
              </div>
            </div>
            {walletSummaryError ? (
              <div style={{ fontSize: 12, color: "#fda4af" }}>{walletSummaryError}</div>
            ) : walletSummaryUpdatedAt ? (
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.44)" }}>
                Atualizado em {formatDateTime(walletSummaryUpdatedAt)}
              </div>
            ) : null}
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={() => { void refreshWalletSummary({ silent: false }); }}
              disabled={walletSummaryLoading}
              style={{
                borderRadius: 12,
                padding: "10px 12px",
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(255,255,255,0.06)",
                color: "#fff",
                fontWeight: 700,
                cursor: walletSummaryLoading ? "default" : "pointer",
                opacity: walletSummaryLoading ? 0.7 : 1,
              }}
            >
              {walletSummaryLoading ? "Atualizando..." : "Atualizar"}
            </button>
            <button
              type="button"
              onClick={() => nav("/wallet")}
              style={{
                borderRadius: 12,
                padding: "10px 12px",
                border: walletLowBalance ? 0 : "1px solid rgba(255,255,255,0.12)",
                background: walletLowBalance ? "linear-gradient(135deg, #f59e0b, #fb7185)" : "rgba(255,255,255,0.08)",
                color: walletLowBalance ? "#111827" : "#fff",
                fontWeight: 900,
                cursor: "pointer",
              }}
            >
              {walletLowBalance ? "Recarregar wallet" : "Abrir wallet"}
            </button>
          </div>
        </div>

        ) : null}

        {/* Messages */}
        <div style={{ ...styles.chatArea, padding: isMobile ? "12px 12px 18px" : styles.chatArea.padding }}>
          {messages.length === 0 ? (
            <div style={styles.premiumEmptyShell}>
              <EmptyStatePremium
                user={user}
                onPrimaryAction={handlePremiumPrimaryAction}
                onSecondaryAction={handlePremiumSecondaryAction}
                onTertiaryAction={handlePremiumTertiaryAction}
                onFillPrompt={fillPremiumPrompt}
              />

              <div style={styles.premiumAside}>
                <div style={styles.premiumAsideCard}>
                  <div style={styles.premiumAsideEyebrow}>Continuity preserved</div>
                  <div style={styles.premiumAsideTitle}>A mudança agora precisa ser impossível de ignorar</div>
                  <div style={styles.premiumAsideText}>
                    O shell principal continua preservado, mas o centro do console passa a comunicar
                    direção, valor e próxima ação com mais intensidade. A ideia não é trocar a rota:
                    é transformar a primeira percepção do produto.
                  </div>

                  <div style={styles.premiumStatusRow}>
                    <div style={styles.premiumStatusCard}>
                      <div style={{ ...styles.premiumStatusLabel, display: isMobile ? "none" : undefined }}>Nova conversa</div>
                      <div style={styles.premiumStatusValue}>Preservada</div>
                    </div>
                    <div style={styles.premiumStatusCard}>
                      <div style={styles.premiumStatusLabel}>Acessos</div>
                      <div style={styles.premiumStatusValue}>{canAccessAdmin ? "Admin + usuário" : "Usuário ativo"}</div>
                    </div>
                    <div style={styles.premiumStatusCard}>
                      <div style={styles.premiumStatusLabel}>Jornada</div>
                      <div style={styles.premiumStatusValue}>Premium in-shell</div>
                    </div>
                  </div>
                </div>

                <div style={styles.premiumAsideCard}>
                  <div style={styles.premiumAsideEyebrow}>Execution preview</div>
                  <ExecutionTimeline steps={EMPTY_STATE_PREVIEW_STEPS} />
                </div>

                <div style={styles.premiumAsideCard}>
                  <div style={styles.premiumAsideEyebrow}>Telemetria executiva</div>
                  <div style={styles.premiumAsideText}>
                    Antes mesmo da primeira mensagem, o usuário já vê sinais concretos de prontidão,
                    continuidade funcional e leitura executiva mais madura.
                  </div>
                  <div style={styles.premiumLogList}>
                    {EMPTY_STATE_PREVIEW_LOGS.map((entry) => (
                      <div key={entry} style={styles.premiumLogItem}>
                        <span style={styles.premiumLogDot} />
                        <span>{entry}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            orderChatMessages(messages).map((m) => (
              <MessageBubble
                key={m.id}
                message={m}
                styles={styles}
                meName={meName}
                lastAgentInfo={lastAgentInfo}
                tryParseEvent={tryParseEvent}
                stripEventMarker={stripEventMarker}
                normalizeMessageSpeaker={normalizeMessageSpeaker}
                resolveAssistantDisplayName={resolveAssistantDisplayName}
                formatDateTime={formatDateTime}
                formatTs={formatTs}
                humanizeConsoleStatusMessage={humanizeConsoleStatusMessage}
                normalizeUserFacingRuntimeMessage={normalizeUserFacingRuntimeMessage}
                renderMessageContentPremium={renderMessageContentPremium}
                playTts={playTts}
                stopTts={stopTts}
                ttsPlaying={ttsPlaying}
                ttsPlayingMessageId={ttsPlayingMessageId}
                extractPatchGovernanceMeta={extractPatchGovernanceMeta}
                openPatchApprovalModal={openPatchApprovalModal}
                extractPatchApprovalMeta={extractPatchApprovalMeta}
                executeApprovedPatchFromMessage={executeApprovedPatchFromMessage}
                canAccessAdmin={canAccessAdmin}
              />
            ))          )}
          <div ref={messagesEndRef} />
        </div>

        {/* V2V-PATCH: status panel por fase */}
        {v2vPhase && (
          <div style={{
            padding: "6px 14px", margin: "4px 0",
            borderRadius: "6px", fontSize: "12px", fontWeight: 500,
            background: v2vPhase === 'error' ? "rgba(192,57,43,0.15)" : "rgba(10,126,140,0.12)",
            color: v2vPhase === 'error' ? "#e74c3c" : "#0A7E8C",
            border: `1px solid ${v2vPhase === 'error' ? "rgba(192,57,43,0.3)" : "rgba(10,126,140,0.25)"}`,
            display: "flex", alignItems: "center", gap: "8px",
          }}>
            <span>{
              v2vPhase === 'recording' ? "🔴 Gravando..." :
              v2vPhase === 'stt'       ? "⚙️ Transcrevendo fala..." :
              v2vPhase === 'chat'      ? "🤖 Gerando resposta..." :
              v2vPhase === 'tts'       ? "🔊 Sintetizando voz..." :
              v2vPhase === 'playing'   ? "🔈 Reproduzindo..." :
              v2vPhase === 'connecting'? "🎙️ Conectando..." :
              v2vPhase === 'listening' ? "🎙️ Ouvindo... 📝 Transcrição ativa" :
              v2vPhase === 'responding'? "🔊 Orkio respondendo..." :
              v2vPhase === 'cooldown'  ? `🕒 ${v2vError || "Voz em cooldown. O chat por texto continua disponível."}` :
              v2vPhase === 'error'     ? `❌ ${v2vError || "Erro no V2V"}` :
              "⏳ Aguardando..."
            }</span>
            {v2vPhase === 'error' && walletBlockedDetail?.code === "WALLET_INSUFFICIENT_BALANCE" && (
              <button
                type="button"
                onClick={() => nav("/wallet")}
                style={{
                  marginLeft: "auto",
                  border: 0,
                  borderRadius: "999px",
                  padding: "7px 12px",
                  cursor: "pointer",
                  fontWeight: 800,
                  background: "linear-gradient(135deg, #f59e0b, #fb7185)",
                  color: "#111827",
                }}
              >
                Recarregar wallet
              </button>
            )}
            {v2vPhase === 'error' && (
              <button type="button" onClick={() => { setV2vPhase(null); setV2vError(null); setWalletBlockedDetail(null); }}
                style={{ marginLeft: walletBlockedDetail?.code === "WALLET_INSUFFICIENT_BALANCE" ? 0 : "auto", background: "none", border: "none", cursor: "pointer", color: "#e74c3c", fontSize: "14px" }}>
                ✕
              </button>
            )}
          </div>
        )}
        {shouldShowRealtimeCounter() ? (
          <div
            style={{
              margin: "4px 0",
              padding: "8px 12px",
              borderRadius: "12px",
              border: "1px solid rgba(96,165,250,0.24)",
              background: "rgba(15,23,42,0.62)",
              color: "#dbeafe",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexWrap: "wrap",
              fontSize: "12px",
              fontWeight: 700,
            }}
          >
            <span>{getRealtimePremiumStatusLabel()}</span>
            {rtcPremiumStatusDetail ? <span style={{ opacity: 0.82 }}>{rtcPremiumStatusDetail}</span> : null}
            {getRealtimeCounterLabel() ? (
              <span style={{ marginLeft: "auto", opacity: 0.95 }}>{getRealtimeCounterLabel()}</span>
            ) : null}
            {realtimeMode ? <span style={{ opacity: 0.8 }}>🔆 Tela ativa</span> : null}
          </div>
        ) : null}
        {uploadStatus ? <div style={styles.uploadStatus}>{uploadStatus}</div> : null}

        {shouldShowRealtimeCounter() ? (
          <div
            data-orkio-realtime-counter="ao61a-hf4"
            style={{
              position: "fixed",
              top: "calc(env(safe-area-inset-top, 0px) + 12px)",
              right: 12,
              zIndex: 2147483000,
              minWidth: 148,
              maxWidth: "min(320px, calc(100vw - 24px))",
              borderRadius: 16,
              border: "1px solid rgba(147,197,253,0.45)",
              background: "linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.94))",
              color: "#eff6ff",
              boxShadow: "0 18px 50px rgba(2,6,23,0.35)",
              padding: "10px 12px",
              pointerEvents: "none",
              display: "flex",
              flexDirection: "column",
              gap: 4,
              fontSize: 12,
              lineHeight: 1.2,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
              <strong style={{ fontSize: 12 }}>{getRealtimeFixedCounterTitle()}</strong>
              <span style={{ fontSize: 18, fontWeight: 900, letterSpacing: "0.02em" }}>{getRealtimeCounterLabel() || "⏳ --:--"}</span>
            </div>
            <div style={{ opacity: 0.84, fontSize: 11 }}>
              {getRealtimeFixedCounterSubtitle() || "O chat por texto continua disponível."}
            </div>
            {realtimeMode ? <div style={{ opacity: 0.82, fontSize: 11 }}>🔆 Tela ativa</div> : null}
          </div>
        ) : null}

        {patchApprovalModal && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.55)",
              zIndex: 9999,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 16,
            }}
            onClick={() => !patchApprovalBusy && setPatchApprovalModal(null)}
          >
            <div
              style={{
                width: "min(480px, 100%)",
                borderRadius: 18,
                border: "1px solid rgba(255,255,255,0.16)",
                background: "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(2,6,23,0.98))",
                color: "#e5e7eb",
                boxShadow: "0 24px 80px rgba(0,0,0,0.45)",
                padding: 18,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ fontSize: 18, fontWeight: 900, marginBottom: 8 }}>Aprovar patch governado</div>
              <div style={{ fontSize: 13, opacity: 0.82, lineHeight: 1.5, marginBottom: 12 }}>
                Esta aprovação não passa pelo chat. Sua senha confirma a autorização humana para o pending proposal desta thread.
              </div>
              <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 10 }}>
                audit_receipt_id: {patchApprovalModal.audit_receipt_id || "n/d"}
              </div>
              <input
                type="password"
                autoFocus
                value={patchApprovalPassword}
                onChange={(e) => setPatchApprovalPassword(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !patchApprovalBusy) submitPatchApproval(); }}
                placeholder="Digite sua senha"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  border: "1px solid rgba(255,255,255,0.18)",
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.06)",
                  color: "#fff",
                  padding: "12px 14px",
                  outline: "none",
                  marginBottom: 10,
                }}
              />
              {patchApprovalError && (
                <div style={{ color: "#fca5a5", fontSize: 13, marginBottom: 10 }}>{patchApprovalError}</div>
              )}
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button
                  type="button"
                  disabled={patchApprovalBusy}
                  onClick={() => setPatchApprovalModal(null)}
                  style={{ border: 0, borderRadius: 999, padding: "9px 13px", cursor: "pointer", background: "rgba(255,255,255,0.08)", color: "#e5e7eb" }}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={patchApprovalBusy}
                  onClick={submitPatchApproval}
                  style={{ border: 0, borderRadius: 999, padding: "9px 14px", cursor: "pointer", background: "linear-gradient(135deg, #10b981, #22c55e)", color: "#052e16", fontWeight: 900 }}
                >
                  {patchApprovalBusy ? "Validando..." : "Confirmar aprovação"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Composer */}
        <div style={{ ...styles.composerContainer, padding: isMobile ? "10px 12px calc(10px + env(safe-area-inset-bottom, 0px))" : styles.composerContainer.padding }}>
          {canAccessAdmin && showOrionSquad && (orionSquadHealth || orionSquadPreview) ? (
            <div
              style={{
                marginBottom: "8px",
                padding: "8px 10px",
                borderRadius: "10px",
                border: "1px solid rgba(89,165,255,0.25)",
                background: "rgba(89,165,255,0.08)",
                fontSize: "12px",
                lineHeight: 1.35,
                color: "rgba(255,255,255,0.86)",
              }}
            >
              <div><strong>Orion Squad:</strong> {orionSquadHealth?.ok === false ? "offline" : "online"}</div>
              {orionSquadHealth?.agents_loaded ? <div><strong>Agents loaded:</strong> {orionSquadHealth.agents_loaded}</div> : null}
              {orionSquadPreview?.primary_specialist ? <div><strong>Primary specialist:</strong> {orionSquadPreview.primary_specialist}</div> : null}
              {orionSquadPreview?.secondary_specialist ? <div><strong>Secondary specialist:</strong> {orionSquadPreview.secondary_specialist}</div> : null}
            </div>
          ) : null}


{executionTrace.length ? (
  <div
    style={{
      marginBottom: "8px",
      borderRadius: "14px",
      border: "1px solid rgba(255,255,255,0.08)",
      background: "rgba(255,255,255,0.035)",
      overflow: "hidden",
    }}
  >
    <button
      type="button"
      onClick={() => setExecutionTraceExpanded((prev) => {
        const next = !prev;
        try { window.localStorage?.setItem("orkio_execution_trace_open", next ? "1" : "0"); } catch {}
        return next;
      })}
      style={{
        width: "100%",
        border: 0,
        background: "transparent",
        color: "#fff",
        padding: "12px 14px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <div>
        <div style={{ fontSize: 13, fontWeight: 900, letterSpacing: "0.01em" }}>
          {executionTraceExpanded ? "Execution trace" : "Ver execução"}
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.62)", marginTop: 2 }}>
          {sending
            ? "Orkio está executando etapas desta solicitação."
            : executionTraceExpanded
            ? "Última execução registrada no console."
            : "Execução recolhida automaticamente. Abra apenas se quiser revisar."}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {lastTraceId ? (
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.44)", fontFamily: "monospace" }}>
            {lastTraceId}
          </span>
        ) : null}
        <span style={{ fontSize: 16, opacity: 0.8 }}>{executionTraceExpanded ? "▾" : "▸"}</span>
      </div>
    </button>

    {!executionTraceExpanded ? (
      <div style={{ padding: "0 14px 14px", display: "grid", gap: 8 }}>
        <div style={{ color: "rgba(255,255,255,0.66)", fontSize: 12, lineHeight: 1.45 }}>
          {(() => {
            // AO45_TRACE_LITE_HONESTY
            const last = executionTrace[executionTrace.length - 1] || {};
            const isLite =
              last?.execution_depth === "lite" ||
              last?.trace_lite === true ||
              last?.dispatch_runtime_executed === false ||
              last?.badges?.includes?.("readonly specialist audit");

            const countLabel = isLite
              ? `${Math.min(executionTrace.length, 3)} sinal(is) registrados`
              : `${executionTrace.length} etapa(s) registradas`;

            return `${isLite ? "Trace Lite. " : ""}${countLabel}. ${
              executionTrace.some((step) => step.kind === "done")
                ? "Fluxo encerrado com segurança."
                : "Execução em andamento."
            }`;
          })()}
        </div>
        {executionTrace[executionTrace.length - 1]?.badges?.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {executionTrace[executionTrace.length - 1].badges.map((badge) => (
              <span
                key={badge}
                style={{
                  fontSize: 11,
                  padding: "4px 8px",
                  borderRadius: 999,
                  background: "rgba(34,197,94,0.12)",
                  border: "1px solid rgba(34,197,94,0.22)",
                  color: "rgba(187,247,208,0.92)",
                }}
              >
                {badge}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    ) : null}

    {executionTraceExpanded ? (
      <div style={{ padding: "0 14px 14px", display: "grid", gap: 8 }}>
        {executionTrace.map((step) => {
          const tone = traceStepTone(step.kind);
          return (
            <div
              key={step.id}
              style={{
                borderRadius: 12,
                border: `1px solid ${tone.border}`,
                background: tone.background,
                padding: "10px 12px",
                display: "grid",
                gap: 4,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <span style={{ fontSize: 14 }}>{tone.icon}</span>
                <span style={{ fontSize: 13, fontWeight: 800, color: tone.color, minWidth: 0 }}>
                  {step.label}
                </span>
                {step.agentName ? (
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: 11,
                      padding: "3px 8px",
                      borderRadius: 999,
                      background: "rgba(255,255,255,0.08)",
                      color: "rgba(255,255,255,0.7)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {step.agentName}
                  </span>
                ) : null}
              </div>
              {step.badges?.length ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {step.badges.map((badge) => (
                    <span
                      key={`${step.id}-${badge}`}
                      style={{
                        fontSize: 11,
                        padding: "3px 8px",
                        borderRadius: 999,
                        background: "rgba(34,197,94,0.10)",
                        border: "1px solid rgba(34,197,94,0.20)",
                        color: "rgba(187,247,208,0.92)",
                      }}
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              ) : null}
              {(step.detail || step.ts) ? (
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.72)", lineHeight: 1.4 }}>
                  {step.detail || ""}
                  {step.ts ? (
                    <span style={{ color: "rgba(255,255,255,0.38)", marginLeft: step.detail ? 8 : 0 }}>
                      {new Date(step.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    ) : null}
  </div>
) : null}
          {showRuntimeHints && runtimeHints ? (
            <div
              style={{
                marginBottom: "8px",
                padding: "8px 10px",
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.08)",
                background: "rgba(255,255,255,0.03)",
                fontSize: "12px",
                lineHeight: 1.35,
                color: "rgba(255,255,255,0.78)",
              }}
            >
              {runtimeHints?.planner?.primary_objective ? <div><strong>Focus:</strong> {runtimeHints.planner.primary_objective}</div> : null}
              {runtimeHints?.resume_hint ? <div><strong>Continuity:</strong> {runtimeHints.resume_hint}</div> : null}
              {runtimeHints?.trial?.recommended_action ? <div><strong>Next:</strong> {runtimeHints.trial.recommended_action}</div> : null}
              {runtimeHints?.routing?.mode ? <div><strong>Route:</strong> {runtimeHints.routing.mode}</div> : null}
              {runtimeHints?.trial?.stage ? <div><strong>Stage:</strong> {runtimeHints.trial.stage}</div> : null}
              {(runtimeHints?.planner?.confidence ?? null) !== null ? <div><strong>Confidence:</strong> {runtimeHints.planner.confidence}</div> : null}
              {(runtimeHints?.trial?.activation_probability ?? null) !== null ? <div><strong>Activation probability:</strong> {runtimeHints.trial.activation_probability}</div> : null}
              {(runtimeHints?.memory?.strong_resume_ready ?? null) !== null ? <div><strong>Resume readiness:</strong> {runtimeHints.memory.strong_resume_ready ? "ready" : "warming"}</div> : null}
              {runtimeHints?.routing?.execution_cursor?.current_node ? <div><strong>Current node:</strong> {runtimeHints.routing.execution_cursor.current_node}</div> : null}
              {(runtimeHints?.routing?.routing_confidence ?? null) !== null ? <div><strong>Routing confidence:</strong> {runtimeHints.routing.routing_confidence}</div> : null}
              {runtimeHints?.capabilities?.multiagent?.available_agents?.length ? <div><strong>Agents:</strong> {runtimeHints.capabilities.multiagent.available_agents.join(", ")}</div> : null}
              {runtimeHints?.capabilities?.github ? <div><strong>GitHub:</strong> {formatGithubRuntimeStatus(runtimeHints.capabilities)}</div> : null}
              {lastTraceId ? <div><strong>Trace:</strong> {lastTraceId}</div> : null}
            </div>
          ) : null}
          {pendingApprovedPatchExecution ? (
            <div style={{
              margin: "8px 14px",
              padding: "12px 14px",
              borderRadius: 14,
              border: "1px solid rgba(59,130,246,0.45)",
              background: "rgba(59,130,246,0.12)",
              color: "#dbeafe",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}>
              <div style={{ fontWeight: 800 }}>
                Execução governada aprovada pendente. O chat comum está bloqueado até executar ou cancelar.
              </div>
              <button
                type="button"
                data-patch-execute-button="true"
                onClick={() => executeApprovedPatchFromMessage(pendingApprovedPatchExecution.message)}
                style={{
                  border: "1px solid rgba(59,130,246,0.65)",
                  borderRadius: 999,
                  padding: "9px 13px",
                  background: "rgba(59,130,246,0.22)",
                  color: "#eff6ff",
                  cursor: "pointer",
                  fontWeight: 900,
                }}
              >
                Executar patch aprovado
              </button>
            </div>
          ) : null}
          <div style={{ ...styles.composer, gap: isMobile ? "8px" : styles.composer.gap }}>
            <input
              type="file"
              ref={fileInputRef}
              onChange={onPickFile}
              accept=".pdf,.docx,.doc,.txt,.md"
              style={{ display: "none" }}
            />

            {!isMobile ? (
              <button
                type="button"
                style={styles.attachBtn}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadProgress || !!pendingApprovedPatchExecution}
                title="Anexar arquivo (PDF, DOCX, TXT)"
              >
                <IconPaperclip />
              </button>
            ) : null}

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={pendingApprovedPatchExecution ? "Execução aprovada pendente — use o botão governado acima." : "Escreva sua mensagem..."}
              style={styles.textarea}
              rows={1}
              disabled={sending || !!pendingApprovedPatchExecution}
            />

            {SUMMIT_VOICE_MODE === "stt_tts" ? (
              <button
                type="button"
                style={{ ...styles.micBtn, opacity: speechSupported ? 1 : 0.6 }}
                onClick={toggleMic}
                title={micEnabled ? "Parar entrada por voz" : "Iniciar entrada por voz"}
              >
                🎙️
              </button>
            ) : (
              <>
                <button
                  type="button"
                  style={{
                    ...styles.micBtn,
                    background: realtimeMode ? "rgba(80,160,255,0.25)" : "rgba(255,255,255,0.05)",
                    border: realtimeMode ? "1px solid rgba(80,160,255,0.5)" : "1px solid rgba(255,255,255,0.1)",
                    position: "relative",
                    opacity: (!realtimeMode && rtcCooldownRemaining > 0) ? 0.45 : 1,
                    cursor: (!realtimeMode && rtcCooldownRemaining > 0) ? "not-allowed" : "pointer",
                  }}
                  onClick={toggleRealtimeMode}
                  disabled={!realtimeMode && rtcCooldownRemaining > 0}
                  title={
                    (!realtimeMode && rtcCooldownRemaining > 0)
                      ? `Voz disponível novamente em ${formatRealtimeCountdown(rtcCooldownRemaining)}`
                      : realtimeMode ? "Desativar voz em tempo real" : "Ativar voz em tempo real"
                  }
                >
                  <span style={{ fontSize: "16px" }}>⚡</span>
                  {realtimeMode && <span style={{ position: "absolute", top: "-2px", right: "-2px", width: "8px", height: "8px", borderRadius: "50%", background: "#50a0ff", animation: "pulse 1.5s infinite" }} />}
                </button>
                {SUMMIT_VOICE_MODE === "realtime" && (isRealtimeTimeboxLimitedUser() || rtcBackendTimeboxLimited || rtcCooldownRemaining > 0) && (realtimeMode || rtcCooldownRemaining > 0) ? (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      height: "32px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {realtimeMode ? (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                          height: "32px",
                          padding: "0 8px",
                          borderRadius: "999px",
                          border: "1px solid rgba(255,255,255,0.12)",
                          background: "rgba(255,255,255,0.05)",
                          fontSize: "12px",
                          lineHeight: "1",
                          opacity: 0.95,
                        }}
                        title="Tentando manter a tela ligada durante a voz"
                      >
                        <span aria-hidden="true">🔆</span>
                        <span>Tela ativa</span>
                      </span>
                    ) : null}
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        minWidth: "64px",
                        height: "32px",
                        padding: "0 8px",
                        borderRadius: "999px",
                        border: "1px solid rgba(255,255,255,0.12)",
                        background: "rgba(255,255,255,0.05)",
                        fontSize: "12px",
                        lineHeight: "1",
                        whiteSpace: "nowrap",
                        opacity: 0.95,
                      }}
                      title={realtimeMode ? "Tempo restante da sessão de voz" : "Voz disponível novamente em breve"}
                    >
                      <span aria-hidden="true">{realtimeMode ? "⏳" : "🕒"}</span>
                      <span>{realtimeMode ? formatRealtimeCountdown(rtcTimeboxRemaining ?? REALTIME_PUBLIC_BETA_TIMEBOX_SECONDS) : formatRealtimeCountdown(rtcCooldownRemaining)}</span>
                    </span>
                  </span>
                ) : null}
              </>
            )}

            {!isMobile && realtimeMode && SUMMIT_VOICE_MODE === "realtime" ? (
              <button
                type="button"
                style={{
                  ...styles.sendBtn,
                  opacity: rtcReadyToRespond ? 1 : 0.5,
                  cursor: rtcReadyToRespond ? "pointer" : "not-allowed",
                }}
                onClick={() => rtcReadyToRespond && triggerRealtimeResponse("manual")}
                disabled={!rtcReadyToRespond}
                title={rtcReadyToRespond ? "Responder agora (tempo real)" : "Aguardando a fala terminar"}
              >
                ▶️
              </button>
            ) : null}

            <button
              type="button"
              style={{ ...styles.micBtn, opacity: handoffBusy ? 0.7 : 1 }}
              onClick={handleFounderHandoff}
              disabled={handoffBusy}
              title="Falar com fundador"
            >
              🤝
            </button>

            <button type="button" style={styles.sendBtn} onMouseDown={(e) => e.preventDefault()} onClick={() => sendMessage()} disabled={sending || !!pendingApprovedPatchExecution} title="Enviar">
              <IconSend />
            </button>
          </div>
          {handoffNotice ? (
            <div style={{ marginTop: 8, fontSize: 12, color: "rgba(255,255,255,0.78)" }}>{handoffNotice}</div>
          ) : null}
          <div style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.62)" }}>
              Respostas geradas por IA podem conter imprecisões. Sempre valide informações importantes antes de tomar decisões.
            </div>
            <div style={{ display: isMobile ? "none" : "flex", gap: 8 }}>
              <button
                onClick={downloadRealtimeAta}
                style={{ ...styles.btn, padding: "6px 10px", fontSize: "12px", opacity: rtcSessionIdRef.current ? 1 : 0.6 }}
                title="Baixar relatório executivo da sessão"
                disabled={!rtcSessionIdRef.current}
              >
                ⬇️ Relatório
              </button>
            </div>
          </div>

          {/* Voice Mode controls — PATCH0100_14 enhanced */}
          {voiceMode && SUMMIT_VOICE_MODE === "stt_tts" && !isMobile && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 8px", fontSize: "12px", color: "rgba(255,255,255,0.7)", flexWrap: "wrap" }}>
              {lastAgentInfo?.avatar_url && (
                <img src={lastAgentInfo.avatar_url} alt="" style={{ width: 24, height: 24, borderRadius: "50%", objectFit: "cover" }} onError={(e) => { e.target.style.display = 'none'; }} />
              )}
              {lastAgentInfo?.agent_name && <span style={{ fontWeight: 600, color: "rgba(255,255,255,0.85)" }}>{lastAgentInfo.agent_name}</span>}
              <span>🔊 Voz:</span>
              <select
                value={ttsVoice}
                onChange={(e) => changeTtsVoice(e.target.value)}
                style={{ ...styles.select, padding: "4px 8px", fontSize: "11px" }}
              >
                <option value="auto">Auto (voz do agente)</option>
                {ORKIO_VOICES.map(v => (
                  <option key={v.id} value={v.id}>{v.label}</option>
                ))}
</select>
              {ttsPlaying && (
                <button
                  onClick={stopTts}
                  style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}
                >
                  ⏹ Parar
                </button>
              )}
              <span style={{ opacity: 0.6 }}>
                {micEnabled ? "🔴 Ouvindo..." : ttsPlaying ? "🔊 Falando..." : "⏸ Aguardando"}
              </span>
              {!!(rtcSessionIdRef.current || rtcAuditEvents?.length) && (
                <button
                  onClick={downloadRealtimeAta}
                  style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}
                  title="Baixar relatório executivo da sessão"
                >
                  ⬇️ Relatório
                </button>
              )}
            </div>
          )}

          {/* PATCH0100_27_2B: Realtime Audit (finals + punctuação assíncrona) */}
          {SHOW_REALTIME_AUDIT && !isMobile && (rtcAuditEvents?.length > 0 || rtcPunctStatus) && (
            <div style={styles.realtimeAudit}>
              <div style={styles.realtimeAuditHeader}>
                <div style={styles.realtimeAuditTitle}>🧾 Realtime (auditável)</div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={styles.realtimeAuditPill}>
                    {rtcPunctStatus === 'pending' ? 'Pontuando…' : rtcPunctStatus === 'done' ? 'Pontuação OK' : rtcPunctStatus === 'timeout' ? 'Pontuação pendente' : 'Registro local'}
                  </div>
                  <button
                    onClick={downloadRealtimeAta}
                    style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}
                    title="Baixar ata da sessão"
                  >
                    ⬇️ Baixar ata
                  </button>
                </div>
              </div>
              {rtcAuditEvents.map((ev, idx) => {
                const who = ev?.role === 'user' ? 'Você' : (ev?.agent_name || 'Assistente');
                const when = ev?.created_at ? new Date(ev.created_at).toLocaleTimeString() : '';
                const text = (ev?.transcript_punct || ev?.content || '').toString();
                return (
                  <div key={(ev?.id || idx) + ''} style={styles.realtimeAuditItem}>
                    <div style={styles.realtimeAuditMeta}>
                      <div style={styles.realtimeAuditWho}>{who}</div>
                      <div style={{ opacity: 0.7 }}>{when}</div>
                    </div>
                    <div style={styles.realtimeAuditText}>{text}</div>
                  </div>
                );
              })}
              {summitSessionScore && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                  <div style={{ fontWeight: 800, marginBottom: 6 }}>🎯 Summit score</div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: 12, opacity: 0.9 }}>
                    <span>Naturalidade: {summitSessionScore?.naturalness_score ?? "-"}</span>
                    <span>Persona: {summitSessionScore?.persona_score ?? "-"}</span>
                    <span>Duplicação: {summitSessionScore?.duplicate_count ?? 0}</span>
                    <span>Truncamento: {summitSessionScore?.truncation_count ?? 0}</span>
                  </div>
                  {!summitSessionScore?.human_review && summitRuntimeModeRef.current === "summit" && (
                    <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                      <button disabled={summitReviewPending} onClick={() => submitStageReview(5, 5, 5)} style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}>✅ Forte</button>
                      <button disabled={summitReviewPending} onClick={() => submitStageReview(4, 4, 4)} style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}>🟨 Bom</button>
                      <button disabled={summitReviewPending} onClick={() => submitStageReview(2, 2, 2)} style={{ ...styles.btn, padding: "4px 8px", fontSize: "11px" }}>🛠 Ajustar</button>
                    </div>
                  )}
                </div>
              )}
              {rtcAuditEvents.length === 0 && <div style={{ opacity: 0.8 }}>Sem eventos finais ainda.</div>}
            </div>
          )}


          {destMode === "multi" ? (
            <div style={{...styles.hint, display: isMobile ? "none" : styles.hint.display}}>
              Multi: selecione os agentes abaixo (será usado no próximo envio).
              <div style={styles.checkGrid}>
                {agents.map(a => (
                  <label key={a.id} style={styles.checkItem}>
                    <input
                      type="checkbox"
                      checked={destMulti.includes(a.id)}
                      onChange={(e) => {
                        setDestMulti((prev) => {
                          const base = Array.isArray(prev) ? prev.map((x) => String(x || "")) : [];
                          if (e.target.checked) return Array.from(new Set([...base, String(a.id)]));
                          return base.filter((x) => String(x) !== String(a.id));
                        });
                      }}
                    />
                    <span>{a.name}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>


      {showHandoffModal ? (
        <div style={styles.modalBack} onClick={() => { if (!handoffBusy) setShowHandoffModal(false); }}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>Talk to founder</div>
            <div style={styles.hint}>
              You are about to share this conversation with the Orkio founder for follow-up.
            </div>
            <div style={{ ...styles.hint, marginTop: 8 }}>
              Orkio will share a concise summary of your context so the next step can be strategic, not repetitive.
            </div>
            <div style={{ marginTop: 12, padding: 12, borderRadius: 12, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)", fontSize: 13, lineHeight: 1.45 }}>
              {handoffDraft || "Your latest strategic context will be shared with the founder."}
            </div>
            <div style={{ ...styles.hint, marginTop: 10 }}>
              By continuing, you explicitly authorize Orkio to share this conversation summary with the founder for direct follow-up.
            </div>
            <div style={styles.modalActions}>
              <button style={styles.btn} onClick={() => setShowHandoffModal(false)} disabled={handoffBusy}>Cancel</button>
              <button type="button" style={{ ...styles.btn, ...styles.btnPrimary, opacity: handoffBusy ? 0.7 : 1 }} onClick={confirmFounderHandoff} disabled={handoffBusy}>
                {handoffBusy ? "Sending..." : "Confirm and share"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Upload Modal */}
      {uploadOpen ? (
        <div style={styles.modalBack} onClick={() => { if (!uploadProgress) setUploadOpen(false); }}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalTitle}>Upload: {uploadFileObj?.name || "arquivo"}</div>
            <div style={styles.hint}>Escolha como este documento será usado.</div>

            <div style={styles.radioRow}>
              <input type="radio" checked={uploadScope === "thread"} onChange={() => setUploadScope("thread")} />
              <span>Somente nesta conversa (contexto do thread)</span>
            </div>

            {!publicBetaOrkioOnly ? (
              <>
                <div style={styles.radioRow}>
                  <input type="radio" checked={uploadScope === "agents"} onChange={() => setUploadScope("agents")} />
                  <span>Vincular a agente(s) específico(s)</span>
                </div>

                {uploadScope === "agents" ? (
                  <div style={styles.checkGrid}>
                    {visibleAgents.map(a => (
                      <label key={a.id} style={styles.checkItem}>
                        <input
                          type="checkbox"
                          checked={uploadAgentIds.includes(a.id)}
                          onChange={(e) => {
                            setUploadAgentIds(prev => e.target.checked ? [...prev, a.id] : prev.filter(x => x !== a.id));
                          }}
                        />
                        <span>{a.name}</span>
                      </label>
                    ))}
                  </div>
                ) : null}
              </>
            ) : null}

            <div style={styles.radioRow}>
              <input type="radio" checked={uploadScope === "institutional"} onChange={() => setUploadScope("institutional")} />
              <span>Institucional (global do tenant → todos os agentes)</span>
            </div>
            <div style={styles.hint}>
              {canAccessAdmin
                ? "Como admin, o documento vira institucional imediatamente."
                : "Como usuário, isso vira uma SOLICITAÇÃO para o admin aprovar/reprovar. Enquanto isso, ele fica disponível nesta conversa."}
            </div>

            <div style={styles.modalActions}>
              <button style={styles.btn} onClick={() => { if (!uploadProgress) setUploadOpen(false); }}>Cancelar</button>
              <button type="button" style={{ ...styles.btn, ...styles.btnPrimary, opacity: uploadProgress ? 0.7 : 1 }} onClick={confirmUpload} disabled={uploadProgress}>
                {uploadProgress ? "Enviando..." : "Enviar"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    
{capacityOpen ? (
  <div style={{
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999
  }}>
    <div style={{
      background: "#0f0f10", color: "#fff", padding: 24, borderRadius: 12,
      maxWidth: 520, width: "92%", boxShadow: "0 10px 40px rgba(0,0,0,0.6)"
    }}>
      <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 10 }}>
        Estamos operando no limite seguro da plataforma
      </div>
      <div style={{ opacity: 0.9, lineHeight: 1.4, marginBottom: 14 }}>
        Muitas pessoas estão acessando ao mesmo tempo. Para manter a estabilidade durante o evento,
        alguns acessos estão temporariamente limitados.
      </div>
      <div style={{ opacity: 0.9, marginBottom: 16 }}>
        Você poderá tentar novamente em <b>{capacitySeconds}s</b>, ou manualmente quando desejar.
      </div>
      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <button style={{ padding: "10px 14px", borderRadius: 10 }} onClick={() => {
          const pending = capacityPendingRef.current;
          closeCapacityModal();
          if (pending?.msg) sendMessage(pending.msg);
        }}>
          Tentar agora
        </button>
        <button style={{ padding: "10px 14px", borderRadius: 10, opacity: 0.9 }} onClick={closeCapacityModal}>
          Voltar
        </button>
      </div>
    </div>
  </div>
) : null}

</div>
    </>
  );
}
