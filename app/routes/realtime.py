    @router.post("/api/realtime/end")
    def realtime_end(
        body: RealtimeEndReq,
        x_org_slug: Optional[str] = Header(default=None),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        org = _resolve_org(user, x_org_slug)
        uid = user.get("sub")

        rs = db.execute(
            select(RealtimeSession).where(
                RealtimeSession.id == body.session_id,
                RealtimeSession.org_slug == org,
            )
        ).scalar_one_or_none()

        if not rs:
            raise HTTPException(status_code=404, detail="Realtime session not found")

        if user.get("role") != "admin":
            _require_thread_member(db, org, rs.thread_id, uid)

        # AO-01 HF6R12 — REALTIME PRE-ACTIVATION END GATE
        # If the browser/PWA closes the Realtime session during warmup,
        # before any real activation evidence exists, persist a zero-duration
        # row so quota/cooldown logic ignores it.

        started_at_norm = _rt_epoch_seconds(getattr(rs, "started_at", None))
        requested_end_at_norm = (
            _rt_epoch_seconds(getattr(body, "ended_at", None))
            or _rt_epoch_seconds(now_ts())
        )

        try:
            activation_event_id = db.execute(
                select(RealtimeEvent.id)
                .where(
                    RealtimeEvent.org_slug == org,
                    RealtimeEvent.session_id == rs.id,
                    RealtimeEvent.event_type.in_(
                        [
                            "transcript.final",
                            "response.final",
                            "telemetry.session_activated",
                            "telemetry.assistant_audio_started",
                            "telemetry.datachannel_open",
                            "telemetry.greeting_sent",
                        ]
                    ),
                )
                .limit(1)
            ).scalar_one_or_none()
            has_activation_evidence = bool(activation_event_id)
        except Exception:
            logger.exception(
                "AO01_HF6R12_REALTIME_ACTIVATION_EVIDENCE_CHECK_FAILED session_id=%s",
                rs.id,
            )
            has_activation_evidence = False

        try:
            incoming_meta = body.meta or {}
        except Exception:
            incoming_meta = {}

        try:
            cur = json.loads(rs.meta) if rs.meta else {}
            if not isinstance(cur, dict):
                cur = {}
        except Exception:
            cur = {}

        if isinstance(incoming_meta, dict):
            cur.update(incoming_meta)

        session_age_seconds = (
            max(0, requested_end_at_norm - started_at_norm)
            if started_at_norm
            else 0
        )

        if (
            not has_activation_evidence
            and started_at_norm > 0
            and session_age_seconds <= 20
        ):
            rs.ended_at = started_at_norm
            cur.update(
                {
                    "ao01_hf6r12": "pre_activation_end_gate",
                    "activation_state": "failed_warmup",
                    "activated": False,
                    "cooldown_billable": False,
                    "quota_billable": False,
                    "forced_zero_duration": True,
                    "requested_end_at": requested_end_at_norm,
                    "session_age_seconds": session_age_seconds,
                    "end_gate_reason": "no_activation_evidence_before_early_end",
                }
            )

            try:
                logger.warning(
                    "AO01_HF6R12_REALTIME_PRE_ACTIVATION_END_ZEROED session_id=%s thread_id=%s age=%s started_at=%s requested_end_at=%s",
                    rs.id,
                    rs.thread_id,
                    session_age_seconds,
                    started_at_norm,
                    requested_end_at_norm,
                )
            except Exception:
                pass
        else:
            rs.ended_at = requested_end_at_norm
            cur.update(
                {
                    "ao01_hf6r12": "normal_end",
                    "activation_state": "activated_or_long_session",
                    "activated": bool(has_activation_evidence),
                    "cooldown_billable": True,
                    "quota_billable": True,
                    "session_age_seconds": session_age_seconds,
                }
            )

        rs.meta = json.dumps(cur, ensure_ascii=False)

        _audit_realtime_safe(
            db,
            org,
            uid,
            action="realtime.session.end",
            meta={
                "session_id": rs.id,
                "thread_id": rs.thread_id,
                "ao01_hf6r12": True,
                "activation_evidence": bool(has_activation_evidence),
                "session_age_seconds": session_age_seconds,
                "ended_at_persisted": rs.ended_at,
            },
        )

        db.add(rs)
        db.commit()

        return {
            "ok": True,
            "session_id": rs.id,
            "ended_at": rs.ended_at,
            "activation_evidence": bool(has_activation_evidence),
            "session_age_seconds": session_age_seconds,
            "ao01_hf6r12": True,
        }
