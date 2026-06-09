import { useCallback, useRef, useState } from "react";

// AO64D-HF1_REALTIME_TRANSCRIPT_SUMMARY_HOOK
// Responsibility:
// - keep transcript turns
// - build/publish summary
// - optionally inline transcript back to chat
// Does not touch WebRTC, DataChannel, response.create, stopRealtime, quota, cooldown or backend.
export function useRealtimeTranscriptSummary({
  logRealtimeStep,
  getSessionId,
  getUserTextFallback,
  getAssistantTextFallback,
  appendSummaryToChat,
  inlineToChat = true,
  modalSuppressed = true,
} = {}) {
  const [summary, setSummary] = useState(null);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const turnsRef = useRef([]);

  const safeLog = useCallback((event, meta = {}) => {
    try {
      if (typeof logRealtimeStep === "function") logRealtimeStep(event, meta);
    } catch {}
  }, [logRealtimeStep]);

  const normalizeText = useCallback((value) => {
    return String(value || "").replace(/\s+/g, " ").trim();
  }, []);

  const reset = useCallback((reason = "reset") => {
    try { turnsRef.current = []; } catch {}
    try { setSummary(null); } catch {}
    try { setSummaryOpen(false); } catch {}
    safeLog("ao66a:transcript_summary_reset", { reason, marker: "AO64D_HF1_SUMMARY_HOOK" });
  }, [safeLog]);

  const appendTurn = useCallback((role, content, meta = {}) => {
    const text = normalizeText(content);
    if (!text) return false;

    const safeRole = role === "assistant" ? "assistant" : "user";
    const now = Math.floor(Date.now() / 1000);
    const nextTurn = {
      id: `rt_${safeRole}_${now}_${Math.random().toString(16).slice(2)}`,
      role: safeRole,
      label: safeRole === "assistant" ? "Orkio respondeu" : "Você disse",
      content: text,
      created_at: now,
      meta: meta && typeof meta === "object" ? meta : {},
    };

    try {
      const prev = Array.isArray(turnsRef.current)
        ? turnsRef.current.slice()
        : [];

      const last = prev[prev.length - 1];
      const shouldUpgradeAssistant = Boolean(
        safeRole === "assistant"
        && last
        && last.role === "assistant"
        && text.length >= String(last.content || "").length
      );

      if (shouldUpgradeAssistant) {
        prev[prev.length - 1] = {
          ...last,
          ...nextTurn,
          id: last.id,
          meta: { ...(last.meta || {}), ...(nextTurn.meta || {}), upgraded: true },
        };
      } else if (!last || last.role !== safeRole || String(last.content || "").trim() !== text) {
        prev.push(nextTurn);
      }

      turnsRef.current = prev.slice(-12);
      return true;
    } catch {
      return false;
    }
  }, [normalizeText]);

  const build = useCallback((reason = "ended", extra = {}) => {
    const turns = Array.isArray(turnsRef.current)
      ? turnsRef.current.filter((turn) => normalizeText(turn?.content))
      : [];

    const userTurns = turns.filter((turn) => turn.role === "user");
    const assistantTurns = turns.filter((turn) => turn.role === "assistant");

    const userText = normalizeText(
      userTurns.length
        ? userTurns.map((turn) => turn.content).join("\n\n")
        : (typeof getUserTextFallback === "function" ? getUserTextFallback() : "")
    );

    const assistantText = normalizeText(
      assistantTurns.length
        ? assistantTurns.map((turn) => turn.content).join("\n\n")
        : (typeof getAssistantTextFallback === "function" ? getAssistantTextFallback() : "")
    );

    const sessionId = extra?.sessionId
      || (typeof getSessionId === "function" ? getSessionId() : null)
      || null;

    return {
      id: `rt_summary_${Date.now()}`,
      reason,
      sessionId,
      endedAt: Math.floor(Date.now() / 1000),
      userText,
      assistantText,
      turns,
      source: extra?.source || "frontend_realtime_events",
    };
  }, [getAssistantTextFallback, getSessionId, getUserTextFallback, normalizeText]);

  const publish = useCallback((reason = "ended", extra = {}) => {
    try {
      const builtSummary = build(reason, extra);
      const hasContent = Boolean(
        normalizeText(builtSummary.userText)
        || normalizeText(builtSummary.assistantText)
        || (Array.isArray(builtSummary.turns) && builtSummary.turns.length > 0)
      );

      if (!hasContent && !extra?.forceOpen) {
        safeLog("ao66r_hf4:transcript_summary_empty", {
          reason,
          sessionId: builtSummary.sessionId || null,
          marker: "AO64D_HF1_SUMMARY_HOOK",
        });
        return false;
      }

      if (!hasContent && extra?.forceOpen) {
        safeLog("ao66r_hf4:transcript_summary_forced_empty", {
          reason,
          sessionId: builtSummary.sessionId || null,
          marker: "AO64D_HF1_SUMMARY_HOOK",
        });
      }

      if (inlineToChat && typeof appendSummaryToChat === "function") {
        try { appendSummaryToChat(builtSummary, reason); } catch {}
      }

      setSummary(builtSummary);
      setSummaryOpen(Boolean(extra?.forceOpen && !modalSuppressed));

      safeLog("ao66a:transcript_summary_published", {
        reason,
        sessionId: builtSummary.sessionId || null,
        turns: builtSummary.turns?.length || 0,
        hasUser: Boolean(builtSummary.userText),
        hasAssistant: Boolean(builtSummary.assistantText),
        inlinedToChat: Boolean(inlineToChat),
        modalSuppressed: Boolean(modalSuppressed),
        marker: "AO64D_HF1_SUMMARY_HOOK",
      });

      return true;
    } catch (err) {
      safeLog("ao66a:transcript_summary_failed", {
        reason,
        message: err?.message || null,
        marker: "AO64D_HF1_SUMMARY_HOOK",
      });
      return false;
    }
  }, [appendSummaryToChat, build, inlineToChat, modalSuppressed, normalizeText, safeLog]);

  const close = useCallback(() => {
    try { setSummaryOpen(false); } catch {}
  }, []);

  return {
    summary,
    summaryOpen,
    setSummaryOpen,
    turnsRef,
    normalizeText,
    reset,
    appendTurn,
    build,
    publish,
    close,
  };
}

export default useRealtimeTranscriptSummary;
