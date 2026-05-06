# EFATA 777 V7 COMPLETE
# Consolidated package for governed capability answers + analytical readonly + registry alignment + realtime self-heal hardening.

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Optional


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _clean_text(value: Optional[str]) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    lowered = text.lower()
    lowered = lowered.replace("’", "'").replace("“", '"').replace("”", '"')
    return lowered.strip()


def _slug(value: Optional[str]) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    raw = raw.replace("/", "_").replace("-", "_").replace(" ", "_")
    raw = re.sub(r"[^a-z0-9_:.]+", "", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class FinalEvent:
    session_id: str
    source: str
    event_type: str
    text: str
    clean_text: str
    text_hash: str
    created_at: float
    partition_key: str
    speaker_id: str = ""
    agent_name: str = ""
    message_id: str = ""
    channel: str = ""
    final_guard_key: str = ""


class RealtimeSelfHeal:
    def __init__(
        self,
        *,
        ttl_seconds: int = 20,
        duplicate_window_seconds: float = 4.0,
        similarity_threshold: float = 0.90,
        canonical_source: str = "text",
    ) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self.duplicate_window_seconds = float(duplicate_window_seconds)
        self.similarity_threshold = float(similarity_threshold)
        self.canonical_source = canonical_source
        self._lock = threading.Lock()
        self._last_final_by_partition: Dict[str, FinalEvent] = {}

    def _prune(self, now_value: float) -> None:
        expired = [
            partition_key
            for partition_key, evt in self._last_final_by_partition.items()
            if (now_value - evt.created_at) > self.ttl_seconds
        ]
        for partition_key in expired:
            self._last_final_by_partition.pop(partition_key, None)

    def _build_partition_key(
        self,
        *,
        session_id: str,
        speaker_id: str,
        agent_name: str,
        message_id: str,
        channel: str,
        final_guard_key: str,
    ) -> str:
        session = _slug(session_id)
        explicit_key = _slug(final_guard_key)
        if explicit_key:
            return f"{session}::guard::{explicit_key}"
        msg = _slug(message_id)
        if msg:
            return f"{session}::message::{msg}"
        speaker = _slug(speaker_id)
        agent = _slug(agent_name)
        ch = _slug(channel) or "default"
        if speaker:
            return f"{session}::speaker::{speaker}::channel::{ch}"
        if agent:
            return f"{session}::agent::{agent}::channel::{ch}"
        return f"{session}::shared::channel::{ch}"

    def analyze(
        self,
        *,
        session_id: str,
        text: str,
        source: str,
        event_type: str,
        now_value: Optional[float] = None,
        speaker_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        message_id: Optional[str] = None,
        channel: Optional[str] = None,
        final_guard_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        now_ts = float(now_value or time.time())
        clean_text = _clean_text(text)
        normalized_session_id = (session_id or "").strip()
        normalized_speaker_id = _slug(speaker_id)
        normalized_agent_name = _slug(agent_name)
        normalized_message_id = _slug(message_id)
        normalized_channel = _slug(channel) or ""
        normalized_guard_key = _slug(final_guard_key)

        if not normalized_session_id and not normalized_message_id and not normalized_guard_key:
            return {"commit": True, "reason": "missing_session_identity", "canonical_source": self.canonical_source}

        if not clean_text:
            return {"commit": False, "reason": "empty_text", "canonical_source": self.canonical_source}

        partition_key = self._build_partition_key(
            session_id=normalized_session_id or "unknown",
            speaker_id=normalized_speaker_id,
            agent_name=normalized_agent_name,
            message_id=normalized_message_id,
            channel=normalized_channel,
            final_guard_key=normalized_guard_key,
        )

        incoming = FinalEvent(
            session_id=normalized_session_id or "unknown",
            source=(source or "").strip().lower() or "unknown",
            event_type=(event_type or "").strip().lower() or "unknown",
            text=text,
            clean_text=clean_text,
            text_hash=_text_hash(clean_text),
            created_at=now_ts,
            partition_key=partition_key,
            speaker_id=normalized_speaker_id,
            agent_name=normalized_agent_name,
            message_id=normalized_message_id,
            channel=normalized_channel,
            final_guard_key=normalized_guard_key,
        )

        with self._lock:
            self._prune(now_ts)
            previous = self._last_final_by_partition.get(partition_key)

            if previous is None:
                self._last_final_by_partition[partition_key] = incoming
                return {
                    "commit": True,
                    "reason": "first_final_for_partition",
                    "canonical_source": self.canonical_source,
                    "session_id": incoming.session_id,
                    "partition_key": partition_key,
                    "source": incoming.source,
                    "event_type": incoming.event_type,
                    "speaker_id": incoming.speaker_id,
                    "agent_name": incoming.agent_name,
                    "message_id": incoming.message_id,
                    "channel": incoming.channel,
                }

            delta = now_ts - previous.created_at
            similarity = _similarity(previous.clean_text, incoming.clean_text)
            same_hash = previous.text_hash == incoming.text_hash

            if delta <= self.duplicate_window_seconds and (same_hash or similarity >= self.similarity_threshold):
                if previous.source == self.canonical_source and incoming.source != self.canonical_source:
                    return {
                        "commit": False,
                        "reason": "duplicate_suppressed_canonical_already_committed",
                        "session_id": incoming.session_id,
                        "partition_key": partition_key,
                        "existing_source": previous.source,
                        "incoming_source": incoming.source,
                        "delta_seconds": round(delta, 3),
                        "similarity": round(similarity, 4),
                        "speaker_id": incoming.speaker_id,
                        "agent_name": incoming.agent_name,
                        "message_id": incoming.message_id,
                        "channel": incoming.channel,
                    }

                if incoming.source == self.canonical_source and previous.source != self.canonical_source:
                    self._last_final_by_partition[partition_key] = incoming
                    return {
                        "commit": False,
                        "reason": "duplicate_suppressed_canonical_replaces_audio",
                        "session_id": incoming.session_id,
                        "partition_key": partition_key,
                        "existing_source": previous.source,
                        "incoming_source": incoming.source,
                        "delta_seconds": round(delta, 3),
                        "similarity": round(similarity, 4),
                        "speaker_id": incoming.speaker_id,
                        "agent_name": incoming.agent_name,
                        "message_id": incoming.message_id,
                        "channel": incoming.channel,
                    }

                return {
                    "commit": False,
                    "reason": "duplicate_suppressed_same_partition",
                    "session_id": incoming.session_id,
                    "partition_key": partition_key,
                    "existing_source": previous.source,
                    "incoming_source": incoming.source,
                    "delta_seconds": round(delta, 3),
                    "similarity": round(similarity, 4),
                    "speaker_id": incoming.speaker_id,
                    "agent_name": incoming.agent_name,
                    "message_id": incoming.message_id,
                    "channel": incoming.channel,
                }

            self._last_final_by_partition[partition_key] = incoming
            return {
                "commit": True,
                "reason": "new_distinct_final",
                "session_id": incoming.session_id,
                "partition_key": partition_key,
                "source": incoming.source,
                "event_type": incoming.event_type,
                "delta_seconds_from_previous": round(delta, 3),
                "similarity": round(similarity, 4),
                "speaker_id": incoming.speaker_id,
                "agent_name": incoming.agent_name,
                "message_id": incoming.message_id,
                "channel": incoming.channel,
            }


_REALTIME_SELF_HEAL_ENABLED = _env_flag("REALTIME_SELF_HEAL_ENABLED", True)

realtime_self_heal = RealtimeSelfHeal(
    ttl_seconds=int(os.getenv("REALTIME_SELF_HEAL_TTL_SECONDS", "20")),
    duplicate_window_seconds=float(os.getenv("REALTIME_SELF_HEAL_WINDOW_SECONDS", "4.0")),
    similarity_threshold=float(os.getenv("REALTIME_SELF_HEAL_SIMILARITY", "0.90")),
    canonical_source=os.getenv("REALTIME_SELF_HEAL_CANONICAL_SOURCE", "text").strip().lower() or "text",
)


def should_commit_realtime_final(
    *,
    session_id: str,
    text: str,
    source: str,
    event_type: str,
    speaker_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    message_id: Optional[str] = None,
    channel: Optional[str] = None,
    final_guard_key: Optional[str] = None,
) -> Dict[str, Any]:
    if not _REALTIME_SELF_HEAL_ENABLED:
        return {"commit": True, "reason": "self_heal_disabled"}
    return realtime_self_heal.analyze(
        session_id=session_id,
        text=text,
        source=source,
        event_type=event_type,
        speaker_id=speaker_id,
        agent_name=agent_name,
        message_id=message_id,
        channel=channel,
        final_guard_key=final_guard_key,
    )


def build_realtime_self_heal_incident(
    *,
    session_id: str,
    text: str,
    source: str,
    event_type: str,
    speaker_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    message_id: Optional[str] = None,
    channel: Optional[str] = None,
    final_guard_key: Optional[str] = None,
) -> Dict[str, Any]:
    decision = should_commit_realtime_final(
        session_id=session_id,
        text=text,
        source=source,
        event_type=event_type,
        speaker_id=speaker_id,
        agent_name=agent_name,
        message_id=message_id,
        channel=channel,
        final_guard_key=final_guard_key,
    )
    return {
        "kind": "realtime_duplicate_final_guard",
        "session_id": session_id,
        "partition_key": decision.get("partition_key"),
        "source": source,
        "event_type": event_type,
        "speaker_id": speaker_id,
        "agent_name": agent_name,
        "message_id": message_id,
        "channel": channel,
        "final_guard_key": final_guard_key,
        "decision": decision,
        "text_preview": (text or "")[:200],
        "created_at": int(time.time()),
    }
