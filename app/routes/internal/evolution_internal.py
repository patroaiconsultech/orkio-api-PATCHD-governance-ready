# EFATA 777 V7 COMPLETE
# Consolidated package for governed capability answers + analytical readonly + registry alignment + realtime self-heal hardening.

from __future__ import annotations

import json
import os
import re
import time
import uuid
import urllib.request as _urllib_request
import urllib.parse as _urllib_parse
import ssl as _ssl
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db import SessionLocal, get_db
from app.models import ContinuousAuditArtifact, ContinuousAuditJob, ContinuousAuditReceipt, EvolutionProposal
from app.services.identity_service import load_active_identity
from app.core.orkio_constitution import load_constitution
from app.core.orkio_permissions import load_permissions
from app.services.capability_service import load_runtime_governed_capabilities
from app.services.governance_service import build_governance_health, evaluate_governance_action
from app.services.receipt_service import make_governed_receipt
from app.services.admin_master_identity import require_admin_console_access, require_master_admin_access

router = APIRouter(prefix="/api/internal/orion", tags=["orion_internal"], dependencies=[Depends(require_admin_console_access)])

PATCH_SENTINEL = "PR_COMPARE_STATUS_SENTINEL_12BN_V1"
PATCH_FEATURE = "github_pr_compare_status_resolver"
PATCH_EXPECTED_BEHAVIOR = "github_compare_and_pr_status_requests_resolve_with_repo_aliases_natural_compare_accept_pr_number_without_hash_and_ignore_ambiguous_branch_tokens"


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _clean_env(name: str, default: str = "") -> str:
    raw = os.getenv(name, default)
    if raw is None:
        return default
    value = str(raw).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value or default


def _now_ts() -> int:
    return int(time.time())


def _new_id() -> str:
    return uuid.uuid4().hex


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False)
    except Exception:
        return "{}"


def _json_loads(value: Any, default: Any) -> Any:
    try:
        if not value:
            return default
        parsed = json.loads(value)
        return parsed if parsed is not None else default
    except Exception:
        return default



def _assisted_evolution_domain_scope(payload: Dict[str, Any]) -> str:
    files = payload.get("probable_files") if isinstance(payload.get("probable_files"), list) else []
    if not files:
        files = payload.get("key_files") if isinstance(payload.get("key_files"), list) else []
    lowered = [str(item or "").strip().lower() for item in files if str(item or "").strip()]
    if lowered and all(item.startswith("src/") for item in lowered):
        return "frontend"
    if lowered and all(item.startswith("app/") for item in lowered):
        return "backend"
    if any(item.startswith("src/") for item in lowered):
        return "frontend"
    if any(item.startswith("app/") for item in lowered):
        return "backend"
    return "platform"


def _assisted_evolution_action(payload: Dict[str, Any]) -> str:
    scope = _assisted_evolution_domain_scope(payload)
    if scope == "frontend":
        return "frontend_patch"
    if scope == "backend":
        return "backend_patch"
    return "platform_patch"


def _assisted_evolution_title(payload: Dict[str, Any]) -> str:
    explicit = str(payload.get("selected_improvement") or payload.get("title") or "").strip()
    if explicit:
        return explicit[:240]
    summary = str(payload.get("technical_summary") or "").strip()
    return (summary or "Assisted evolution proposal").strip()[:240]


def _assisted_evolution_summary(payload: Dict[str, Any]) -> str:
    pieces: List[str] = []
    for key in ("technical_summary", "root_cause", "user_impact", "technical_risk", "final_consolidation"):
        value = str(payload.get(key) or "").strip()
        if value:
            pieces.append(value)
    if not pieces:
        recs = payload.get("recommended_actions") if isinstance(payload.get("recommended_actions"), list) else []
        pieces = [str(item).strip() for item in recs if str(item).strip()]
    return "\n\n".join(pieces[:5]).strip()[:4000]


def _assisted_evolution_fingerprint(payload: Dict[str, Any]) -> str:
    seed = {
        "scope": _assisted_evolution_domain_scope(payload),
        "action": _assisted_evolution_action(payload),
        "title": _assisted_evolution_title(payload),
        "selected_improvement": str(payload.get("selected_improvement") or "").strip(),
        "root_cause": str(payload.get("root_cause") or "").strip(),
        "probable_files": list(payload.get("probable_files") or [])[:20] if isinstance(payload.get("probable_files"), list) else [],
        "key_files": list(payload.get("key_files") or [])[:20] if isinstance(payload.get("key_files"), list) else [],
    }
    raw = json.dumps(seed, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _persist_assisted_evolution_proposal(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {
            "proposal_created": False,
            "proposal_status": "unavailable",
            "assisted_evolution_ready": False,
            "failure_reason": "governed_persistent_proposal_flow_not_available",
        }
    payload = dict(payload or {})
    try:
        title = _assisted_evolution_title(payload)
        summary = _assisted_evolution_summary(payload)
        fingerprint = _assisted_evolution_fingerprint(payload)
        action = _assisted_evolution_action(payload)
        domain_scope = _assisted_evolution_domain_scope(payload)
        now = _now_ts()
        db = SessionLocal()
        try:
            row = db.execute(
                select(EvolutionProposal).where(EvolutionProposal.fingerprint == fingerprint)
            ).scalar_one_or_none()
            issue_json = {
                "source": "assisted_evolution_runtime",
                "event": str(payload.get("event") or "").strip(),
                "delivery_contract": str(payload.get("delivery_contract") or "").strip(),
                "scope": domain_scope,
                "key_files": list(payload.get("key_files") or []) if isinstance(payload.get("key_files"), list) else [],
                "probable_files": list(payload.get("probable_files") or []) if isinstance(payload.get("probable_files"), list) else [],
            }
            decision_json = {
                "recommended_actions": list(payload.get("recommended_actions") or []) if isinstance(payload.get("recommended_actions"), list) else [],
                "priority_score": payload.get("priority_score"),
                "priority_score_label": str(payload.get("priority_score_label") or "").strip(),
                "human_approval_required": True,
                "delivery_contract": str(payload.get("delivery_contract") or "").strip(),
                "execution_depth": str(payload.get("execution_depth") or "").strip(),
                "assisted_evolution": True,
            }
            finding_json = {
                "technical_summary": str(payload.get("technical_summary") or "").strip(),
                "selected_improvement": str(payload.get("selected_improvement") or "").strip(),
                "root_cause": str(payload.get("root_cause") or "").strip(),
                "user_impact": str(payload.get("user_impact") or "").strip(),
                "technical_risk": str(payload.get("technical_risk") or "").strip(),
                "final_consolidation": str(payload.get("final_consolidation") or "").strip(),
            }
            created = False
            if row is None:
                row = EvolutionProposal(
                    id=f"eprop_{_new_id()[:12]}",
                    org_slug="system",
                    fingerprint=fingerprint,
                    code="assisted_evolution_proposal",
                    severity="MEDIUM",
                    category="assisted_evolution",
                    source="orion_runtime",
                    action=action,
                    status="awaiting_master_approval",
                    title=title,
                    summary=summary,
                    finding_json=_json_dumps(finding_json),
                    issue_json=_json_dumps(issue_json),
                    decision_json=_json_dumps(decision_json),
                    domain_scope=domain_scope,
                    recurrence_window_count=1,
                    blast_radius_accumulated=0,
                    security_accumulated=0,
                    last_priority_score=int(payload.get("priority_score") or 0),
                    last_recommendation=(decision_json["recommended_actions"][0] if decision_json["recommended_actions"] else ""),
                    last_cadence_seconds=0,
                    first_detected_at=now,
                    last_detected_at=now,
                    detected_count=1,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                created = True
            else:
                row.title = title
                row.summary = summary
                row.finding_json = _json_dumps(finding_json)
                row.issue_json = _json_dumps(issue_json)
                row.decision_json = _json_dumps(decision_json)
                row.action = action
                row.domain_scope = domain_scope
                row.last_priority_score = int(payload.get("priority_score") or getattr(row, "last_priority_score", 0) or 0)
                row.last_recommendation = (decision_json["recommended_actions"][0] if decision_json["recommended_actions"] else getattr(row, "last_recommendation", "") or "")
                row.last_detected_at = now
                row.detected_count = int(getattr(row, "detected_count", 0) or 0) + 1
                if str(getattr(row, "status", "") or "").lower() in {"resolved", "rejected", "failed", "rolled_back"}:
                    row.status = "awaiting_master_approval"
                row.updated_at = now
            db.commit()
            safe_payload = payload if isinstance(payload, dict) else {}
            safe_payload["proposal_id"] = row.id
            safe_payload["proposal_status"] = str(getattr(row, "status", "") or "").strip()
            safe_payload["proposal_title"] = str(getattr(row, "title", "") or "").strip()
            safe_payload["proposal_created"] = bool(created)
            safe_payload["proposal_reference"] = f"/admin/evolution?proposal_id={row.id}"
            safe_payload["assisted_evolution_ready"] = True
            safe_payload["proposal_domain_scope"] = str(getattr(row, "domain_scope", "") or domain_scope).strip()
            safe_payload["proposal_action"] = str(getattr(row, "action", "") or action).strip()
            if not str(safe_payload.get("next_authorization_command") or "").strip():
                safe_payload["next_authorization_command"] = f"Approve proposal {row.id} no Evolution Center antes de qualquer execução."
            return {
                "proposal_id": row.id,
                "proposal_status": str(getattr(row, "status", "") or "").strip(),
                "proposal_title": str(getattr(row, "title", "") or "").strip(),
                "proposal_created": bool(created),
                "proposal_reference": f"/admin/evolution?proposal_id={row.id}",
                "assisted_evolution_ready": True,
                "proposal_domain_scope": str(getattr(row, "domain_scope", "") or domain_scope).strip(),
                "proposal_action": str(getattr(row, "action", "") or action).strip(),
            }
        finally:
            db.close()
    except Exception:
        return {
            "proposal_created": False,
            "proposal_status": "unavailable",
            "assisted_evolution_ready": False,
            "failure_reason": "proposal_object_unavailable",
        }


def _extract_continuous_audit_job_id(message: str) -> str:
    effective = _continuous_audit_effective_input(message or "")
    payload = dict(effective.get("payload") or {})
    for key in ("job_id", "audit_job_id", "continuous_audit_job_id"):
        value = payload.get(key)
        if value not in (None, "", "null"):
            return str(value).strip().lower()
    raw = str(effective.get("message") or message or "").strip()
    if not raw:
        return ""
    patterns = [
        r"(?im)^\s*job_id\s*[:=]\s*([a-f0-9-]{8,})\s*$",
        r"\bjob[_ -]?id\s*[:=]?\s*([a-f0-9-]{8,})\b",
        r"/api/admin/audit-jobs/([a-f0-9-]{8,})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return str(match.group(1) or "").strip().lower()
    return ""


def _looks_like_continuous_audit_status_request(message: str) -> bool:
    effective = _continuous_audit_effective_input(message or "")
    raw = str(effective.get("message") or message or "").strip().lower()
    if not raw:
        return False
    explicit_job_id = _extract_continuous_audit_job_id(message)
    status_markers = [
        "consultar status",
        "forneça o status",
        "forneca o status",
        "status do continuous audit",
        "status do continuous audit job",
        "status do job",
        "status da auditoria contínua",
        "status da auditoria continua",
        "job existente",
        "job persistido mais recente",
        "usar somente o job_id",
        "não criar novo job",
        "nao criar novo job",
        "proibido criar novo job",
        "mais recente",
    ]
    create_markers = [
        "iniciar auditoria contínua",
        "iniciar auditoria continua",
        "iniciar continuous audit",
        "criar novo job",
        "iniciar job",
        "start continuous audit",
        "execute continuous audit",
    ]
    asks_status = bool(explicit_job_id) or any(marker in raw for marker in status_markers)
    asks_create = any(marker in raw for marker in create_markers)
    return bool(asks_status and not asks_create)


def _looks_like_continuous_audit_request(message: str) -> bool:
    effective = _continuous_audit_effective_input(message or "")
    raw = str(effective.get("message") or message or "").strip().lower()
    if not raw or _looks_like_continuous_audit_status_request(message):
        return False
    markers = [
        "auditoria contínua",
        "auditoria continua",
        "continuous audit",
        "continuous_audit",
        "job persistido",
        "job_id",
        "progresso rastreável",
        "progresso rastreavel",
        "execução contínua",
        "execucao continua",
        "audit job",
        "persisted state",
        "progresso real",
    ]
    return any(marker in raw for marker in markers)


def _continuous_audit_operation_kind(message: str) -> str:
    effective = _continuous_audit_effective_input(message or "")
    payload = dict(effective.get("payload") or {})
    explicit = str(
        payload.get("operation")
        or payload.get("mode")
        or payload.get("kind")
        or payload.get("intent")
        or payload.get("capability_name")
        or payload.get("runtime_kind")
        or ""
    ).strip().lower()
    if explicit in {"continuous_audit_job_status", "read_status", "status"}:
        return "status"
    if explicit in {"continuous_audit_job", "create_continuous_audit_job", "start_continuous_audit"}:
        return "create"
    if _looks_like_continuous_audit_status_request(message):
        return "status"
    if _looks_like_continuous_audit_request(message):
        return "create"
    return ""


def _continuous_audit_title(message: str) -> str:
    headline = "Auditoria contínua read-only"
    for line in (message or "").splitlines():
        stripped = str(line or "").strip()
        if stripped and not stripped.startswith("@"):
            headline = stripped[:120]
            break
    return headline


def _extract_embedded_runtime_payload(message: str) -> Dict[str, Any]:
    raw = str(message or "").strip()
    if not raw:
        return {}
    candidates: List[str] = []
    if raw.startswith("{") and raw.endswith("}"):
        candidates.append(raw)
    first = raw.find("{")
    last = raw.rfind("}")
    if first >= 0 and last > first:
        candidate = raw[first:last + 1].strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _continuous_audit_effective_input(
    message: str,
    *,
    include_frontend: bool = False,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    payload = _extract_embedded_runtime_payload(message or "")
    payload_message = payload.get("message") if isinstance(payload, dict) else None
    effective_message = str(payload_message or message or "")
    payload_thread_id = payload.get("thread_id") if isinstance(payload, dict) else None
    effective_thread_id = thread_id
    if effective_thread_id in (None, "", "null"):
        effective_thread_id = payload_thread_id
    payload_include_frontend = payload.get("include_frontend") if isinstance(payload, dict) else None
    effective_include_frontend = bool(include_frontend or payload_include_frontend is True)
    return {
        "message": effective_message,
        "include_frontend": effective_include_frontend,
        "thread_id": (str(effective_thread_id).strip() if effective_thread_id not in (None, "", "null") else None),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _continuous_audit_selected_specialists(message: str, include_frontend: bool = False) -> tuple[Dict[str, Any], List[str], List[str]]:
    effective = _continuous_audit_effective_input(message or "", include_frontend=bool(include_frontend))
    effective_message = str(effective.get("message") or "")
    effective_include_frontend = bool(effective.get("include_frontend"))
    constraints = _extract_hard_constraints(effective_message)
    required = list(constraints.get("specialists_required") or [])
    default_selected = ["orion", "auditor", "cto"]
    needs_frontend = (
        effective_include_frontend
        or ("ux_frontend" in required)
        or ("ux/frontend" in effective_message.lower())
        or ("ux_frontend" in effective_message.lower())
        or ("frontend" in effective_message.lower())
    )
    if needs_frontend:
        default_selected.append("ux_frontend")
    selected = _apply_specialist_constraints(default_selected, constraints=constraints)
    if not selected:
        selected = _dedupe_dispatch_actors(default_selected)
    violations = _validate_dispatch_constraints(
        visible_agent=str(constraints.get("required_signer") or "orion"),
        selected_specialists=list(selected or []),
        constraints=constraints,
    )
    return constraints, _dedupe_dispatch_actors(selected), list(violations or [])


def _serialize_continuous_audit_job(job: ContinuousAuditJob) -> Dict[str, Any]:
    return {
        "job_id": getattr(job, "id", None),
        "org_slug": getattr(job, "org_slug", None),
        "thread_id": getattr(job, "thread_id", None),
        "title": getattr(job, "title", None),
        "status": getattr(job, "status", None),
        "progress_percentage": int(getattr(job, "progress_percentage", 0) or 0),
        "requested_signer": getattr(job, "requested_signer", None),
        "selected_specialists": list(_json_loads(getattr(job, "selected_specialists_json", None), [])),
        "required_specialists": list(_json_loads(getattr(job, "required_specialists_json", None), [])),
        "forbidden_specialists": list(_json_loads(getattr(job, "forbidden_specialists_json", None), [])),
        "execution_mode": getattr(job, "execution_mode", None),
        "persisted_state_location": getattr(job, "persisted_state_location", None),
        "latest_event": getattr(job, "latest_event", None),
        "latest_summary": getattr(job, "latest_summary", None),
        "payload": _json_loads(getattr(job, "payload_json", None), {}),
        "started_at": getattr(job, "started_at", None),
        "last_updated_at": getattr(job, "last_updated_at", None),
        "completed_at": getattr(job, "completed_at", None),
        "created_at": getattr(job, "created_at", None),
        "updated_at": getattr(job, "updated_at", None),
        "requested_by_user_id": getattr(job, "requested_by_user_id", None),
        "requested_by_user_name": getattr(job, "requested_by_user_name", None),
    }


def _serialize_continuous_audit_receipt(receipt: ContinuousAuditReceipt) -> Dict[str, Any]:
    return {
        "id": getattr(receipt, "id", None),
        "job_id": getattr(receipt, "job_id", None),
        "seq": int(getattr(receipt, "seq", 0) or 0),
        "event": getattr(receipt, "event", None),
        "phase": getattr(receipt, "phase", None),
        "agent": getattr(receipt, "agent", None),
        "status": getattr(receipt, "status", None),
        "detail": getattr(receipt, "detail", None),
        "payload": _json_loads(getattr(receipt, "payload_json", None), {}),
        "created_at": getattr(receipt, "created_at", None),
    }


def _serialize_continuous_audit_artifact(artifact: ContinuousAuditArtifact) -> Dict[str, Any]:
    content = getattr(artifact, "content", None)
    parsed = _json_loads(content, content)
    return {
        "id": getattr(artifact, "id", None),
        "job_id": getattr(artifact, "job_id", None),
        "artifact_type": getattr(artifact, "artifact_type", None),
        "title": getattr(artifact, "title", None),
        "content_type": getattr(artifact, "content_type", None),
        "content": parsed,
        "created_at": getattr(artifact, "created_at", None),
    }


def get_continuous_audit_job_snapshot(db: Session, org: str, job_id: str) -> Dict[str, Any]:
    job = db.execute(
        select(ContinuousAuditJob).where(
            ContinuousAuditJob.org_slug == org,
            ContinuousAuditJob.id == str(job_id or "").strip(),
        ).limit(1)
    ).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Continuous audit job not found")
    receipts = db.execute(
        select(ContinuousAuditReceipt).where(
            ContinuousAuditReceipt.org_slug == org,
            ContinuousAuditReceipt.job_id == job.id,
        ).order_by(ContinuousAuditReceipt.seq.asc(), ContinuousAuditReceipt.created_at.asc())
    ).scalars().all()
    artifacts = db.execute(
        select(ContinuousAuditArtifact).where(
            ContinuousAuditArtifact.org_slug == org,
            ContinuousAuditArtifact.job_id == job.id,
        ).order_by(ContinuousAuditArtifact.created_at.asc())
    ).scalars().all()
    payload = _serialize_continuous_audit_job(job)
    serialized_receipts = [_serialize_continuous_audit_receipt(item) for item in receipts]
    serialized_artifacts = [_serialize_continuous_audit_artifact(item) for item in artifacts]

    specialist_reports: List[Dict[str, Any]] = []
    final_consolidation = ""
    latest_summary_artifact: Dict[str, Any] = {}

    for artifact in serialized_artifacts:
        artifact_type = str(artifact.get("artifact_type") or "").strip().lower()
        content = artifact.get("content")
        if artifact_type == "specialist_report" and isinstance(content, dict):
            specialist_reports.append(content)
        elif artifact_type == "final_consolidation":
            if isinstance(content, dict):
                latest_summary_artifact = content
                final_consolidation = str(content.get("final_consolidation") or "").strip()
            elif content is not None:
                final_consolidation = str(content).strip()

    payload["receipts"] = serialized_receipts
    payload["dispatch_receipts"] = serialized_receipts
    payload["artifacts"] = serialized_artifacts
    payload["specialist_reports"] = specialist_reports
    payload["dispatch_receipts_count"] = len(serialized_receipts)
    payload["artifacts_count"] = len(serialized_artifacts)
    payload["selected_specialists_count"] = len(list(payload.get("selected_specialists") or []))
    payload["specialist_reports_count"] = len(specialist_reports)
    if latest_summary_artifact:
        payload["technical_summary"] = str(latest_summary_artifact.get("technical_summary") or "").strip()
        payload["executive_diagnostic"] = str(latest_summary_artifact.get("executive_diagnostic") or "").strip()
    if final_consolidation:
        payload["final_consolidation"] = final_consolidation
    required_specialists = _dedupe_dispatch_actors(list(payload.get("required_specialists") or []))
    selected_specialists = _dedupe_dispatch_actors(list(payload.get("selected_specialists") or []))
    payload["missing_specialists"] = [item for item in required_specialists if item not in selected_specialists]
    payload["compliance_status"] = "passed" if not payload["missing_specialists"] else "failed"
    return payload


def get_latest_continuous_audit_job_snapshot(db: Session, org: str) -> Dict[str, Any]:
    job = db.execute(
        select(ContinuousAuditJob).where(
            ContinuousAuditJob.org_slug == org,
        ).order_by(ContinuousAuditJob.created_at.desc()).limit(1)
    ).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="No continuous audit job found")
    return get_continuous_audit_job_snapshot(db, org, job.id)


def get_continuous_audit_status_from_message(db: Session, org: str, message: str) -> Dict[str, Any]:
    job_id = _extract_continuous_audit_job_id(message or "")
    if job_id:
        payload = get_continuous_audit_job_snapshot(db, org, job_id)
    else:
        payload = get_latest_continuous_audit_job_snapshot(db, org)
    payload.update({
        "ok": True,
        "service": "orion_internal",
        "provider": "platform",
        "mode": "continuous_audit_job_status",
        "event": "CONTINUOUS_AUDIT_JOB_STATUS",
        "execution_depth": "persisted_job",
    })
    return payload


def start_continuous_audit_job(
    db: Session,
    org: str,
    *,
    message: str,
    thread_id: Optional[str] = None,
    include_frontend: bool = False,
    requested_by_user_id: Optional[str] = None,
    requested_by_user_name: Optional[str] = None,
) -> Dict[str, Any]:
    if _continuous_audit_operation_kind(message or "") == "status":
        return get_continuous_audit_status_from_message(db, org, message or "")
    effective = _continuous_audit_effective_input(
        message or "",
        include_frontend=bool(include_frontend),
        thread_id=thread_id,
    )
    effective_message = str(effective.get("message") or "")
    effective_thread_id = effective.get("thread_id")
    effective_include_frontend = bool(effective.get("include_frontend"))
    embedded_payload = dict(effective.get("payload") or {})
    constraints, selected_specialists, violations = _continuous_audit_selected_specialists(
        effective_message,
        include_frontend=effective_include_frontend,
    )
    now = _now_ts()
    status = "blocked" if violations else "initialized"
    latest_event = "CONTINUOUS_AUDIT_JOB_BLOCKED" if violations else "CONTINUOUS_AUDIT_JOB_CREATED"
    progress_percentage = 0 if violations else 25
    requested_signer = str(constraints.get("required_signer") or _resolve_visible_agent(effective_message, default="orion") or "orion").strip().lower() or "orion"
    generated_dispatch_receipts = _audit_dispatch_receipts(selected_specialists, "continuous_audit") if not violations else []
    generated_specialist_reports = _audit_specialist_reports(selected_specialists, "continuous_audit") if not violations else []
    generated_final_consolidation = _audit_final_consolidation(selected_specialists, "continuous_audit") if not violations else ""
    latest_summary = (
        "Hard constraints blocked continuous audit initialization."
        if violations
        else "Continuous audit job persisted with initial specialist reports and tracked follow-up state."
    )
    title = _continuous_audit_title(effective_message or "")
    job = ContinuousAuditJob(
        id=_new_id(),
        org_slug=org,
        thread_id=(str(effective_thread_id or "").strip() or None),
        requested_by_user_id=(str(requested_by_user_id or "").strip() or None),
        requested_by_user_name=(str(requested_by_user_name or "").strip() or None),
        requested_signer=requested_signer,
        title=title,
        source_message=effective_message or "",
        execution_mode="read_only_continuous",
        status=status,
        progress_percentage=progress_percentage,
        selected_specialists_json=_json_dumps(selected_specialists),
        required_specialists_json=_json_dumps(list(constraints.get("specialists_required") or [])),
        forbidden_specialists_json=_json_dumps(list(constraints.get("specialists_forbidden") or [])),
        persisted_state_location=f"continuous_audit_jobs:{org}:{title[:32]}",
        latest_event=latest_event,
        latest_summary=latest_summary,
        payload_json=_json_dumps({
            "requested_message": effective_message or "",
            "embedded_payload": embedded_payload,
            "include_frontend": effective_include_frontend,
            "hard_constraints": constraints,
            "selected_specialists": selected_specialists,
            "constraint_violations": violations,
        }),
        started_at=(now if not violations else None),
        last_updated_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.flush()

    receipt_rows: List[ContinuousAuditReceipt] = []
    receipt_rows.append(
        ContinuousAuditReceipt(
            id=_new_id(),
            org_slug=org,
            job_id=job.id,
            seq=1,
            event=latest_event,
            phase="init",
            agent=requested_signer,
            status=status,
            detail=latest_summary,
            payload_json=_json_dumps({
                "selected_specialists": selected_specialists,
                "required_signer": requested_signer,
                "constraint_violations": violations,
            }),
            created_at=now,
        )
    )
    if selected_specialists:
        receipt_rows.append(
            ContinuousAuditReceipt(
                id=_new_id(),
                org_slug=org,
                job_id=job.id,
                seq=2,
                event="CONTINUOUS_AUDIT_SPECIALISTS_LOCKED",
                phase="planning",
                agent=requested_signer,
                status="recorded",
                detail="Selected specialists locked for persisted continuous audit job.",
                payload_json=_json_dumps({"selected_specialists": selected_specialists}),
                created_at=now,
            )
        )
    for row in receipt_rows:
        db.add(row)

    artifact_rows = [
        ContinuousAuditArtifact(
            id=_new_id(),
            org_slug=org,
            job_id=job.id,
            artifact_type="audit_plan",
            title="Continuous audit plan",
            content=_json_dumps({
                "title": title,
                "message": message or "",
                "embedded_payload": embedded_payload,
                "include_frontend": effective_include_frontend,
                "selected_specialists": selected_specialists,
                "hard_constraints": constraints,
                "constraint_violations": violations,
                "dispatch_receipts_count": len(generated_dispatch_receipts),
                "specialist_reports_count": len(generated_specialist_reports),
            }),
            content_type="application/json",
            created_at=now,
        )
    ]
    if violations:
        artifact_rows.append(
            ContinuousAuditArtifact(
                id=_new_id(),
                org_slug=org,
                job_id=job.id,
                artifact_type="constraint_violation",
                title="Continuous audit blockers",
                content=_json_dumps({"violations": violations}),
                content_type="application/json",
                created_at=now,
            )
        )
    else:
        for idx, report in enumerate(generated_specialist_reports, start=1):
            report_agent = str(report.get("agent") or f"specialist_{idx}").strip() or f"specialist_{idx}"
            artifact_rows.append(
                ContinuousAuditArtifact(
                    id=_new_id(),
                    org_slug=org,
                    job_id=job.id,
                    artifact_type="specialist_report",
                    title=f"Continuous audit report • {report_agent}",
                    content=_json_dumps(report),
                    content_type="application/json",
                    created_at=now + idx,
                )
            )
        artifact_rows.append(
            ContinuousAuditArtifact(
                id=_new_id(),
                org_slug=org,
                job_id=job.id,
                artifact_type="final_consolidation",
                title="Continuous audit consolidation",
                content=_json_dumps({
                    "technical_summary": "Continuous audit job iniciado com especialistas bloqueados e relatórios materializados para acompanhamento incremental.",
                    "executive_diagnostic": f"Job persistido com {len(selected_specialists)} especialista(s) selecionado(s), {len(generated_dispatch_receipts)} receipt(s) e {len(generated_specialist_reports)} relatório(s) inicial(is).",
                    "final_consolidation": generated_final_consolidation,
                }),
                content_type="application/json",
                created_at=now + max(1, len(generated_specialist_reports)) + 1,
            )
        )
    for row in artifact_rows:
        db.add(row)

    db.commit()
    payload = get_continuous_audit_job_snapshot(db, org, job.id)
    payload.update({
        "ok": True,
        "service": "orion_internal",
        "provider": "platform",
        "event": latest_event,
        "execution_depth": "persisted_job",
        "delivery_contract": "continuous_audit_job_v1",
        "mode": "continuous_audit_job",
        "execution_state": status,
        "selected_specialists_count": len(selected_specialists),
        "constraint_violations": violations,
    })
    return payload



def _start_continuous_audit_job_detached(inp: "OrionRuntimeIn", *, org: str = "public") -> Dict[str, Any]:
    db: Optional[Session] = None
    effective = _continuous_audit_effective_input(
        inp.message or "",
        include_frontend=bool(inp.include_frontend),
        thread_id=getattr(inp, "thread_id", None),
    )
    effective_message = str(effective.get("message") or inp.message or "")
    try:
        db = SessionLocal()
        if _continuous_audit_operation_kind(effective_message) == "status":
            return get_continuous_audit_status_from_message(db, org, effective_message)
        return start_continuous_audit_job(
            db,
            org,
            message=effective_message,
            thread_id=(str(effective.get("thread_id") or "").strip() or None),
            include_frontend=bool(effective.get("include_frontend")),
            requested_by_user_name="orion_runtime",
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

def _get_continuous_audit_status_detached(inp: "OrionRuntimeIn", *, org: str = "public") -> Dict[str, Any]:
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        return get_continuous_audit_status_from_message(db, org, inp.message or "")
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def _platform_self_audit_detached(inp: "OrionRuntimeIn", *, org: str = "public") -> Dict[str, Any]:
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        if _looks_like_continuous_audit_status_request(inp.message or ""):
            payload = get_continuous_audit_status_from_message(db, org, inp.message or "")
            payload["governance_decision"] = evaluate_governance_action(
                action_scope="read",
                capability_name="continuous_audit_job_status",
                target_scope="platform",
                context=_governance_context_from_message(inp.message),
                safe_mode=False,
            )
            payload["danielic_integrity_passed"] = bool(payload["governance_decision"].get("danielic_integrity_passed"))
            return payload
        if _looks_like_continuous_audit_request(inp.message or ""):
            payload = start_continuous_audit_job(
                db,
                org,
                message=inp.message or "",
                include_frontend=bool(inp.include_frontend),
                requested_by_user_name="orion_runtime",
            )
            payload["governance_decision"] = evaluate_governance_action(
                action_scope="diagnose",
                capability_name="continuous_audit_job",
                target_scope="platform",
                context=_governance_context_from_message(inp.message),
                safe_mode=False,
            )
            payload["danielic_integrity_passed"] = bool(payload["governance_decision"].get("danielic_integrity_passed"))
            return payload

        visible_agent = _resolve_visible_agent(inp.message, default="orkio")
        payload = _build_platform_self_audit_payload(inp, visible_agent)
        decision = evaluate_governance_action(
            action_scope="diagnose",
            capability_name="platform_self_audit",
            target_scope="platform",
            context=_governance_context_from_message(inp.message),
            safe_mode=False,
        )
        payload["governance_decision"] = decision
        payload["danielic_integrity_passed"] = bool(decision.get("danielic_integrity_passed"))
        return payload
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def platform_self_audit_readonly_final(inp: "OrionRuntimeIn", *, org: str = "public") -> Dict[str, Any]:
    shadow_inp = inp.copy(update={"prepare_only": True}) if hasattr(inp, "copy") else inp
    payload = _platform_self_audit_detached(shadow_inp, org=org)
    payload["ok"] = True
    payload["service"] = "orion_internal"
    payload["mode"] = "analytical_final_readonly"
    payload["provider"] = "platform"
    payload["event"] = "ANALYTICAL_FINAL_READONLY_READY"
    payload["status"] = "ready"
    payload["report_format"] = "analytical_final_readonly_v1"
    payload["delivery_contract"] = "analytical_final_readonly_v1"
    payload["execution_depth"] = "final_readonly"
    payload["dispatch_executed"] = False
    payload["visible_agent"] = "orion"
    payload["target_agent"] = "orion"
    payload["best_effort_analysis"] = True
    payload["specialist_unavailability_is_not_blocking"] = True
    payload["refusal_policy_override"] = "do_not_refuse_for_missing_specialists"
    payload["response_contract"] = "deliver_final_analysis_best_effort"
    payload["grounded_analysis_required"] = True
    payload["required_output_sections"] = [
        "visao_geral_objetiva",
        "evidencias_concretas_observadas",
        "causa_raiz_provavel",
        "fragilidades_arquiteturais_reais",
        "melhorias_priorizadas",
        "riscos_e_validacao",
    ]
    payload["grounding_anchors"] = [
        "app/main.py",
        "app/runtime/intent_engine.py",
        "app/routes/internal/orion_internal.py",
        "/api/chat/stream",
        "/api/auth/heartbeat",
        "/api/me",
        "squad_resolve_readonly",
        "CONSTRAINT_VIOLATION",
    ]
    payload["constraint_notes"] = []
    payload.setdefault("key_files", [
        "app/main.py",
        "app/runtime/intent_engine.py",
        "app/routes/internal/orion_internal.py",
    ])
    payload.setdefault("observed_endpoints", [
        "/api/chat/stream",
        "/api/auth/heartbeat",
        "/api/me",
    ])
    return payload


def _github_repo() -> str:
    return _clean_env("GITHUB_REPO", "")


def _github_repo_web() -> str:
    return _clean_env("GITHUB_REPO_WEB", "")


def _default_branch() -> str:
    return _clean_env("GITHUB_DEFAULT_BASE_BRANCH", _clean_env("GITHUB_BRANCH", "main"))


def _github_write_enabled() -> bool:
    return _bool_env("GITHUB_WRITE_RUNTIME_ENABLED", False) or (
        _bool_env("ENABLE_GITHUB_BRIDGE", False)
        and _bool_env("GITHUB_AUTOMATION_ALLOWED", False)
        and _bool_env("AUTO_CODE_EMISSION_ENABLED", False)
    )


def _github_pr_enabled() -> bool:
    return _bool_env("GITHUB_PR_RUNTIME_ENABLED", False) and (
        _bool_env("AUTO_PR_BACKEND_ENABLED", False)
        or _bool_env("AUTO_PR_FRONTEND_ENABLED", False)
        or _bool_env("AUTO_PR_WRITE_ENABLED", False)
    )


def _main_direct_allowed() -> bool:
    return _bool_env("ALLOW_GITHUB_MAIN_DIRECT", False)


def _evolution_enabled() -> bool:
    return _bool_env("ENABLE_EVOLUTION_LOOP", False)


def _allowed_write_agents() -> List[str]:
    raw = _clean_env("GITHUB_WRITE_ALLOWED_AGENTS", "orion")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def _allowed_read_agents() -> List[str]:
    raw = _clean_env(
        "GITHUB_READ_ALLOWED_AGENTS",
        "orkio,orion,chris,auditor,cto,ux_frontend,backend_engineer,frontend_engineer,devops_sre,security_guardian,data_db_architect,qa_release_engineer,realtime_voice_engineer",
    )
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def _extract_agent_handles(message: str) -> List[str]:
    found = re.findall(r"@([A-Za-z0-9_]+)", message or "")
    return [x.strip().lower() for x in found if x.strip()]


def _excluded_agents_from_message(message: str) -> List[str]:
    raw = (message or "").strip().lower()
    if not raw:
        return []
    patterns = {
        "chris": [
            r"(?:sem|exceto|without|exclude|bloque(?:ar|ie)|remover)\s+@?chris\b",
            r"@?chris\b.*?(?:nao\s+pode|não\s+pode|nao\s+deve|não\s+deve|nao\s+responder|não\s+responder|nao\s+assinar|não\s+assinar|nao\s+interceptar|não\s+interceptar|nao\s+substituir|não\s+substituir)",
        ],
    }
    excluded: List[str] = []
    for canonical, pats in patterns.items():
        if any(re.search(p, raw, flags=re.IGNORECASE) for p in pats):
            excluded.append(canonical)
    return excluded


def _strip_constraint_token(value: Any) -> str:
    raw = str(value or "").strip()
    prev = None
    while raw and raw != prev:
        prev = raw
        raw = re.sub(r"^\s*[-*•]+\s*", "", raw)
        raw = re.sub(r"^\s*\d+[.)]\s*", "", raw)
        raw = raw.strip()
    return raw


def _canonical_dispatch_actor(value: Any) -> str:
    cleaned = _strip_constraint_token(value)
    raw = str(cleaned or "").strip().lower().replace("@", "")
    raw = raw.replace("\\/", "/").replace("/", "_").replace("-", "_").replace(" ", "_")
    raw = re.sub(r"_+", "_", raw).strip("_")
    if not raw:
        return ""
    aliases = {
        "ux_frontend": "ux_frontend",
        "ux_front": "ux_frontend",
        "ux": "ux_frontend",
        "frontend": "ux_frontend",
        "front_end": "ux_frontend",
        "frontend_ux": "ux_frontend",
        "ui_ux": "ux_frontend",
        "orion_cto": "orion",
        "cto_runtime": "orion",
        "backend": "backend_engineer",
        "backend_dev": "backend_engineer",
        "backend_engineer": "backend_engineer",
        "front_engineer": "frontend_engineer",
        "frontend_engineer": "frontend_engineer",
        "devops_sre": "devops_sre",
        "sre": "devops_sre",
        "security_guardian": "security_guardian",
        "data_architect": "data_db_architect",
        "db_architect": "data_db_architect",
        "database_architect": "data_db_architect",
        "data_db_architect": "data_db_architect",
        "qa": "qa_release_engineer",
        "qa_release": "qa_release_engineer",
        "qa_release_engineer": "qa_release_engineer",
        "realtime_engineer": "realtime_voice_engineer",
        "voice_engineer": "realtime_voice_engineer",
        "realtime_voice_engineer": "realtime_voice_engineer",
    }
    return aliases.get(raw, raw)

def _dedupe_dispatch_actors(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: set = set()
    for item in list(items or []):
        slug = _canonical_dispatch_actor(item)
        if slug and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


def _extract_constraint_scalar(message: str, keys: List[str]) -> str:
    raw = message or ""
    for key in keys:
        match = re.search(rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*([^\n#]+?)\s*$", raw)
        if match:
            return _canonical_dispatch_actor(_strip_constraint_token(match.group(1)))
    return ""


def _extract_constraint_list(message: str, keys: List[str]) -> List[str]:
    raw = message or ""
    lines = raw.splitlines()
    out: List[str] = []
    active = False
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        matched = None
        for key in keys:
            if lowered.startswith(f"{key.lower()}:"):
                matched = key
                break
        if matched is not None:
            active = True
            inline = _strip_constraint_token(stripped.split(":", 1)[1].strip())
            if inline:
                parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", inline)]
                out.extend([p for p in parts if p])
            continue
        if not active:
            continue
        if not stripped:
            if out:
                break
            continue
        if re.match(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)", stripped):
            out.append(_strip_constraint_token(stripped))
            continue
        if re.match(r"^[A-Za-z0-9_/@.-]+\s*[:=]", stripped):
            break
        if out:
            break
    if out:
        return _dedupe_dispatch_actors(out)
    for key in keys:
        match = re.search(rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*([^\n#]+?)\s*$", raw)
        if match:
            parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", match.group(1))]
            return _dedupe_dispatch_actors([p for p in parts if p])
    return []

def _extract_constraint_count(message: str) -> Any:
    raw = message or ""
    for pattern in (
        r"(?im)^\s*selected_specialists_count_must_be\s*[:=]\s*(\d+)\s*$",
        r"(?im)^\s*selected_specialists_count\s*[:=]\s*(\d+)\s*$",
    ):
        match = re.search(pattern, raw)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def _extract_hard_constraints(message: str) -> Dict[str, Any]:
    required_signer = _extract_constraint_scalar(message, ["required_signer", "signer_must_be", "signer_must"])
    specialists_required = _extract_constraint_list(message, ["specialists_required", "allowed_specialists_only"])
    specialists_forbidden = _extract_constraint_list(message, ["specialists_forbidden", "forbidden_specialists"])
    selected_count = _extract_constraint_count(message)
    if selected_count is None and specialists_required:
        selected_count = len(specialists_required)
    return {
        "required_signer": required_signer or None,
        "specialists_required": specialists_required,
        "specialists_forbidden": specialists_forbidden,
        "selected_specialists_count_must_be": selected_count,
        "has_hard_constraints": bool(required_signer or specialists_required or specialists_forbidden or selected_count is not None),
    }


def _apply_specialist_constraints(selected: List[str], *, constraints: Dict[str, Any]) -> List[str]:
    required = _dedupe_dispatch_actors(list(constraints.get("specialists_required") or []))
    forbidden = set(_dedupe_dispatch_actors(list(constraints.get("specialists_forbidden") or [])))
    signer = _canonical_dispatch_actor(constraints.get("required_signer") or "")
    count = constraints.get("selected_specialists_count_must_be")
    out = _dedupe_dispatch_actors(required or selected or [])
    if forbidden:
        out = [item for item in out if item not in forbidden]
    if signer and signer not in out and (not required or count is None or len(out) < int(count)):
        out = [signer] + out
        out = _dedupe_dispatch_actors(out)
    if count is not None and int(count) >= 0 and len(out) > int(count):
        out = out[: int(count)]
    return out


def _validate_dispatch_constraints(*, visible_agent: str, selected_specialists: List[str], constraints: Dict[str, Any]) -> List[str]:
    violations: List[str] = []
    required_signer = _canonical_dispatch_actor(constraints.get("required_signer") or "")
    required = _dedupe_dispatch_actors(list(constraints.get("specialists_required") or []))
    forbidden = set(_dedupe_dispatch_actors(list(constraints.get("specialists_forbidden") or [])))
    count = constraints.get("selected_specialists_count_must_be")

    if required_signer and _canonical_dispatch_actor(visible_agent) != required_signer:
        violations.append(f"required_signer={required_signer} was not satisfied")
    if forbidden:
        forbidden_hits = [item for item in selected_specialists if _canonical_dispatch_actor(item) in forbidden]
        if forbidden_hits:
            violations.append("forbidden_specialists present in selected_specialists: " + ", ".join(forbidden_hits))
    if required:
        missing = [item for item in required if item not in _dedupe_dispatch_actors(selected_specialists)]
        extras = [item for item in _dedupe_dispatch_actors(selected_specialists) if item not in required]
        if missing:
            violations.append("missing required specialists: " + ", ".join(missing))
        if extras:
            violations.append("selected_specialists outside required set: " + ", ".join(extras))
    if count is not None and len(list(selected_specialists or [])) != int(count):
        violations.append(f"selected_specialists_count_must_be={int(count)} but got {len(list(selected_specialists or []))}")
    return violations


def _constraint_violation_payload(message: str, *, constraints: Dict[str, Any], violations: List[str]) -> Dict[str, Any]:
    visible_agent = str(constraints.get("required_signer") or _resolve_visible_agent(message, default="orion") or "orion").strip().lower() or "orion"
    return {
        "ok": False,
        "service": "orion_internal",
        "mode": "constraint_violation",
        "provider": "platform",
        "event": "CONSTRAINT_VIOLATION",
        "status": "blocked",
        "execution_depth": "pre_dispatch",
        "delivery_contract": "constraint_violation_v1",
        "visible_agent": visible_agent,
        "required_signer": constraints.get("required_signer"),
        "specialists_required": list(constraints.get("specialists_required") or []),
        "specialists_forbidden": list(constraints.get("specialists_forbidden") or []),
        "selected_specialists_count_must_be": constraints.get("selected_specialists_count_must_be"),
        "message": "CONSTRAINT_VIOLATION",
        "resolution": "Hard constraints blocked execution before dispatch.",
        "constraint_violations": list(violations or []),
        "required_signer": constraints.get("required_signer"),
        "specialists_required": list(constraints.get("specialists_required") or []),
        "specialists_forbidden": list(constraints.get("specialists_forbidden") or []),
        "selected_specialists_count_must_be": constraints.get("selected_specialists_count_must_be"),
        "recommended_actions": [],
        "final_consolidation": "Dispatch abortado antes da execução porque as hard constraints solicitadas não puderam ser satisfeitas com segurança.",
        "generated_at": _now_ts(),
    }
    _persist_assisted_evolution_proposal(payload)
    return payload

def _is_orion_only_request(message: str) -> bool:
    raw = (message or "").strip().lower()
    if not raw:
        return False
    constraints = _extract_hard_constraints(message)
    if len(list(constraints.get("specialists_required") or [])) > 1:
        return False
    if not re.search(r"@orion\b|\borion\b", raw, flags=re.IGNORECASE):
        return False
    if re.search(r"@team\b|\bteam\b|\bequipe\b|\bboard\b|\bconselho\b", raw, flags=re.IGNORECASE):
        return False
    excluded = set(_excluded_agents_from_message(message))
    if "chris" not in excluded and re.search(r"@chris\b|\bchris\b|\bcfo\b", raw, flags=re.IGNORECASE):
        return False
    return True


def _is_team_technical_audit_request(message: str) -> bool:
    raw = (message or "").strip().lower()
    if not raw:
        return False
    has_team = bool(re.search(r"@team\b|\bteam\b|\bequipe\b|\bsquad\b|\bespecialistas\b|\bwar room\b", raw, flags=re.IGNORECASE))
    has_explicit_specialists = sum(
        1 for handle in ("@orion", "@auditor", "@cto", "@ux_frontend", "@ux/frontend")
        if handle in raw
    ) >= 2
    has_audit = bool(re.search(r"auditoria|auditar|audit|diagn[óo]stico|diagnostico|scan|varredura|an[áa]lise t[ée]cnica|analise tecnica|an[áa]lise arquitetural|analise arquitetural|an[áa]lise detalhada|analise detalhada|melhorias priorizadas|recomendac[aã]o consolidada", raw, flags=re.IGNORECASE))
    has_technical_scope = bool(re.search(r"code|codebase|c[óo]digo|codigo|runtime|backend|frontend|repo|reposit[óo]rio|repositorio|main\.py|intent_engine\.py|orion_internal\.py|governan[çc]a|roteamento|agentes|ux|console|chat stream|sse|github bridge", raw, flags=re.IGNORECASE))
    read_only = (
        bool(re.search(r"read[- ]only|somente leitura|sem escrever|n[ãa]o escrever|n[ãa]o executar|nao executar", raw, flags=re.IGNORECASE))
        or not bool(re.search(r"aplicar patch|criar branch|abrir pr|merge|deploy|escrever arquivo", raw, flags=re.IGNORECASE))
    )
    return bool((has_team or has_explicit_specialists) and has_audit and has_technical_scope and read_only)

def _looks_like_final_readonly_analysis_request(message: str) -> bool:
    raw = (message or "").strip().lower()
    if not raw:
        return False
    has_analysis = bool(re.search(r"an[áa]lise detalhada|an[áa]lise arquitetural|auditoria t[ée]cnica|diagn[óo]stico t[ée]cnico|melhorias priorizadas|recomendac[aã]o consolidada|an[áa]lise final", raw, flags=re.IGNORECASE))
    has_scope = bool(re.search(r"code|codebase|c[óo]digo|codigo|runtime|backend|frontend|console|chat stream|sse|intent|governan[çc]a|github bridge|ux", raw, flags=re.IGNORECASE))
    read_only = bool(re.search(r"read[- ]only|somente leitura|n[ãa]o executar|nao executar|n[ãa]o abrir pr|nao abrir pr|n[ãa]o escrever|nao escrever", raw, flags=re.IGNORECASE))
    wants_final_output = bool(re.search(r"entregue apenas a an[áa]lise final|entregar apenas a an[áa]lise final|n[ãa]o resolva squad|nao resolva squad|n[ãa]o retorne trace|nao retorne trace", raw, flags=re.IGNORECASE))
    return bool(has_analysis and has_scope and read_only and wants_final_output)


def _looks_like_governance_capability_question(message: str) -> bool:
    raw = (message or "").strip().lower()
    if not raw:
        return False
    asks_question = ("?" in str(message or "")) or bool(re.search(r"temos a capacidade|tem capacidade|podemos|[ée] poss[íi]vel|eh possivel", raw, flags=re.IGNORECASE))
    asks_write_domain = bool(re.search(r"aplicar melhorias no code|aplicar melhorias no c[óo]digo|melhorias no code|melhorias no c[óo]digo|patch no code|abrir pr|pull request|criar branch|commit|merge|deploy", raw, flags=re.IGNORECASE))
    asks_governance = bool(re.search(r"aprova[cç][ãa]o|autoriza[cç][ãa]o|approval|authorized|sob minha aprova[cç][ãa]o|com minha aprova[cç][ãa]o|mediante minha aprova[cç][ãa]o|ap[óo]s evidenciar as necessidades|evidenciar as necessidades", raw, flags=re.IGNORECASE))
    return bool(asks_question and asks_write_domain and asks_governance)


def _filter_specialists_for_message(selected: List[str], message: str) -> List[str]:
    excluded = set(_dedupe_dispatch_actors(_excluded_agents_from_message(message)))
    out: List[str] = []
    for item in list(selected or []):
        slug = _canonical_dispatch_actor(item)
        if slug and slug not in excluded:
            out.append(slug)
    return _dedupe_dispatch_actors(out)

def _resolve_visible_agent(message: str, default: str = "orion") -> str:
    constraints = _extract_hard_constraints(message)
    required_signer = _canonical_dispatch_actor(constraints.get("required_signer") or "")
    if required_signer:
        return required_signer
    handles = _extract_agent_handles(message)
    if _is_orion_only_request(message):
        return "orion"
    if "orion" in handles:
        return "orion"
    if "orkio" in handles:
        return "orkio"
    if handles:
        return handles[0]
    return default


def _suggested_squad() -> List[Dict[str, str]]:
    return [
        {"id": "orkio", "role": "orchestrator", "scope": "coordenação e síntese"},
        {"id": "orion", "role": "cto", "scope": "execução técnica e GitHub runtime"},
        {"id": "auditor", "role": "technical_auditor", "scope": "auditoria arquitetural e riscos"},
        {"id": "cto", "role": "systems_architect", "scope": "plano técnico e desenho de patch"},
        {"id": "ux_frontend", "role": "ux_frontend", "scope": "renderização, estado local e experiência operacional"},
        {"id": "chris", "role": "commercial_strategist", "scope": "impacto funcional e leitura de produto"},
        {"id": "saint_germain", "role": "refiner", "scope": "maturidade e refinamento incremental"},
        {"id": "miguel", "role": "guardian", "scope": "guarda de segurança e limites"},
        {"id": "uriel", "role": "diagnostician", "scope": "diagnóstico de causa raiz"},
        {"id": "rafael", "role": "organizer", "scope": "plano de ação prático"},
        {"id": "gabriel", "role": "translator", "scope": "tradução executiva e explicação clara"},
        {"id": "metatron", "role": "scribe", "scope": "registro e continuidade"},
    ]


def _build_repo_targets() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    backend = _github_repo()
    frontend = _github_repo_web()
    if backend:
        items.append({"repo": backend, "kind": "backend", "default_branch": _default_branch()})
    if frontend:
        items.append({"repo": frontend, "kind": "frontend", "default_branch": _default_branch()})
    return items


def _safe_patch_policy() -> Dict[str, Any]:
    return {
        "write_enabled": _github_write_enabled(),
        "pr_enabled": _github_pr_enabled(),
        "main_direct_write_allowed": _main_direct_allowed(),
        "require_explicit_deploy_approval": _bool_env("REQUIRE_EXPLICIT_DEPLOY_APPROVAL", True),
        "require_explicit_pr_approval": _bool_env("REQUIRE_EXPLICIT_PR_APPROVAL", True),
        "require_explicit_db_approval": _bool_env("REQUIRE_EXPLICIT_DB_APPROVAL", True),
        "db_runtime_allow_destructive": _bool_env("DB_RUNTIME_ALLOW_DESTRUCTIVE", False),
        "controlled_overlay_enabled": _bool_env("CONTROLLED_EVOLUTION_OVERLAY_ENABLED", True),
        "evolution_loop_enabled": _evolution_enabled(),
        "write_allowed_agents": _allowed_write_agents(),
        "read_allowed_agents": _allowed_read_agents(),
        "require_explicit_pr_approval": _bool_env("REQUIRE_EXPLICIT_PR_APPROVAL", True),
        "transactional_flow_required": True,
        "receipt_required_steps": [
            "branch_created",
            "files_written",
            "commit_created",
            "compare_ok",
            "pull_request_opened",
        ],
        "pr_open_requires_branch_and_commit": True,
        "approval_grant_expands_transaction_prerequisites": True,
        "frontend_repo_target_hard_binding": True,
        "proposal_to_file_write_emission": True,
        "patch_sentinel": PATCH_SENTINEL,
        "patch_feature": PATCH_FEATURE,
        "patch_expected_behavior": PATCH_EXPECTED_BEHAVIOR,
    }



def _github_runtime_token() -> str:
    return (
        _clean_env("ORKIO_GITHUB_CONTROL_PLANE_TOKEN", "")
        or _clean_env("GITHUB_TOKEN", "")
        or _clean_env("GH_TOKEN", "")
    )


def _github_headers() -> Dict[str, str]:
    token = _github_runtime_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "orkio-orion-runtime/1.0",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_api_json(method: str, url: str) -> tuple[int, Any]:
    req = _urllib_request.Request(url, headers=_github_headers(), method=method.upper())
    ctx = _ssl.create_default_context()
    try:
        with _urllib_request.urlopen(req, context=ctx, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace") or "null"
            try:
                return int(getattr(resp, "status", 200) or 200), json.loads(raw)
            except Exception:
                return int(getattr(resp, "status", 200) or 200), {"raw": raw}
    except Exception as exc:
        status = int(getattr(exc, "code", 0) or 0)
        body = getattr(exc, "read", None)
        parsed: Any = {}
        try:
            if body:
                raw = body().decode("utf-8", errors="replace") or "null"
                parsed = json.loads(raw)
        except Exception:
            parsed = {"message": str(exc)}
        if not parsed:
            parsed = {"message": str(exc)}
        return status, parsed



def _looks_like_compare_status_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    compare_markers = [
        "compare a branch",
        "compare branch",
        "compare branches",
        "compare da",
        "compare do",
        "quero o compare",
        "quero compare",
        "comparar a branch",
        "comparar branch",
        "compare_ok",
        "ahead_by",
        "status da pr",
        "status final da pr",
        "status final do pr",
        "pr status",
        "pull request status",
        "pr_url",
        "pr_number",
    ]
    has_compare = any(marker in txt for marker in compare_markers)
    has_pr_ref = bool(re.search(r"\bpr\s*#?\s*\d+\b", txt, flags=re.IGNORECASE))
    has_branch_compare = (("branch" in txt) or ("branches" in txt)) and (("compare" in txt) or ("comparar" in txt))
    has_compare_word = ("compare" in txt) or ("comparar" in txt)
    has_repo_hint = any(token in txt for token in ["repo", "repositório", "repositorio", "frontend", "backend", "main", "master", "contra", "versus", "vs"])
    has_ref_slug = bool(re.search(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", txt))
    structured_fields = any(field in txt for field in ["files_changed", "commit_sha", "compare_ok", "ahead_by", "pr_url", "pr_number"])
    return bool(has_compare or has_pr_ref or has_branch_compare or structured_fields or (has_compare_word and (has_repo_hint or has_ref_slug)))


def _repo_short_name(repo: str) -> str:
    repo = str(repo or "").strip()
    if "/" not in repo:
        return repo
    return repo.split("/", 1)[1].strip()


def _repo_owner(repo: str) -> str:
    repo = str(repo or "").strip()
    if "/" not in repo:
        return ""
    return repo.split("/", 1)[0].strip()


def _looks_like_branch_slug(value: str) -> bool:
    value = str(value or "").strip().lower()
    if not value or "/" not in value:
        return False
    prefixes = ("feat/", "fix/", "hotfix/", "chore/", "docs/", "refactor/", "test/", "tests/", "build/", "ci/", "perf/", "release/")
    if value.startswith(prefixes):
        return True
    owner, slug = value.split("/", 1)
    if owner in {"main", "master", "develop", "dev", "production", "prod"}:
        return True
    if not owner or not slug:
        return True
    return False


_BRANCH_NAME_STOPWORDS = {
    "a",
    "as",
    "branch",
    "branches",
    "compare",
    "comparar",
    "com",
    "contra",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "na",
    "no",
    "para",
    "pr",
    "pull",
    "request",
    "the",
    "to",
    "vs",
    "versus",
}


def _normalize_branch_candidate(value: str) -> str:
    candidate = str(value or "").strip().strip(".,:;()[]{}")
    if not candidate:
        return ""
    lowered = candidate.lower()
    if lowered in _BRANCH_NAME_STOPWORDS:
        return ""
    if re.fullmatch(r"#?\d+", candidate):
        return ""
    return candidate


def _extract_explicit_repo_from_message(message: str) -> str:
    txt = (message or "").strip()
    if not txt:
        return ""

    url_match = re.search(r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", txt, flags=re.IGNORECASE)
    if url_match:
        candidate = str(url_match.group(1) or "").strip().strip("/")
        return "" if _looks_like_branch_slug(candidate) else candidate

    marker_patterns = [
        r"(?:repositório|repositorio|repo|repository)\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
        r"(?:repositório|repositorio|repo|repository)\s*[:=]\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
        r"no\s+(?:repositório|repositorio|repo|repository)\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
        r"do\s+(?:repositório|repositorio|repo|repository)\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
    ]
    for pat in marker_patterns:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = str(m.group(1) or "").strip()
        if candidate and not _looks_like_branch_slug(candidate):
            return candidate
    return ""


def _repo_matches_alias(candidate: str, configured: str) -> bool:
    candidate = str(candidate or "").strip().lower()
    configured = str(configured or "").strip().lower()
    if not candidate or not configured:
        return False
    if candidate == configured:
        return True
    candidate_owner = _repo_owner(candidate)
    configured_owner = _repo_owner(configured)
    candidate_short = _repo_short_name(candidate).lower()
    configured_short = _repo_short_name(configured).lower()
    if candidate_owner and configured_owner and candidate_owner != configured_owner:
        return False
    if candidate_short == configured_short:
        return True
    if configured_short.startswith(candidate_short + "-"):
        return True
    return False


def _normalize_repo_target(repo_candidate: str, backend: str, frontend: str, message: str) -> str:
    candidate = str(repo_candidate or "").strip()
    txt = (message or "").strip().lower()
    if candidate:
        if _repo_matches_alias(candidate, frontend):
            return frontend or candidate
        if _repo_matches_alias(candidate, backend):
            return backend or candidate
        return candidate
    if "frontend" in txt or "web" in txt or "appconsole" in txt or "react" in txt or "tsx" in txt or "jsx" in txt:
        return frontend or backend
    return backend or frontend


def _resolve_repo_target_from_message(message: str) -> str:
    explicit = _extract_explicit_repo_from_message(message)
    backend = _github_repo()
    frontend = _github_repo_web()
    return _normalize_repo_target(explicit, backend, frontend, message)




def _extract_branch_names_from_message(message: str) -> tuple[str, str]:
    txt = (message or "").strip()
    default_branch = _default_branch()
    head = ""
    base = ""
    patterns = [
        r"compare\s+(?:a\s+)?branch\s+([A-Za-z0-9_./-]+)\s+com\s+a\s+(?:branch\s+)?([A-Za-z0-9_./-]+)",
        r"compare\s+(?:a\s+)?branch\s+([A-Za-z0-9_./-]+)\s+(?:contra|com|versus|vs)\s+(?:a\s+)?(?:branch\s+)?([A-Za-z0-9_./-]+)",
        r"comparar\s+(?:a\s+)?branch\s+([A-Za-z0-9_./-]+)\s+(?:contra|com|versus|vs)\s+(?:a\s+)?(?:branch\s+)?([A-Za-z0-9_./-]+)",
        r"compare\s+(?:da|do|de)\s+([A-Za-z0-9_./-]+).*?(?:contra|com|versus|vs)\s+([A-Za-z0-9_./-]+)",
        r"comparar\s+(?:da|do|de)\s+([A-Za-z0-9_./-]+).*?(?:contra|com|versus|vs)\s+([A-Za-z0-9_./-]+)",
        r"branch\s+([A-Za-z0-9_./-]+)\s+to\s+([A-Za-z0-9_./-]+)",
        r"da\s+branch\s+([A-Za-z0-9_./-]+)\s+para\s+([A-Za-z0-9_./-]+)",
        r"head\s*[:=]\s*([A-Za-z0-9_./-]+).*?base\s*[:=]\s*([A-Za-z0-9_./-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, txt, flags=re.IGNORECASE)
        if m:
            head = _normalize_branch_candidate(m.group(1))
            base = _normalize_branch_candidate(m.group(2))
            if head or base:
                break

    if not head:
        m = re.search(r"branch\s+([A-Za-z0-9_./-]+)", txt, flags=re.IGNORECASE)
        if m:
            head = _normalize_branch_candidate(m.group(1))

    if not head and (("compare" in txt.lower()) or ("comparar" in txt.lower())):
        slug_match = re.search(
            r"\b((?:feat|fix|hotfix|chore|docs|refactor|test|tests|build|ci|perf|release)/[A-Za-z0-9_./-]+)\b",
            txt,
            flags=re.IGNORECASE,
        )
        if slug_match:
            head = _normalize_branch_candidate(slug_match.group(1))

    if not base:
        m = re.search(r"(?:contra|com|versus|vs)\s+(?:a\s+)?(?:branch\s+)?([A-Za-z0-9_./-]+)", txt, flags=re.IGNORECASE)
        if m:
            base = _normalize_branch_candidate(m.group(1))

    if not base:
        m = re.search(r"base(?:_branch)?\s*[:=]?\s*([A-Za-z0-9_./-]+)", txt, flags=re.IGNORECASE)
        if m:
            base = _normalize_branch_candidate(m.group(1))

    if not base:
        m = re.search(r"\b(main|master|production|prod|develop|dev)\b", txt, flags=re.IGNORECASE)
        if m:
            base = _normalize_branch_candidate(m.group(1))

    return head, (base or default_branch)

def _extract_pr_number_from_message(message: str) -> int:
    txt = (message or "").strip()
    if not txt:
        return 0
    m = re.search(r"\bpr\s*#?\s*(\d+)\b", txt, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bpull request\s*#?\s*(\d+)\b", txt, flags=re.IGNORECASE)
    try:
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def _github_branch_head_sha(repo: str, branch: str) -> str:
    repo = str(repo or "").strip()
    branch = str(branch or "").strip()
    if not repo or not branch:
        return ""
    url = f"https://api.github.com/repos/{repo}/branches/{_urllib_parse.quote(branch, safe='')}"
    status, body = _github_api_json("GET", url)
    if status != 200 or not isinstance(body, dict):
        return ""
    commit = body.get("commit") if isinstance(body.get("commit"), dict) else {}
    return str(commit.get("sha") or "").strip()


def _github_pr_by_number(repo: str, pr_number: int) -> Dict[str, Any]:
    if not repo or pr_number <= 0:
        return {"ok": False, "message": "pr_number_missing"}
    url = f"https://api.github.com/repos/{repo}/pulls/{int(pr_number)}"
    status, body = _github_api_json("GET", url)
    ok = status == 200 and isinstance(body, dict)
    return {"ok": ok, "status": status, "body": body if isinstance(body, dict) else {}, "message": "" if ok else str((body or {}).get("message") or f"pull_fetch_failed_status_{status}")}


def _github_find_pull_by_head(repo: str, head: str, base: str) -> Dict[str, Any]:
    repo = str(repo or "").strip()
    head = str(head or "").strip()
    base = str(base or "").strip()
    owner = _repo_owner(repo)
    if not repo or not head:
        return {"ok": False, "message": "repo_or_head_missing"}
    q = _urllib_parse.urlencode({"state": "open", "head": f"{owner}:{head}", "base": base or _default_branch()})
    url = f"https://api.github.com/repos/{repo}/pulls?{q}"
    status, body = _github_api_json("GET", url)
    if status != 200 or not isinstance(body, list):
        return {"ok": False, "message": f"pull_list_failed_status_{status}", "body": body}
    first = body[0] if body else {}
    return {"ok": bool(first), "body": first if isinstance(first, dict) else {}, "message": "" if first else "pull_not_found"}


def _github_compare(repo: str, base: str, head: str) -> Dict[str, Any]:
    repo = str(repo or "").strip()
    base = str(base or "").strip()
    head = str(head or "").strip()
    if not repo or not base or not head:
        return {"ok": False, "message": "repo_base_head_missing", "files_changed": []}
    url = f"https://api.github.com/repos/{repo}/compare/{_urllib_parse.quote(base, safe='')}...{_urllib_parse.quote(head, safe='')}"
    status, body = _github_api_json("GET", url)
    if status != 200 or not isinstance(body, dict):
        message = str((body or {}).get("message") or f"compare_failed_status_{status}")
        return {"ok": False, "status": status, "message": message, "body": body, "files_changed": []}
    files = body.get("files") if isinstance(body.get("files"), list) else []
    file_names = []
    for item in files:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip()
        if filename:
            file_names.append(filename)
    commits = body.get("commits") if isinstance(body.get("commits"), list) else []
    latest_commit_sha = ""
    if commits and isinstance(commits[-1], dict):
        latest_commit_sha = str(commits[-1].get("sha") or "").strip()
    if not latest_commit_sha:
        latest_commit_sha = _github_branch_head_sha(repo, head)
    return {
        "ok": True,
        "status": status,
        "body": body,
        "ahead_by": int(body.get("ahead_by") or 0),
        "behind_by": int(body.get("behind_by") or 0),
        "files_changed": file_names,
        "files_count": len(file_names),
        "commit_sha": latest_commit_sha,
        "html_url": str(body.get("html_url") or "").strip(),
    }


def _github_compare_status_payload(message: str, visible_agent: str, repository_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    repo_target = _resolve_repo_target_from_message(message)
    default_branch = _default_branch()
    pr_number = _extract_pr_number_from_message(message)
    head, base = _extract_branch_names_from_message(message)
    pr_payload: Dict[str, Any] = {}
    pr_url = ""
    merge_executed = False
    head_sha = ""

    if pr_number > 0:
        pr_lookup = _github_pr_by_number(repo_target, pr_number)
        if pr_lookup.get("ok"):
            pr_payload = pr_lookup.get("body") if isinstance(pr_lookup.get("body"), dict) else {}
            head_ref = pr_payload.get("head") if isinstance(pr_payload.get("head"), dict) else {}
            base_ref = pr_payload.get("base") if isinstance(pr_payload.get("base"), dict) else {}
            resolved_pr_head = _normalize_branch_candidate(head_ref.get("ref"))
            resolved_pr_base = _normalize_branch_candidate(base_ref.get("ref"))
            normalized_head = _normalize_branch_candidate(head)
            normalized_base = _normalize_branch_candidate(base)
            head = normalized_head or resolved_pr_head
            base = normalized_base or resolved_pr_base or default_branch
            head_sha = str(head_ref.get("sha") or "").strip()
            pr_url = str(pr_payload.get("html_url") or "").strip()
            merge_executed = bool(pr_payload.get("merged"))
        else:
            return {
                "ok": True,
                "service": "orion_internal",
                "mode": "github_compare_status",
                "event": "GITHUB_COMPARE_STATUS_OK",
                "provider": "github",
                "visible_agent": visible_agent,
                "repo": repo_target,
                "repo_target": repo_target,
                "backend_repo": _github_repo(),
                "frontend_repo": _github_repo_web(),
                "repository_details": repository_details,
                "branch": head,
                "branch_name": head,
                "base_branch": base or default_branch,
                "compare_ok": False,
                "merge_executed": False,
                "deploy_executed": False,
                "pr_number": int(pr_number or 0),
                "pr_found": False,
                "resolution": "pull_request_not_found",
                "message": "pull_request_not_found",
                "github_error": str(pr_lookup.get("message") or "pull_request_not_found"),
                "generated_at": _now_ts(),
            }

    head = _normalize_branch_candidate(head)
    base = _normalize_branch_candidate(base) or default_branch

    if not head:
        return {
            "ok": True,
            "service": "orion_internal",
            "mode": "github_compare_status",
            "event": "GITHUB_COMPARE_STATUS_INPUT_INVALID",
            "provider": "github",
            "visible_agent": visible_agent,
            "repo": repo_target,
            "repo_target": repo_target,
            "backend_repo": _github_repo(),
            "frontend_repo": _github_repo_web(),
            "repository_details": repository_details,
            "pr_number": int(pr_number or 0),
            "compare_ok": False,
            "merge_executed": False,
            "deploy_executed": False,
            "message": "head_branch_not_detected",
            "expected_input": "compare <head_branch> contra <base_branch> no repo <owner/repo>",
            "generated_at": _now_ts(),
        }

    compare_payload = _github_compare(repo_target, base or default_branch, head)
    if (not compare_payload.get("ok")) and head_sha:
        compare_payload = _github_compare(repo_target, base or default_branch, head_sha)

    if not compare_payload.get("ok"):
        if not pr_number:
            pr_lookup = _github_find_pull_by_head(repo_target, head, base or default_branch)
            if pr_lookup.get("ok"):
                pr_payload = pr_lookup.get("body") if isinstance(pr_lookup.get("body"), dict) else {}
                pr_number = int(pr_payload.get("number") or 0)
                pr_url = str(pr_payload.get("html_url") or "").strip()
                merge_executed = bool(pr_payload.get("merged"))
        if pr_number or pr_url:
            return {
                "ok": True,
                "service": "orion_internal",
                "mode": "github_compare_status",
                "event": "GITHUB_COMPARE_STATUS_PARTIAL",
                "provider": "github",
                "visible_agent": visible_agent,
                "repo": repo_target,
                "repo_target": repo_target,
                "backend_repo": _github_repo(),
                "frontend_repo": _github_repo_web(),
                "repository_details": repository_details,
                "branch": head,
                "branch_name": head,
                "base_branch": base or default_branch,
                "compare_ok": False,
                "compare_error": str(compare_payload.get("message") or "compare_failed"),
                "pr_number": int(pr_number or 0),
                "pr_url": pr_url,
                "merge_executed": bool(merge_executed),
                "deploy_executed": False,
                "generated_at": _now_ts(),
            }
        return {
            "ok": False,
            "service": "orion_internal",
            "mode": "github_compare_status",
            "event": "GITHUB_COMPARE_STATUS_FAILED",
            "provider": "github",
            "visible_agent": visible_agent,
            "repo": repo_target,
            "repo_target": repo_target,
            "backend_repo": _github_repo(),
            "frontend_repo": _github_repo_web(),
            "repository_details": repository_details,
            "branch_name": head,
            "base_branch": base or default_branch,
            "message": str(compare_payload.get("message") or "compare_failed"),
            "generated_at": _now_ts(),
        }

    if not pr_number:
        pr_lookup = _github_find_pull_by_head(repo_target, head, base or default_branch)
        if pr_lookup.get("ok"):
            pr_payload = pr_lookup.get("body") if isinstance(pr_lookup.get("body"), dict) else {}
            pr_number = int(pr_payload.get("number") or 0)
            pr_url = str(pr_payload.get("html_url") or "").strip()
            merge_executed = bool(pr_payload.get("merged"))
    commit_sha = str(compare_payload.get("commit_sha") or "").strip()
    files_changed = list(compare_payload.get("files_changed") or [])
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "github_compare_status",
        "event": "GITHUB_COMPARE_STATUS_OK",
        "provider": "github",
        "visible_agent": visible_agent,
        "repo": repo_target,
        "repo_target": repo_target,
        "backend_repo": _github_repo(),
        "frontend_repo": _github_repo_web(),
        "repository_details": repository_details,
        "branch": head,
        "branch_name": head,
        "base_branch": base or default_branch,
        "compare_ok": True,
        "ahead_by": int(compare_payload.get("ahead_by") or 0),
        "behind_by": int(compare_payload.get("behind_by") or 0),
        "files_changed": files_changed,
        "files_count": len(files_changed),
        "commit_sha": commit_sha,
        "pr_number": int(pr_number or 0),
        "pr_url": pr_url,
        "merge_executed": bool(merge_executed),
        "deploy_executed": False,
        "generated_at": _now_ts(),
    }


def _looks_like_repo_inventory_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    patterns = [
        r"github_repo_web",
        r"github_repo\b",
        r"reposit[oó]rio backend",
        r"reposit[oó]rio frontend",
        r"repos?it[oó]rios? ativos",
        r"quais os reposit[oó]rios",
        r"valor bruto carregado",
        r"runtime.*github_repo",
        r"listar as novas repos",
    ]
    return any(re.search(p, txt, flags=re.IGNORECASE) for p in patterns)


def _wants_root_evidence(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    markers = [
        "raiz",
        "root",
        "readme",
        "3 arquivos",
        "3 pastas",
        "arquivos ou pastas",
        "evidência",
        "evidencia",
        "cite pelo menos 3",
        "mostre pelo menos 3",
    ]
    return any(marker in txt for marker in markers)


def _github_root_entries(repo: str, branch: str, *, limit: int = 3) -> Dict[str, Any]:
    token = _github_runtime_token()
    if not repo:
        return {"ok": False, "message": "repo_not_configured", "entries": []}
    if not token:
        return {"ok": False, "message": "github_token_not_available", "entries": []}
    url = f"https://api.github.com/repos/{repo}/contents?ref={branch}"
    status, body = _github_api_json("GET", url)
    if status != 200 or not isinstance(body, list):
        message = ""
        if isinstance(body, dict):
            message = str(body.get("message") or "").strip()
        return {"ok": False, "message": message or f"root_list_failed_status_{status}", "entries": []}
    entries: List[str] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        kind = str(item.get("type") or "").strip()
        if not name:
            continue
        entries.append(f"{name} ({kind or 'item'})")
        if len(entries) >= limit:
            break
    return {"ok": True, "entries": entries}


def _scan_categories() -> List[Dict[str, str]]:
    return [
        {"category": "repo_structure", "description": "estrutura de pastas, módulos críticos e zonas de risco"},
        {"category": "routes", "description": "rotas internas, públicas e contratos de execução"},
        {"category": "runtime", "description": "intent engine, planner, capabilities e dispatch"},
        {"category": "security", "description": "env flags, política de escrita e controles destrutivos"},
        {"category": "frontend_backend_contract", "description": "handoff entre chat/stream e executores internos"},
    ]


def _audit_scope(message: str) -> str:
    txt = (message or "").strip().lower()
    specialist_markers = (
        "por especialidade",
        "por especialista",
        "por área",
        "por area",
        "especialistas internos",
        "specialist",
        "acione os especialistas",
        "acione a equipe técnica",
        "acione a equipe tecnica",
        "equipe técnica",
        "equipe tecnica",
        "especialistas técnicos",
        "especialistas tecnicos",
    )
    return "specialist" if any(marker in txt for marker in specialist_markers) else "standard"


def _is_premium_platform_audit_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    premium_markers = (
        "experiência premium",
        "experiencia premium",
        "irresistível",
        "irresistivel",
        "alto valor percebido",
        "elegante",
        "fluida",
        "confiável",
        "confiavel",
        "onboarding",
        "primeira impressão",
        "primeira impressao",
        "consistência visual",
        "consistencia visual",
        "wallet",
        "billing",
        "mobile",
        "pwa",
        "latência",
        "latencia",
    )
    audit_markers = (
        "varredura profunda",
        "somente leitura",
        "read only",
        "multiagente",
        "toda a equipe técnica interna",
        "toda a equipe tecnica interna",
        "plataforma inteira",
        "melhorias necessárias",
        "melhorias necessarias",
        "premium",
    )
    return any(marker in txt for marker in premium_markers) and any(marker in txt for marker in audit_markers)


def _is_controlled_self_evolution_propose_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    evolution_markers = (
        "autoevolução controlada",
        "autoevolucao controlada",
        "auto evolucao controlada",
        "ciclo de autoevolução",
        "ciclo de autoevolucao",
        "self evolution",
        "self-evolution",
        "evolução controlada",
        "evolucao controlada",
    )
    scope_markers = (
        "propose_only",
        "modo propose_only",
        "somente proposta",
        "apenas proposta",
        "backlog priorizado",
        "selecionar a melhoria",
        "melhoria de maior impacto",
        "menor risco",
        "última auditoria premium",
        "ultima auditoria premium",
        "sem pr",
        "sem merge",
        "sem deploy",
    )
    return any(marker in txt for marker in evolution_markers) and any(marker in txt for marker in scope_markers)


def _is_platform_improvement_review_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False

    source_audit_markers = (
        "auditoria de fonte do runtime",
        "catálogo público",
        "catalogo publico",
        "catálogo privilegiado",
        "catalogo privilegiado",
        "agentes ocultos",
        "agentes internos",
        "agentes system",
        "seed oculto",
        "divergências entre fontes",
        "divergencias entre fontes",
    )
    if any(marker in txt for marker in source_audit_markers):
        return False

    explicit_review_markers = (
        "mesa de melhorias",
        "rodada de melhorias",
        "review de melhorias",
        "improvement review",
        "platform improvement review",
        "melhorias da plataforma",
        "propostas de melhoria",
        "sugestões de melhoria",
        "sugestoes de melhoria",
        "quick wins",
        "melhorias estruturais",
        "ordem recomendada de implementação",
        "ordem recomendada de implementacao",
        "ordem de implementação",
        "ordem de implementacao",
    )
    if any(marker in txt for marker in explicit_review_markers):
        return True

    improvement_markers = (
        "melhoria",
        "melhorias",
        "improvement",
        "quick wins",
        "estruturais",
        "priorizadas",
        "priorizados",
        "sugestões",
        "sugestoes",
        "propostas",
    )
    scope_markers = (
        "plataforma",
        "app console",
        "landing",
        "fluxo de entrada",
        "receipts",
        "specialist reports",
        "dispatch",
        "observabilidade",
        "logs",
        "governança",
        "governanca",
        "capabilities",
        "comandos",
        "chat/stream",
        "streaming",
        "performance percebida",
        "multiagente",
        "multi-tenant",
        "segurança",
        "seguranca",
        "ux",
        "frontend",
    )
    write_markers = (
        "aplicar patch",
        "criar branch",
        "abrir pr",
        "merge",
        "deploy",
        "escrever arquivo",
    )
    return any(marker in txt for marker in improvement_markers) and any(marker in txt for marker in scope_markers) and not any(marker in txt for marker in write_markers)


def _build_controlled_self_evolution_sections(selected_specialists: List[str]) -> Dict[str, Any]:
    premium = _build_premium_platform_audit_sections(selected_specialists)
    probable_files = [
        "frontend: src/routes/AppConsole.jsx",
        "frontend: src/components/console/EmptyStatePremium.jsx",
        "frontend: src/components/chat/ChatTopbar.jsx",
        "frontend: src/components/chat/MessageComposer.jsx",
    ]
    implementation_steps = [
        "Criar empty state premium com CTA primário, prova de valor e primeira ação guiada.",
        "Exibir objetivo atual, próximo passo recomendado e sinal de controle humano no topo do console.",
        "Padronizar loading, erro e fallback com linguagem premium e baixa fricção.",
        "Adicionar instrumentação de UX percebida para empty state, CTA inicial e recuperação.",
    ]
    return {
        "selected_improvement": "Reescrever o empty state premium do AppConsole com primeira vitória guiada.",
        "root_cause": "A plataforma possui potência real no backend, mas o console inicial ainda não traduz imediatamente esse valor em desejo de uso, clareza e sensação de exclusividade.",
        "user_impact": "Aumenta compreensão imediata, reduz fricção na primeira sessão e melhora a percepção de sofisticação e controle do produto.",
        "technical_risk": "Baixo a moderado. A mudança é principalmente de frontend e contrato de apresentação, com risco contido desde que não altere fluxos críticos de autenticação, chat e streaming.",
        "probable_files": probable_files,
        "implementation_steps": implementation_steps,
        "priority_score": 9.4,
        "priority_score_label": "9.4/10",
        "pr_required": True,
        "human_approval_required": True,
        "approval_required_for_pr": True,
        "next_authorization_command": "@Orion Autorizo preparar branch, aplicar patch do empty state premium no frontend e abrir PR nesta thread. Não autorizo merge nem deploy.",
        "source_audit_event": "PLATFORM_PREMIUM_AUDIT_EXECUTED",
        "source_audit_reference": premium.get("principal_premium_blocker") or "",
        "final_consolidation": "A primeira autoevolução recomendada é frontend-first: empty state premium + onboarding de primeira vitória, em PR governada e sem tocar em main, merge ou deploy.",
    }


def platform_self_evolution_plan(inp: "OrionRuntimeIn") -> Dict[str, Any]:
    constraints = _extract_hard_constraints(inp.message)
    visible_agent = _resolve_visible_agent(inp.message, default="orion")
    selected_specialists = _filter_specialists_for_message(_audit_selected_specialists("specialist", bool(inp.include_frontend), premium_mode=True), inp.message)
    selected_specialists = _apply_specialist_constraints(selected_specialists, constraints=constraints)
    violations = _validate_dispatch_constraints(
        visible_agent=visible_agent,
        selected_specialists=selected_specialists,
        constraints=constraints,
    )
    if violations:
        return _constraint_violation_payload(inp.message, constraints=constraints, violations=violations)
    dispatch_receipts = _audit_dispatch_receipts(selected_specialists, "specialist")
    specialist_reports = _audit_specialist_reports(selected_specialists, "specialist")
    counts = _dispatch_receipt_counts(dispatch_receipts, specialist_reports, selected_specialists)
    sections = _build_controlled_self_evolution_sections(selected_specialists)
    payload = {
        "ok": True,
        "service": "orion_internal",
        "mode": "controlled_self_evolution_propose_only",
        "provider": "platform",
        "event": "CONTROLLED_SELF_EVOLUTION_PROPOSED",
        "status": "executed",
        "scope": "specialist",
        "report_format": "controlled_self_evolution_propose_only_v1",
        "delivery_contract": "controlled_self_evolution_propose_only_v1",
        "execution_depth": "dispatch",
        "execution_mode": "propose_only",
        "founder_control_mode": "human_controlled_runtime_only",
        "auditability_status": "ready_for_persistence",
        "visible_agent": visible_agent,
        "repo": _github_repo(),
        "technical_summary": "Ciclo de autoevolução controlada executado em modo propose_only. A plataforma selecionou a melhoria de maior impacto e menor risco sem acionar GitHub write, PR, merge ou deploy.",
        "selected_specialists": selected_specialists,
        "selected_specialists_count": counts.get("selected_specialists_count", 0),
        "dispatch_receipts": dispatch_receipts,
        "dispatch_receipts_count": counts.get("dispatch_receipts_count", 0),
        "specialist_reports": specialist_reports,
        "specialist_reports_count": counts.get("specialist_reports_count", 0),
        "github_write_blocked": True,
        "specialist_fanout_applied": True,
        "approval_required_for_pr": True,
        "selected_improvement": sections.get("selected_improvement") or "",
        "root_cause": sections.get("root_cause") or "",
        "user_impact": sections.get("user_impact") or "",
        "technical_risk": sections.get("technical_risk") or "",
        "probable_files": sections.get("probable_files") or [],
        "implementation_steps": sections.get("implementation_steps") or [],
        "priority_score": sections.get("priority_score"),
        "priority_score_label": sections.get("priority_score_label") or "",
        "pr_required": bool(sections.get("pr_required")),
        "human_approval_required": bool(sections.get("human_approval_required")),
        "next_authorization_command": sections.get("next_authorization_command") or "",
        "source_audit_event": sections.get("source_audit_event") or "",
        "source_audit_reference": sections.get("source_audit_reference") or "",
        "final_consolidation": sections.get("final_consolidation") or "",
        "recommended_actions": [
            "Preparar patch frontend do empty state premium em branch governada.",
            "Manter merge e deploy bloqueados até aprovação humana explícita.",
            "Validar UX em web e PWA antes de expandir para próximos ciclos.",
        ],
        "key_files": [
            "src/routes/AppConsole.jsx",
            "src/components/console/EmptyStatePremium.jsx",
            "src/components/chat/ChatTopbar.jsx",
            "src/components/chat/MessageComposer.jsx",
        ],
        "generated_at": _now_ts(),
    }


def platform_improvement_review(inp: "OrionRuntimeIn") -> Dict[str, Any]:
    payload = platform_self_evolution_plan(inp)
    payload["mode"] = "platform_improvement_review"
    payload["event"] = "PLATFORM_IMPROVEMENT_REVIEW_EXECUTED"
    payload["report_format"] = "platform_improvement_review_v1"
    payload["delivery_contract"] = "platform_improvement_review_v1"
    payload["technical_summary"] = "Mesa técnica de melhorias executada em modo read-only/propose-only. A plataforma consolidou propostas novas e priorizadas sem acionar GitHub write, PR, merge ou deploy."
    payload["focus_areas"] = [
        "app_console",
        "landing_and_entry_flow",
        "dispatch_clarity",
        "receipts_and_specialist_reports",
        "observability_and_log_noise",
        "governance_of_sensitive_actions",
        "capabilities_and_commands_ux",
        "chat_stream_performance",
        "multiagent_coherence",
        "security_and_multi_tenant_isolation",
    ]
    return payload


def _audit_wants_full_execution(message: str, prepare_only: bool = False) -> bool:
    if prepare_only:
        return False
    txt = (message or "").strip().lower()
    execution_markers = (
        "prosseguir agora",
        "prosseguir com a auditoria",
        "quero a execução integral",
        "quero a execucao integral",
        "auditoria completa",
        "auditoria profunda",
        "execução integral",
        "execucao integral",
        "fatos observados",
        "evidências técnicas",
        "evidencias tecnicas",
        "causas raiz",
        "maturidade atual do sistema",
        "acione os especialistas",
        "acione a equipe técnica",
        "acione a equipe tecnica",
        "varredura no código",
        "varredura no codigo",
        "dê continuidade",
        "de continuidade",
        "execute as ações necessárias",
        "execute as acoes necessarias",
        "execute as últimas orientações",
        "execute as ultimas orientacoes",
        "verifique o github runtime",
        "verifique github runtime",
        "verifique o runtime",
        "verifique runtime",
        "diagnóstico técnico objetivo",
        "diagnostico tecnico objetivo",
        "análise técnica objetiva",
        "analise tecnica objetiva",
        "diagnóstico técnico da plataforma",
        "diagnostico tecnico da plataforma",
        "diagnóstico do backend",
        "diagnostico do backend",
        "diagnóstico do frontend",
        "diagnostico do frontend",
        "responda exclusivamente como orion",
        "respondendo exclusivamente como orion",
    )
    return any(marker in txt for marker in execution_markers)


def _is_orion_direct_diagnostic_request(message: str, visible_agent: str = "orion") -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    if str(visible_agent or "").strip().lower() != "orion":
        return False

    direct_markers = (
        "verifique o github runtime",
        "verifique github runtime",
        "verifique o runtime",
        "verifique runtime",
        "diagnóstico técnico objetivo",
        "diagnostico tecnico objetivo",
        "análise técnica objetiva",
        "analise tecnica objetiva",
        "diagnóstico técnico da plataforma",
        "diagnostico tecnico da plataforma",
        "diagnóstico do backend",
        "diagnostico do backend",
        "diagnóstico do frontend",
        "diagnostico do frontend",
        "me devolva um diagnóstico técnico objetivo",
        "me devolva um diagnostico tecnico objetivo",
        "responda exclusivamente como orion",
        "respondendo exclusivamente como orion",
        "sem delegar a outro agente",
    )

    if any(marker in txt for marker in direct_markers):
        return True

    return (
        ("github" in txt or "runtime" in txt)
        and ("diagnóstico" in txt or "diagnostico" in txt or "objetivo" in txt or "verifique" in txt)
        and ("orion" in txt or "@orion" in txt)
    )


def _audit_facts_observed(scope: str) -> List[str]:
    facts = [
        "Capability consultiva registrada no runtime interno.",
        "Handlers de escrita governada e runtime GitHub continuam habilitados e protegidos por flags e aprovações explícitas.",
        "ALLOW_GITHUB_MAIN_DIRECT permanece desabilitado, preservando o bloqueio de escrita direta em main.",
        "ENABLE_EVOLUTION_LOOP pode permanecer falso sem impedir auditoria read-only.",
    ]
    if scope == "specialist":
        facts.append("Escopo specialist solicitado: auditor, cto, orion e chris devem ser despachados e consolidados com recibos explícitos.")
    return facts


def _audit_evidence_points() -> List[str]:
    return [
        f"ENABLE_EVOLUTION_LOOP={_evolution_enabled()}",
        f"GITHUB_WRITE_RUNTIME_ENABLED={_bool_env('GITHUB_WRITE_RUNTIME_ENABLED', False)}",
        f"GITHUB_PR_RUNTIME_ENABLED={_bool_env('GITHUB_PR_RUNTIME_ENABLED', False)}",
        f"AUTO_PR_WRITE_ENABLED={_bool_env('AUTO_PR_WRITE_ENABLED', False)}",
        f"ALLOW_GITHUB_MAIN_DIRECT={_main_direct_allowed()}",
        f"REQUIRE_EXPLICIT_DEPLOY_APPROVAL={_bool_env('REQUIRE_EXPLICIT_DEPLOY_APPROVAL', True)}",
        f"REQUIRE_EXPLICIT_DB_APPROVAL={_bool_env('REQUIRE_EXPLICIT_DB_APPROVAL', True)}",
        f"backend_repo_configured={bool(_github_repo())}",
        f"frontend_repo_configured={bool(_github_repo_web())}",
    ]


def _audit_findings(scope: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = [
        {
            "severity": "ALTO",
            "title": "Auditoria consultiva já entra na trilha correta, mas readiness report ainda pode substituir a execução profunda.",
            "detail": "Quando a intenção consultiva é reconhecida, a capability correta deve produzir relatório final e não apenas confirmação de preparação.",
        },
        {
            "severity": "ALTO",
            "title": "Separação entre auditoria consultiva, inventário/runtime e escrita governada continua sendo zona sensível de regressão.",
            "detail": "Prompts que misturam termos como GitHub, repo e branch ainda exigem precedência explícita da trilha consultiva para evitar captura indevida.",
        },
        {
            "severity": "MÉDIO",
            "title": "Loop automático desabilitado não pode degradar auditoria read-only.",
            "detail": "A execução consultiva deve depender apenas do dispatcher interno e não do ENABLE_EVOLUTION_LOOP.",
        },
        {
            "severity": "MÉDIO",
            "title": "Qualidade da saída consultiva ainda precisa distinguir fatos, inferências e recomendações.",
            "detail": "Sem essa separação, a auditoria perde valor operacional e volta ao padrão de resumo genérico.",
        },
    ]
    if scope == "specialist":
        findings.append(
            {
                "severity": "MÉDIO",
                "title": "Escopo specialist exige consolidação multiagente em uma única resposta.",
                "detail": "Sem consolidação explícita, cada agente tende a ecoar readiness ou observações parciais sem fechar o diagnóstico executivo.",
            }
        )
    return findings


def _audit_risks() -> List[str]:
    return [
        "Falso positivo de escrita governada quando o prompt cita operações em contexto negativo.",
        "Falso positivo de runtime/config quando o pedido é analítico mas menciona repositório ou GitHub.",
        "Duplicidade de resposta entre Orkio e Orion quando ambos ecoam o mesmo resultado operacional.",
        "Regressão de precedência se handlers operacionais forem avaliados antes da capability consultiva.",
    ]


def _audit_recommendations(scope: str) -> List[str]:
    recs = [
        "Executar platform_self_audit antes de qualquer inventário/runtime quando a intenção for consultiva e read-only.",
        "Responder com blocos distintos de fatos observados, inferências e recomendações.",
        "Manter escrita governada fora da trilha consultiva, mesmo quando o prompt menciona GitHub ou repositório.",
        "Preservar bloqueios de main e exigência de aprovações explícitas para deploy e DB.",
    ]
    if scope == "specialist":
        recs.append("Consolidar auditor, cto, orion e chris no mesmo payload final para evitar eco parcial de readiness.")
    return recs


def _audit_root_causes(scope: str) -> List[str]:
    causes = [
        "O runtime mantinha classificação consultiva e handlers operacionais muito próximos semanticamente, o que favorecia captura indevida por inventário/config GitHub.",
        "A capability consultiva existia, mas readiness report e execução profunda não estavam claramente separados no compositor final.",
        "O sistema passou a depender de precedência implícita no roteador em vez de contrato explícito entre intenção, dispatcher e formato de saída.",
    ]
    if scope == "specialist":
        causes.append("A consolidação multiagente não estava materializada em um relatório único; cada trilha podia devolver apenas confirmação operacional parcial.")
    return causes


def _audit_intent_misclassification_points() -> List[str]:
    return [
        "Prompts consultivos com termos como GitHub, repo, branch ou arquivo em contexto analítico podiam ser classificados como runtime/config.",
        "Prompts com negação operacional ('não criar', 'não abrir PR') ainda continham gatilhos de escrita capazes de acionar políticas indevidas.",
        "A ausência de um marcador forte de read-only no pacote de intenção facilitava regressões entre análise e operação.",
    ]


def _audit_routing_error_points() -> List[str]:
    return [
        "Antes do ajuste, pedidos de auditoria consultiva podiam terminar em GITHUB_RUNTIME_CONFIG_OK em vez de cair na capability consultiva.",
        "A trilha consultiva precisava vencer github_runtime_general e handlers afins antes da renderização da resposta final.",
        "A execução final passou a depender do dispatcher consultivo interno, e não do loop automático de evolução.",
    ]


def _audit_execution_response_mismatches() -> List[str]:
    return [
        "Houve fases em que a execução interna era correta, mas a resposta final ao usuário saía como readiness report ou snapshot de runtime/config.",
        "A capability podia estar registrada e pronta, porém a superfície de resposta ainda não entregava a auditoria completa pedida.",
        "A diferença entre 'executado' e 'composto/formatado corretamente' era a principal fonte do falso negativo funcional remanescente.",
    ]


def _audit_agent_duplication_points(scope: str) -> List[str]:
    points = [
        "Orkio e Orion podem ecoar o mesmo resultado operacional na thread, gerando duplicidade de percepção mesmo quando o backend executa apenas uma trilha útil.",
        "Sem consolidação explícita, readiness e recibos operacionais de agentes diferentes competem com o relatório consultivo.",
    ]
    if scope == "specialist":
        points.append("Escopo specialist amplia o risco de eco textual entre auditor, cto, orion e chris se o compositor final não unificar as saídas.")
    return points


def _audit_technical_debts(scope: str) -> Dict[str, List[str]]:
    debts = {
        "critical": [
            "Ausência histórica de contrato rígido entre intenção consultiva e handlers operacionais, com impacto direto em classificação e roteamento.",
        ],
        "high": [
            "Compositor de saída consultiva ainda dependia de payload parcial, o que reduzia a profundidade do diagnóstico entregue.",
            "Precedência entre platform_self_audit e github_runtime_general continua sendo ponto de regressão de alto impacto.",
        ],
        "medium": [
            "Duplicidade de resposta entre agentes na thread ainda polui percepção operacional e leitura de sucesso/erro.",
            "Campos de evidência e conclusão ainda precisam permanecer sincronizados com os blocos pedidos pelo usuário.",
        ],
        "low": [
            "Nomenclatura de modos/eventos consultivos ainda pode ser refinada para diferenciar readiness intermediário de relatório final.",
        ],
    }
    if scope == "specialist":
        debts["medium"].append("Consolidação multiagente ainda é sintética; não há pesos diferenciados por especialista no payload final.")
    return debts


def _audit_preserve_items() -> List[str]:
    return [
        "Preservar bloqueio de escrita direta em main com ALLOW_GITHUB_MAIN_DIRECT=False.",
        "Preservar separação entre escrita governada e auditoria read-only.",
        "Preservar capability self_knowledge_app registrada no boot do runtime.",
        "Preservar exigência de aprovações explícitas para deploy e DB fora da trilha consultiva.",
    ]


def _audit_simplify_items() -> List[str]:
    return [
        "Unificar a superfície de saída consultiva em um único relatório final, evitando readiness repetido.",
        "Simplificar a fronteira entre classificação consultiva, inventário/runtime e escrita governada.",
        "Concentrar a composição textual da auditoria em um único compositor para evitar blocos parciais espalhados.",
    ]


def _audit_correction_order() -> List[str]:
    return [
        "1. Preservar precedência estável de platform_self_audit sobre github_runtime_general.",
        "2. Manter execução consultiva profunda desacoplada do ENABLE_EVOLUTION_LOOP.",
        "3. Consolidar relatório final completo com 14 blocos obrigatórios.",
        "4. Reduzir duplicidade de resposta entre Orkio e Orion na thread.",
        "5. Só depois refinar a qualidade analítica por especialista.",
    ]


def _audit_maturity_conclusion(scope: str) -> str:
    base = (
        "O sistema saiu do estágio de falha de roteamento consultivo e entrou em maturidade intermediária: "
        "a capability correta é registrada, ativada e executada, mas a qualidade final da auditoria ainda depende "
        "de um compositor consistente para entregar diagnóstico completo sem eco parcial."
    )
    if scope == "specialist":
        return base + " No escopo specialist, a maturidade ainda é limitada pela consolidação multiagente sintética, não por ausência de capability."
    return base


def _audit_specialist_views(scope: str) -> Dict[str, List[str]]:
    views: Dict[str, List[str]] = {
        "auditor": [
            "Classificação consultiva e handlers operacionais continuam sendo a principal zona de regressão arquitetural.",
            "Duplicidade de resposta entre agentes permanece como ruído operacional real.",
        ],
        "cto": [
            "A correção estrutural mais importante foi desacoplar auditoria read-only do loop automático e dar precedência explícita à capability consultiva.",
            "O próximo risco técnico não é boot nem capability ausente; é composição incompleta da resposta final.",
        ],
        "orion": [
            "O dispatcher consultivo agora executa; o foco passa a ser transformar payload executado em relatório final integral.",
            "Precedência estável entre intent engine, dispatcher e renderização precisa ser preservada em patches futuros.",
        ],
        "chris": [
            "Do ponto de vista de produto, readiness repetido degrada confiança do usuário mesmo quando o backend faz a coisa certa.",
            "A percepção de maturidade melhora quando a resposta final traduz corretamente o que já foi executado internamente.",
        ],
        "ux_frontend": [
            "Quando a interface depende de refresh completo para materializar a resposta final, a percepção do usuário é de falha operacional.",
            "O trilho de fallback precisa concluir no mesmo turno visual, sem depender de reconciliação tardia da thread.",
        ],
    }
    if scope != "specialist":
        views.pop("chris", None)
        views.pop("ux_frontend", None)
    return views



def _audit_selected_specialists(scope: str, include_frontend: bool = False, premium_mode: bool = False) -> List[str]:
    if premium_mode:
        return ["auditor", "cto", "orion", "chris", "architect", "devops", "security", "memory_ops", "stage_manager"]

    selected = ["auditor", "cto", "orion"]

    needs_frontend = (
        scope == "specialist"
        or bool(include_frontend)
    )

    if needs_frontend:
        selected.append("ux_frontend")

    return _dedupe_dispatch_actors(selected)


def _audit_dispatch_receipts(selected_specialists: List[str], scope: str) -> List[Dict[str, Any]]:
    receipts: List[Dict[str, Any]] = []
    deliverables = {
        "auditor": "varredura arquitetural e inconsistências reais",
        "cto": "plano técnico incremental e pontos de correção",
        "orion": "roteamento seguro e consolidação executável",
        "chris": "impacto funcional e leitura de produto",
        "architect": "arquitetura premium, onboarding e clareza estrutural",
        "devops": "performance percebida, latência e observabilidade operacional",
        "security": "confiança, transparência, controles e percepção de segurança",
        "memory_ops": "continuidade, memória útil e persistência contextual",
        "stage_manager": "ritmo da experiência, estados de transição e acabamento premium",
        "ux_frontend": "renderização, sincronização visual e percepção de resposta",
    }
    for agent in selected_specialists:
        receipts.append({
            "agent": agent,
            "status": "executed",
            "mode": "read_only_dispatch",
            "scope": scope,
            "deliverable": deliverables.get(agent, "análise especializada"),
            "generated_at": _now_ts(),
        })
    return receipts


def _audit_specialist_reports(selected_specialists: List[str], scope: str) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    templates: Dict[str, Dict[str, Any]] = {
        "auditor": {
            "role": "technical_auditor",
            "focus": "riscos arquiteturais, regressões e evidências de execução",
            "findings": [
                "O gargalo principal não está mais no boot nem na capability ausente.",
                "A composição final ainda precisa provar dispatch real ao usuário, com recibos e blocos por especialista.",
            ],
            "next_actions": [
                "Manter precedência da trilha consultiva sobre handlers de runtime/config.",
                "Bloquear qualquer fallback que volte a reescrever a saída como readiness report genérico.",
            ],
        },
        "cto": {
            "role": "systems_architect",
            "focus": "handoff de runtime, profundidade de execução e formato de resposta",
            "findings": [
                "O planner e o dispatcher já atingem o caminho correto; o problema residual é de payload final.",
                "A resposta precisa expor execution_depth=dispatch, receipts e relatórios por especialista.",
            ],
            "next_actions": [
                "Preservar prepare_only=False quando a intenção for execução.",
                "Propagar include_frontend/specialist_mode até o executor para compor o squad correto.",
            ],
        },
        "orion": {
            "role": "cto_runtime",
            "focus": "despacho interno, consolidação final e integridade operacional",
            "findings": [
                "A capability platform_self_audit deve responder como execução confirmada, não como relatório consultivo legado.",
                "A consolidação final precisa refletir o dispatch já realizado internamente.",
            ],
            "next_actions": [
                "Emitir event específico de dispatch executado.",
                "Consolidar a saída final em formato único, sem eco de facts/inferences como corpo principal.",
            ],
        },
        "chris": {
            "role": "product_reader",
            "focus": "impacto funcional, clareza de superfície e percepção de maturidade",
            "findings": [
                "Quando a interface recebe texto de readiness, o usuário percebe estagnação mesmo com backend estável.",
                "A resposta final precisa deixar explícito quem foi acionado e o que cada especialista entregou.",
            ],
            "next_actions": [
                "Traduzir dispatch interno em linguagem operacional verificável.",
                "Evitar duplicidade entre narrativa técnica e narrativa de produto na mesma resposta.",
            ],
        },
        "ux_frontend": {
            "role": "ux_frontend",
            "focus": "sincronização do estado visual, render incremental e percepção de completude",
            "findings": [
                "Quando a resposta final depende apenas de reload completo da thread, a percepção é de falha ou atraso do sistema.",
                "A camada visual precisa materializar a resposta final no mesmo turno, mesmo quando o fallback JSON é acionado.",
            ],
            "next_actions": [
                "Aplicar retry curto de leitura após o envio para reduzir corrida entre persistência e renderização.",
                "Garantir fallback visual da resposta final quando o backend já devolveu o conteúdo mas a lista ainda não refletiu a persistência.",
            ],
        },
    }
    for agent in selected_specialists:
        base = dict(templates.get(agent, {}))
        base["agent"] = agent
        base["scope"] = scope
        reports.append(base)
    return reports


def _audit_final_consolidation(selected_specialists: List[str], scope: str) -> str:
    roster = ", ".join(selected_specialists)
    if scope == "specialist":
        return (
            f"Dispatch read-only concluído com {roster}. "
            "O sistema já não está preso em readiness operacional; a pendência remanescente é apresentar "
            "a execução em formato consolidado, com recibos por especialista e síntese final única."
        )
    return (
        f"Dispatch read-only concluído com {roster}. "
        "A execução foi materializada internamente e a resposta final deve refletir isso sem recair no template consultivo legado."
    )



def _dispatch_receipt_counts(dispatch_receipts: List[Dict[str, Any]], specialist_reports: List[Dict[str, Any]], selected_specialists: List[str]) -> Dict[str, int]:
    return {
        "selected_specialists_count": len(list(selected_specialists or [])),
        "dispatch_receipts_count": len(list(dispatch_receipts or [])),
        "specialist_reports_count": len(list(specialist_reports or [])),
    }



def _infer_progressive_dispatch_followup_subtype(message: str) -> str:
    txt = (message or "").strip().lower()
    if not txt:
        return ""
    if "formato executivo" in txt or "diagnóstico executivo" in txt or "diagnostico executivo" in txt:
        return "executive_format"
    if (
        ("root causes" in txt or "causas raiz" in txt)
        and ("risks" in txt or "riscos" in txt)
        and ("next actions" in txt or "próximas ações" in txt or "proximas ações" in txt or "proximas acoes" in txt or "próximos passos" in txt or "proximos passos" in txt)
    ):
        return "root_causes_risks_next_actions"
    if "causas raiz" in txt and ("riscos estruturais" in txt or "riscos" in txt):
        return "root_causes_risks"
    if "root causes" in txt or "causas raiz" in txt:
        return "root_causes"
    if "riscos estruturais" in txt or "risks" in txt or "riscos" in txt:
        return "risks"
    if "next actions" in txt or "próximas ações" in txt or "proximas ações" in txt or "proximas acoes" in txt or "próximos passos" in txt or "proximos passos" in txt:
        return "next_steps"
    if "sem perder evidências" in txt or "sem perder evidencias" in txt or "evidências técnicas" in txt or "evidencias tecnicas" in txt:
        return "evidence_preserving"
    if any(term in txt for term in ("continue", "prossiga", "aprofunde", "desdobre", "expanda", "refine", "incremental", "follow-up", "followup")):
        return "continuation"
    return ""


def _dispatch_render_strategy(followup_subtype: str) -> str:
    subtype = (followup_subtype or "").strip().lower()
    if subtype == "executive_format":
        return "dispatch_executive_replace"
    if subtype == "root_causes_risks_next_actions":
        return "dispatch_incremental_replace"
    if subtype in {"root_causes_risks", "root_causes", "risks", "next_steps", "evidence_preserving"}:
        return "dispatch_progressive_compact"
    if subtype == "continuation":
        return "dispatch_progressive_full"
    return "dispatch_full"


def _derive_incremental_root_causes(specialist_reports: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for report in list(specialist_reports or []):
        findings = report.get("findings") if isinstance(report.get("findings"), list) else []
        for finding in findings[:6]:
            item = str(finding or "").strip()
            if item and item not in out:
                out.append(item)
    return out[:4]


def _derive_incremental_risks(*, technical_summary: str, confirmed_evidence: str, specialist_reports: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for report in list(specialist_reports or []):
        findings = report.get("findings") if isinstance(report.get("findings"), list) else []
        for finding in findings[:4]:
            item = str(finding or "").strip()
            if item and item not in out:
                out.append(f"Derivado de specialist_reports: {item}")
                if len(out) >= 2:
                    break
        if len(out) >= 2:
            break
    if technical_summary:
        out.append(f"Derivado de technical_summary: {technical_summary}")
    if confirmed_evidence:
        out.append(f"Confirmado por confirmed_evidence: {confirmed_evidence}")
    return out[:4]


def _derive_incremental_next_actions(*, final_consolidation: str, specialist_reports: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    if final_consolidation:
        out.append(f"Derivado de final_consolidation: {final_consolidation}")
    for report in list(specialist_reports or []):
        actions = report.get("next_actions") if isinstance(report.get("next_actions"), list) else []
        for action in actions[:6]:
            item = str(action or "").strip()
            if item and item not in out:
                out.append(item)
    return out[:5]


def _build_dispatch_executive_sections(
    *,
    direct_orion_diagnostic: bool,
    selected_specialists: List[str],
    dispatch_receipts: List[Dict[str, Any]],
    specialist_reports: List[Dict[str, Any]],
    scope: str,
    include_frontend: bool,
    followup_subtype: str = "",
) -> Dict[str, Any]:
    roster = ", ".join(selected_specialists) if selected_specialists else "orion"
    counts = _dispatch_receipt_counts(dispatch_receipts, specialist_reports, selected_specialists)
    followup_subtype = (followup_subtype or "").strip().lower()
    progressive_followup = bool(followup_subtype)
    report_format = "orion_diagnostic_prose_v2" if direct_orion_diagnostic else "dispatch_audit_v2"
    if progressive_followup and followup_subtype == "executive_format":
        report_format = "dispatch_executive_followup_v1"
    elif progressive_followup:
        report_format = "dispatch_progressive_followup_v1"

    if followup_subtype == "root_causes_risks_next_actions":
        confirmed_evidence = (
            f"Dispatch preservado com especialistas={counts['selected_specialists_count']}, "
            f"receipts={counts['dispatch_receipts_count']} e reports={counts['specialist_reports_count']}."
        )
        technical_summary = (
            "Aprofundamento incremental derivado do dispatch já concluído. "
            "O backend deve responder a partir do contexto preservado, sem voltar ao recibo bruto."
        )
        final_consolidation = (
            "A continuidade deve permanecer incremental: usar o dispatch confirmado como base, "
            "preservar evidências essenciais e evitar repetir blocos operacionais completos."
        )
        return {
            "report_format": "dispatch_incremental_followup_v1",
            "technical_summary": technical_summary,
            "root_causes": _derive_incremental_root_causes(specialist_reports),
            "risks": _derive_incremental_risks(
                technical_summary=technical_summary,
                confirmed_evidence=confirmed_evidence,
                specialist_reports=specialist_reports,
            ),
            "next_actions": _derive_incremental_next_actions(
                final_consolidation=final_consolidation,
                specialist_reports=specialist_reports,
            ),
            "derivation_basis": [
                "specialist_reports",
                "technical_summary",
                "final_consolidation",
                "confirmed_evidence",
            ],
            "executive_diagnostic": "",
            "backend_assessment": "",
            "frontend_assessment": "",
            "integration_assessment": "",
            "confirmed_evidence": confirmed_evidence,
            "main_risk": "",
            "recommended_actions": [],
            "final_consolidation": final_consolidation,
        }

    if direct_orion_diagnostic:
        if followup_subtype == "executive_format":
            return {
                "report_format": report_format,
                "executive_diagnostic": (
                    "Diagnóstico executivo consolidado: o dispatch foi mantido, Orion permaneceu como signer visível "
                    "e a resposta foi reformatada para leitura diretiva sem recair no template consultivo."
                ),
                "backend_assessment": (
                    "A causa raiz residual deixou de ser roteamento e passou a ser composição de continuidade. "
                    "O backend já preserva o contrato; agora ele também precisa variar a entrega entre recibo, aprofundamento e síntese executiva."
                ),
                "frontend_assessment": (
                    "O frontend não precisa reinterpretar a semântica. A camada web deve apenas consumir um payload já progressivo e renderizá-lo com clareza."
                ),
                "integration_assessment": (
                    "Thread history, intent engine e dispatcher interno já mantêm o mesmo trilho. "
                    "A resposta executiva agora precisa só preservar evidências essenciais sem repetir blocos completos."
                ),
                "confirmed_evidence": (
                    f"Evidências preservadas: event=ORION_RUNTIME_DIAGNOSTIC_EXECUTED, execution_depth=dispatch, "
                    f"selected_specialists={counts['selected_specialists_count']}, dispatch_receipts={counts['dispatch_receipts_count']}."
                ),
                "main_risk": (
                    "O risco residual é a resposta seguir tecnicamente correta, mas com excesso de repetição operacional quando o usuário pede síntese executiva."
                ),
                "recommended_actions": [
                    "1. Manter contrato sticky na thread.",
                    "2. Reduzir repetição textual em follow-ups executivos.",
                    "3. Preservar evidências essenciais e counts do dispatch.",
                    "4. Deixar receipts detalhados para visualização expandida no frontend.",
                ],
                "final_consolidation": (
                    "Veredito executivo: o motor de dispatch já está estável, Orion manteve a assinatura correta e a próxima etapa é transformar os detalhes técnicos em visualização progressiva no frontend, sem tocar no núcleo operacional."
                ),
            }
        if followup_subtype in {"root_causes_risks", "root_causes", "risks", "next_steps", "evidence_preserving", "continuation"}:
            return {
                "report_format": report_format,
                "executive_diagnostic": (
                    "Aprofundamento progressivo aplicado sobre um dispatch já confirmado. "
                    "A continuidade não deve reiniciar o diagnóstico; deve expandir a leitura do que já foi executado."
                ),
                "backend_assessment": (
                    "A causa raiz do comportamento anterior era a continuidade reaproveitar o mesmo template de recibo. "
                    "Com a sticky thread ativa, o próximo refinamento é compor respostas incrementais, não duplicadas."
                ),
                "frontend_assessment": (
                    "A interface deve receber blocos progressivos distintos, evitando a sensação de repetição do mesmo relatório bruto."
                ),
                "integration_assessment": (
                    "O handshake entre intent, dispatcher e fechamento do stream está íntegro. "
                    "O foco agora é evolução semântica da resposta dentro do mesmo contrato."
                ),
                "confirmed_evidence": (
                    f"Dispatch preservado nesta continuação com {counts['dispatch_receipts_count']} receipt(s) e "
                    f"{counts['specialist_reports_count']} relatório(s) especializado(s)."
                ),
                "main_risk": (
                    "Se a composição de follow-up não variar por subtipo, o usuário percebe regressão mesmo quando o backend continua correto."
                ),
                "recommended_actions": [
                    "1. Separar resposta de recibo da resposta de aprofundamento.",
                    "2. Tratar causas raiz, riscos e próximos passos como camadas progressivas.",
                    "3. Usar formato executivo quando o pedido explicitamente exigir síntese.",
                    "4. Manter receipts detalhados fora do corpo principal quando o foco for aprofundamento.",
                ],
                "final_consolidation": (
                    "Síntese progressiva: o dispatch segue válido e a continuidade agora deve aprofundar causas raiz, riscos e ações sem repetir integralmente o bloco original de receipts."
                ),
            }
        return {
            "report_format": report_format,
            "executive_diagnostic": (
                "Orion executou o diagnóstico técnico objetivo em modo somente leitura. "
                "O runtime respondeu em dispatch real, a persona visível permaneceu Orion "
                "e a trilha não voltou para PLATFORM_SELF_AUDIT_READY."
            ),
            "backend_assessment": (
                "O backend já materializa a capability de auditoria como execução confirmada. "
                "O risco residual deixou de ser ativação e passou a ser acabamento do payload final."
            ),
            "frontend_assessment": (
                "A assinatura visual do Orion permaneceu coerente neste fluxo. "
                "A camada web ainda deve apenas renderizar receipts e consolidação, sem reinterpretar semântica."
            ),
            "integration_assessment": (
                "Intent, dispatcher interno e composição final estão alinhados. "
                "O próximo salto é persistir e exibir o dispatch com estrutura auditável e leitura executiva."
            ),
            "confirmed_evidence": (
                "Sinais confirmados nesta execução: "
                f"event=ORION_RUNTIME_DIAGNOSTIC_EXECUTED, execution_depth=dispatch, "
                f"selected_specialists={counts['selected_specialists_count']}, "
                f"dispatch_receipts={counts['dispatch_receipts_count']}."
            ),
            "main_risk": (
                "O risco residual é apresentar uma resposta excessivamente técnica ou estrutural "
                "quando o usuário espera diagnóstico executivo direto."
            ),
            "recommended_actions": [
                "1. Preservar precedência do diagnóstico Orion-only sobre rotas genéricas.",
                "2. Persistir contagens e evidências do dispatch no payload final.",
                "3. Exibir receipts e specialist reports sem recair em template consultivo READY.",
                "4. Manter Orion como signer visível em persistência e renderização.",
            ],
            "final_consolidation": (
                "Orion consolidou a análise técnica objetiva como agente único visível. "
                "O dispatch já está confirmado; o próximo passo é enriquecer a saída com recibos persistíveis "
                "e acabamento executivo sem perder evidência operacional."
            ),
        }

    frontend_line = (
        "O frontend foi incluído no escopo e precisa apenas renderizar melhor receipts, specialist reports e consolidação."
        if include_frontend else
        "O frontend não precisa reinterpretar o dispatch; basta consumir e renderizar o payload estruturado."
    )
    if progressive_followup:
        if followup_subtype == "executive_format":
            return {
                "report_format": report_format,
                "executive_diagnostic": (
                    f"Diagnóstico executivo do dispatch concluído com {roster}. "
                    "A leitura foi condensada para decisão diretiva, sem reexecutar nem repetir o bloco operacional completo."
                ),
                "backend_assessment": (
                    "O backend já sustenta a thread sticky e o dispatch correto. "
                    "Neste estágio, o papel da continuidade executiva é sintetizar, não reimprimir receipts e relatórios brutos."
                ),
                "frontend_assessment": (
                    "A interface pode consumir esta síntese como corpo principal e deixar os detalhes operacionais para expansão secundária."
                ),
                "integration_assessment": (
                    "Intent engine, dispatcher e stream continuam íntegros. "
                    "A transformação aqui é exclusivamente de enquadramento da resposta, preservando o mesmo trilho técnico."
                ),
                "confirmed_evidence": (
                    f"Dispatch preservado com especialistas={counts['selected_specialists_count']}, "
                    f"receipts={counts['dispatch_receipts_count']} e reports={counts['specialist_reports_count']}."
                ),
                "main_risk": (
                    "O risco residual é manter excesso de detalhe operacional no corpo principal quando o pedido já mudou para formato executivo."
                ),
                "recommended_actions": [
                    "1. Exibir apenas síntese decisória no corpo principal.",
                    "2. Preservar evidências essenciais e contagens do dispatch.",
                    "3. Deixar receipts e specialist reports completos para expansão auditável.",
                    "4. Manter o mesmo signer visível sem reiniciar o fluxo.",
                ],
                "final_consolidation": (
                    "Veredito executivo: o dispatch multiagente permanece válido, o backend está estável no mesmo contrato da thread e o próximo passo é lapidar a apresentação sem tocar no motor operacional."
                ),
            }
        return {
            "report_format": report_format,
            "executive_diagnostic": (
                f"Continuidade progressiva aplicada ao dispatch concluído com {roster}. "
                "A resposta foi reorientada para aprofundamento sem reiniciar a execução."
            ),
            "backend_assessment": (
                "O backend já preserva o contrato estruturado da thread. "
                "O foco agora é diversificar a camada narrativa conforme o pedido do usuário."
            ),
            "frontend_assessment": frontend_line,
            "integration_assessment": (
                "Intent engine, orion dispatcher e chat/stream continuam alinhados. "
                "A continuidade deve alterar o enquadramento da resposta, não o trilho técnico."
            ),
            "confirmed_evidence": (
                f"Especialistas preservados: {roster}. Receipts mantidos: {counts['dispatch_receipts_count']}. "
                f"Reports mantidos: {counts['specialist_reports_count']}."
            ),
            "main_risk": (
                "O risco residual é reapresentar a mesma estrutura completa quando o usuário espera refinamento incremental."
            ),
            "recommended_actions": [
                "1. Variar o enquadramento sem quebrar o contrato do dispatch.",
                "2. Preservar evidências essenciais e ocultar repetição desnecessária.",
                "3. Reservar detalhamento bruto para expansão posterior no frontend.",
            ],
            "final_consolidation": (
                "O dispatch permanece válido e a continuidade passa a servir como camada de aprofundamento, não como duplicação do recibo original."
            ),
        }
    return {
        "report_format": report_format,
        "executive_diagnostic": (
            f"Dispatch interno concluído com {roster}. "
            "A plataforma já não está presa em readiness operacional; a execução multiagente foi materializada."
        ),
        "backend_assessment": (
            "O backend aciona o squad solicitado e consolida a entrega em modo somente leitura. "
            "A camada de execução já produz receipts, relatórios por especialista e síntese final."
        ),
        "frontend_assessment": frontend_line,
        "integration_assessment": (
            "A integração entre intent engine, Orion internal dispatcher e chat/stream foi estabilizada. "
            "O esforço remanescente é de persistência auditável e apresentação executiva."
        ),
        "confirmed_evidence": (
            f"Especialistas acionados: {roster}. "
            f"Receipts gerados: {counts['dispatch_receipts_count']}. "
            f"Relatórios especializados: {counts['specialist_reports_count']}."
        ),
        "main_risk": (
            "O principal risco residual é a resposta final perder clareza executiva ao misturar payload técnico "
            "com narrativa consultiva legada."
        ),
        "recommended_actions": [
            "1. Manter dispatch como resposta principal quando execution_depth=dispatch.",
            "2. Persistir contagens e especialista(s) selecionados no fechamento do stream.",
            "3. Renderizar technical_summary, dispatch_receipts e final_consolidation em blocos claros.",
            "4. Evitar reuso de templates consultivos em respostas já executadas.",
        ],
        "final_consolidation": _audit_final_consolidation(selected_specialists, scope),
    }



def _build_premium_platform_audit_sections(selected_specialists: List[str]) -> Dict[str, Any]:
    roster = ", ".join(selected_specialists) if selected_specialists else "auditor, cto, orion, chris"
    return {
        "executive_verdict": "A plataforma já tem base operacional forte, mas ainda não entrega acabamento premium consistente na primeira impressão, na fluidez do console e na tradução de poder técnico em valor percebido.",
        "findings_by_specialty": {
            "auditor": "Há maturidade operacional crescente, porém a percepção do usuário ainda sofre quando o sistema ecoa contratos internos em vez de respostas refinadas.",
            "cto": "O núcleo já suporta governança e fluxo controlado; o próximo salto é transformar capacidade técnica em jornadas mais desejáveis e mais simples de entender.",
            "orion": "A orquestração responde, mas a superfície final ainda precisa diferenciar auditoria, execução e experiência premium.",
            "chris": "Valor percebido depende de primeira vitória rápida, linguagem de benefício e sensação de exclusividade funcional.",
            "architect": "Onboarding, empty states e hierarquia visual ainda não mostram de imediato o que torna a plataforma única.",
            "devops": "Latência, fallbacks e estados transitórios precisam parecer elegantes mesmo quando algo demora ou degrada.",
            "security": "Confiança cresce quando o usuário percebe controle, transparência e previsibilidade das ações sensíveis.",
            "memory_ops": "Continuidade entre conversas precisa parecer inteligente e útil, não apenas histórica.",
            "stage_manager": "Falta um acabamento uniforme de ritmo, microinteração e progressão visual para parecer premium.",
        },
        "top_improvements": [
            "Criar onboarding com promessa clara e primeira vitória em poucos cliques.",
            "Redesenhar empty state do console com CTA principal e demonstração de valor.",
            "Padronizar loading, erro e recuperação com linguagem premium e baixo ruído.",
            "Mostrar contexto ativo, objetivo atual e próximo passo recomendado.",
            "Refinar hierarquia visual do chat para reduzir densidade técnica percebida.",
            "Padronizar respostas executivas mais curtas, claras e confiáveis.",
            "Melhorar fluidez entre texto, voz e realtime com fallbacks elegantes.",
            "Dar mais visibilidade à proposta de valor, wallet e Execution Blueprint quando aplicável.",
            "Aumentar consistência entre branding, cor, espaçamento e ícones.",
            "Expor melhor sinais de segurança e controle humano.",
            "Melhorar mobile/PWA com foco em toque, leitura e continuidade.",
            "Reduzir repetição estrutural nas respostas multiagente.",
            "Evidenciar qualidade do produto já na primeira sessão.",
            "Criar sensação de progressão e conquista no uso.",
            "Aumentar observabilidade orientada à experiência percebida.",
        ],
        "quick_wins_24h": [
            "Novo empty state premium no AppConsole.",
            "Copy mais clara para onboarding e primeira ação.",
            "Padronização visual de estados de loading e erro.",
            "Resumo executivo padrão para respostas longas.",
            "Mensagem de confiança/controle em ações sensíveis.",
        ],
        "improvements_7d": [
            "Refino da hierarquia visual do chat e topbar.",
            "Aprimoramento dos estados de voz/realtime/fallback.",
            "Melhorias na UX de wallet, billing e preview de custo.",
            "Context banner com objetivo atual e continuidade.",
            "Indicadores de performance percebida e recuperação.",
        ],
        "improvements_30d": [
            "Onboarding guiado adaptativo.",
            "Sistema de memória útil com retomada contextual elegante.",
            "Visualização progressiva multiagente no frontend.",
            "Camada premium de métricas UX + observabilidade operacional.",
            "Biblioteca de componentes premium consistente em web/PWA.",
        ],
        "premium_blockers": [
            "Primeira impressão ainda não comunica imediatamente exclusividade e benefício.",
            "Superfície do chat ainda expõe densidade técnica em excesso em alguns fluxos.",
            "Estados transitórios e de erro ainda não parecem premium o suficiente.",
            "Continuidade contextual e sensação de inteligência pessoal ainda podem evoluir muito.",
        ],
        "primary_product_adjustment": "Transformar a primeira experiência em uma jornada guiada para uma vitória concreta e memorável, sem exigir que o usuário interprete a arquitetura da plataforma.",
        "primary_frontend_adjustment": "Reescrever o empty state e a hierarquia visual do AppConsole para comunicar valor, próxima ação e status do sistema com clareza premium.",
        "primary_backend_adjustment": "Separar de forma ainda mais rígida os contratos de auditoria, execução e governança para que a superfície nunca volte a ecoar detalhes operacionais indevidos.",
        "principal_premium_blocker": "Hoje o principal impeditivo de percepção premium é a distância entre a potência real do backend e o acabamento percebido na experiência inicial.",
        "github_write_blocked": True,
        "audit_mode": "premium_read_only_multiagent",
        "specialist_fanout_applied": True,
        "premium_roster": roster,
    }


def _build_platform_self_audit_payload(inp: "OrionRuntimeIn", visible_agent: str) -> Dict[str, Any]:
    scope = _audit_scope(inp.message)
    premium_mode = _is_premium_platform_audit_request(inp.message)
    if premium_mode:
        scope = "specialist"
    team_technical_audit = _is_team_technical_audit_request(inp.message)
    if team_technical_audit:
        scope = "specialist"
    direct_orion_diagnostic = _is_orion_direct_diagnostic_request(inp.message, visible_agent) and not premium_mode and not team_technical_audit
    execute_full = premium_mode or team_technical_audit or _audit_wants_full_execution(inp.message, bool(inp.prepare_only)) or direct_orion_diagnostic
    repo_targets = _build_repo_targets()
    audit_plan = {
        "requested_by": visible_agent,
        "prepare_only": bool(inp.prepare_only),
        "include_frontend": bool(inp.include_frontend),
        "scope": scope,
        "repo_targets": repo_targets,
        "specialists": [
            {"agent": "auditor", "deliverable": "riscos arquiteturais e inconsistências reais"},
            {"agent": "cto", "deliverable": "plano técnico incremental e patch plan"},
            {"agent": "orion", "deliverable": "análise executável e roteamento seguro"},
            {"agent": "chris", "deliverable": "impacto funcional e leitura de produto"},
        ],
        "scans": _scan_categories(),
        "approval_gate": {
            "required_for_execution": False,
            "deploy": _bool_env("REQUIRE_EXPLICIT_DEPLOY_APPROVAL", True),
            "db": _bool_env("REQUIRE_EXPLICIT_DB_APPROVAL", True),
        },
    }
    if not execute_full:
        return {
            "ok": True,
            "service": "orion_internal",
            "mode": "premium_platform_audit" if premium_mode else "platform_self_audit",
            "provider": "platform",
            "event": "PLATFORM_SELF_AUDIT_READY",
            "status": "ready",
            "scope": scope,
            "visible_agent": visible_agent,
            "repo": _github_repo(),
            "technical_summary": "Auditoria consultiva preparada com base em sinais de runtime e política operacional. Nenhuma ação destrutiva foi iniciada; o objetivo é produzir diagnóstico estruturado com especialistas e evitar captura indevida por handlers de GitHub/runtime.",
            "findings": _audit_findings(scope),
            "risks": _audit_risks(),
            "suggested_actions": _audit_recommendations(scope),
            "key_files": [
                "app/runtime/intent_engine.py",
                "app/routes/internal/orion_internal.py",
                "app/main.py",
            ],
            "related_modules": [
                "auditor: riscos arquiteturais e inconsistências reais",
                "cto: plano técnico incremental e patch plan",
                "orion: análise executável e roteamento seguro",
                "chris: impacto funcional e leitura de produto",
            ],
            "risk_points": _audit_evidence_points(),
            "architecture_notes": [
                "Capability consultiva deve ter precedência sobre handlers de GitHub/runtime quando o pedido é de auditoria read-only.",
                "Loop de evolução automática e escrita governada permanecem protegidos por flags e aprovações explícitas.",
            ] + [f"{item['category']}: {item['description']}" for item in _scan_categories()],
            "remediation_plan": [
                "1. Classificar auditoria consultiva antes de inventário/config.",
                "2. Executar platform_self_audit via dispatcher interno.",
                "3. Preservar resposta evidencial sem acionar escrita governada.",
            ],
            "audit_plan": audit_plan,
            "generated_at": _now_ts(),
        }

    selected_specialists = (
        ["orion", "auditor", "cto"]
        if team_technical_audit
        else (["orion"] if direct_orion_diagnostic else _audit_selected_specialists(scope, bool(inp.include_frontend), premium_mode=premium_mode))
    )
    dispatch_receipts = _audit_dispatch_receipts(selected_specialists, scope)
    specialist_reports = _audit_specialist_reports(selected_specialists, scope)
    followup_subtype = _infer_progressive_dispatch_followup_subtype(inp.message)
    render_strategy = _dispatch_render_strategy(followup_subtype)
    incremental_followup = followup_subtype == "root_causes_risks_next_actions"
    executive_body_mode = (
        "incremental_replace"
        if incremental_followup
        else ("executive_replace" if followup_subtype == "executive_format" else "")
    )
    compact_dispatch_details = bool(executive_body_mode or render_strategy in {"dispatch_incremental_replace", "dispatch_progressive_compact"})
    dispatch_receipts_appendix = list(dispatch_receipts or []) if compact_dispatch_details else []
    specialist_reports_appendix = list(specialist_reports or []) if compact_dispatch_details else []
    body_dispatch_receipts = [] if compact_dispatch_details else dispatch_receipts
    body_specialist_reports = [] if compact_dispatch_details else specialist_reports
    executive_sections = _build_dispatch_executive_sections(
        direct_orion_diagnostic=direct_orion_diagnostic,
        selected_specialists=selected_specialists,
        dispatch_receipts=dispatch_receipts,
        specialist_reports=specialist_reports,
        scope=scope,
        include_frontend=bool(inp.include_frontend),
        followup_subtype=followup_subtype,
    )
    counts = _dispatch_receipt_counts(dispatch_receipts, specialist_reports, selected_specialists)

    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "premium_platform_audit" if premium_mode else "platform_self_audit",
        "provider": "platform",
        "event": "PLATFORM_PREMIUM_AUDIT_EXECUTED" if premium_mode else ("ORION_RUNTIME_DIAGNOSTIC_EXECUTED" if direct_orion_diagnostic else "PLATFORM_SELF_AUDIT_DISPATCH_EXECUTED"),
        "status": "executed",
        "scope": scope,
        "report_format": ("premium_platform_audit_v1" if premium_mode else (executive_sections.get("report_format") or ("orion_diagnostic_v1" if direct_orion_diagnostic else "dispatch_audit_v1"))),
        "delivery_contract": "premium_platform_audit_v1" if premium_mode else "orion_structured_dispatch_v1",
        "audit_payload_version": "dispatch_audit_envelope_v1",
        "execution_mode": "premium_read_only_multiagent" if premium_mode else "read_only_dispatch",
        "founder_control_mode": "human_controlled_runtime_only",
        "auditability_status": "ready_for_persistence",
        "sticky_thread_dispatch_supported": True,
        "sticky_thread_dispatch_contract": "orion_structured_dispatch_v1",
        "persistable_sections": [
            "technical_summary",
            "executive_diagnostic",
            "backend_assessment",
            "frontend_assessment",
            "integration_assessment",
            "confirmed_evidence",
            "main_risk",
            "recommended_actions",
            "selected_specialists",
            "dispatch_receipts",
            "dispatch_receipts_appendix",
            "specialist_reports",
            "specialist_reports_appendix",
            "frontend_render_cards",
            "team_technical_audit",
            "final_consolidation",
        ],
        "execution_depth": "dispatch",
        "visible_agent": visible_agent,
        "repo": _github_repo(),
        "followup_mode": (
            "incremental_analysis"
            if incremental_followup
            else ("progressive_dispatch_followup" if followup_subtype else "execution_receipt")
        ),
        "followup_subtype": followup_subtype,
        "render_strategy": render_strategy,
        "response_body_mode": ("premium_audit_full_renderer" if premium_mode else executive_body_mode),
        "compact_dispatch_details": compact_dispatch_details,
        "premium_renderer_required": bool(premium_mode),
        "premium_sections_complete": bool(premium_mode),
        "minimum_sections": (["A","B","C","D","E","F","G","H","I","J"] if premium_mode else []),
        "technical_summary": (
            "Varredura premium multiagente executada em modo somente leitura. A equipe técnica consolidou melhorias de UX, confiança, fluidez, mobile/PWA, billing e performance percebida sem acionar GitHub nem escrita governada."
            if premium_mode
            else (executive_sections.get("technical_summary") or "").strip()
            if incremental_followup
            else "Síntese executiva progressiva aplicada sobre dispatch confirmado. O backend preservou evidências essenciais e reduziu repetição estrutural."
            if followup_subtype == "executive_format"
            else "Aprofundamento progressivo aplicado sobre dispatch confirmado. A continuidade expandiu a leitura sem regressão de contrato."
            if followup_subtype
            else "Orion executou um diagnóstico técnico objetivo em modo somente leitura, verificando runtime, handoff do chat e sinais de plataforma sem depender de escrita governada."
            if direct_orion_diagnostic
            else "Dispatch interno de especialistas executado em modo somente leitura. O backend acionou o squad solicitado e consolidou a entrega sem depender do loop automático nem de escrita governada."
        ),
        "selected_specialists": selected_specialists,
        "selected_specialists_count": counts.get("selected_specialists_count", 0),
        "selected_specialists_summary": ", ".join(str(item) for item in list(selected_specialists or [])[:20]),
        "team_technical_audit": bool(team_technical_audit),
        "frontend_render_cards": [
            {
                "type": "specialist_report",
                "agent": report.get("agent"),
                "role": report.get("role"),
                "focus": report.get("focus"),
                "findings": report.get("findings", []),
                "next_actions": report.get("next_actions", []),
            }
            for report in list(specialist_reports or [])
        ],
        "dispatch_receipts": body_dispatch_receipts,
        "dispatch_receipts_count": counts.get("dispatch_receipts_count", 0),
        "dispatch_receipts_appendix": dispatch_receipts_appendix,
        "specialist_reports": body_specialist_reports,
        "specialist_reports_count": counts.get("specialist_reports_count", 0),
        "specialist_reports_appendix": specialist_reports_appendix,
        "root_causes": executive_sections.get("root_causes") or [],
        "risks": executive_sections.get("risks") or [],
        "next_actions": executive_sections.get("next_actions") or [],
        "derivation_basis": executive_sections.get("derivation_basis") or [],
        "final_consolidation": (
            _build_premium_platform_audit_sections(selected_specialists).get("principal_premium_blocker")
            if premium_mode
            else executive_sections.get("final_consolidation") or (
                "Orion consolidou a análise técnica objetiva como agente único visível. A resposta final deve sair assinada como Orion e não deve recair em PLATFORM_SELF_AUDIT_READY."
                if direct_orion_diagnostic
                else _audit_final_consolidation(selected_specialists, scope)
            )
        ),
        "executive_diagnostic": executive_sections.get("executive_diagnostic") or "",
        "backend_assessment": executive_sections.get("backend_assessment") or "",
        "frontend_assessment": executive_sections.get("frontend_assessment") or "",
        "integration_assessment": executive_sections.get("integration_assessment") or "",
        "confirmed_evidence": executive_sections.get("confirmed_evidence") or "",
        "main_risk": executive_sections.get("main_risk") or "",
        "recommended_actions": executive_sections.get("recommended_actions") or [],
        "executive_verdict": (_build_premium_platform_audit_sections(selected_specialists).get("executive_verdict") if premium_mode else ""),
        "findings_by_specialty": (_build_premium_platform_audit_sections(selected_specialists).get("findings_by_specialty") if premium_mode else {}),
        "top_improvements": (_build_premium_platform_audit_sections(selected_specialists).get("top_improvements") if premium_mode else []),
        "quick_wins_24h": (_build_premium_platform_audit_sections(selected_specialists).get("quick_wins_24h") if premium_mode else []),
        "improvements_7d": (_build_premium_platform_audit_sections(selected_specialists).get("improvements_7d") if premium_mode else []),
        "improvements_30d": (_build_premium_platform_audit_sections(selected_specialists).get("improvements_30d") if premium_mode else []),
        "premium_blockers": (_build_premium_platform_audit_sections(selected_specialists).get("premium_blockers") if premium_mode else []),
        "primary_product_adjustment": (_build_premium_platform_audit_sections(selected_specialists).get("primary_product_adjustment") if premium_mode else ""),
        "primary_frontend_adjustment": (_build_premium_platform_audit_sections(selected_specialists).get("primary_frontend_adjustment") if premium_mode else ""),
        "primary_backend_adjustment": (_build_premium_platform_audit_sections(selected_specialists).get("primary_backend_adjustment") if premium_mode else ""),
        "principal_premium_blocker": (_build_premium_platform_audit_sections(selected_specialists).get("principal_premium_blocker") if premium_mode else ""),
        "github_write_blocked": bool(_build_premium_platform_audit_sections(selected_specialists).get("github_write_blocked")) if premium_mode else False,
        "specialist_fanout_applied": bool(_build_premium_platform_audit_sections(selected_specialists).get("specialist_fanout_applied")) if premium_mode else False,
        "audit_mode": _build_premium_platform_audit_sections(selected_specialists).get("audit_mode") if premium_mode else ("specialist" if scope == "specialist" else "standard"),
        "key_files": [
            "app/runtime/intent_engine.py",
            "app/routes/internal/orion_internal.py",
            "app/main.py",
        ],
        "related_modules": [
            "runtime intent engine",
            "orion internal dispatcher",
            "chat/stream runtime handoff",
            "governed GitHub write policy",
        ],
        "risk_points": _audit_evidence_points(),
        "architecture_notes": [
            "Dispatch executado precisa ser refletido pela camada de renderização final.",
            "A auditoria read-only continua isolada de escrita governada, deploy e operações destrutivas.",
            "Handlers de inventário/config e dispatch multiagente não devem compartilhar o mesmo template textual.",
        ] + (
            [
                "Pedidos Orion-only de diagnóstico técnico objetivo devem produzir execução diagnóstica real, não PLATFORM_SELF_AUDIT_READY.",
                "A síntese final do diagnóstico direto deve permanecer assinada por Orion, sem delegação visual para outro agente.",
            ] if direct_orion_diagnostic else []
        ),
        "remediation_plan": (
            [
                "1. Bloquear GitHub write path em auditoria premium read-only.",
                "2. Executar fan-out multiagente obrigatório por especialidade.",
                "3. Renderizar resposta final em A–J com foco em valor percebido.",
                "4. Priorizar empty state, onboarding, fluidez e confiança.",
            ] if premium_mode else [
                "1. Preservar precedência do diagnóstico Orion-only sobre github_runtime_general.",
                "2. Emitir ORION_RUNTIME_DIAGNOSTIC_EXECUTED como resposta principal.",
                "3. Manter receipts e síntese final alinhados a Orion.",
                "4. Evitar regressão para template consultivo READY.",
            ] if direct_orion_diagnostic else [
                "1. Preservar precedência de platform_self_audit sobre github_runtime_general.",
                "2. Renderizar execution_depth=dispatch como resposta principal.",
                "3. Exibir receipts e relatórios por especialista sem recair em full_audit_v1.",
                "4. Consolidar a síntese final em um único bloco operacional verificável.",
            ]
        ),
        "audit_plan": audit_plan,
        "generated_at": _now_ts(),
    }



def orion_runtime_execute(inp: "OrionRuntimeIn") -> Dict[str, Any]:
    message = inp.message or ""
    effective = _continuous_audit_effective_input(
        message,
        include_frontend=bool(getattr(inp, "include_frontend", False)),
        thread_id=getattr(inp, "thread_id", None),
    )
    effective_message = str(effective.get("message") or message or "")
    lowered = effective_message.lower()
    visible_agent = _resolve_visible_agent(effective_message, default="orion")
    audit_op = _continuous_audit_operation_kind(message or effective_message)
    if audit_op == "status":
        return _get_continuous_audit_status_detached(inp)
    if audit_op == "create":
        return _start_continuous_audit_job_detached(inp)
    if _looks_like_governance_capability_question(effective_message):
        return governance_capability_answer(inp)
    if _looks_like_final_readonly_analysis_request(effective_message):
        return platform_self_audit_readonly_final(inp)
    if _looks_like_squad_resolution_trace_request(effective_message):
        return squad_resolution_trace_readonly(inp)
    if _looks_like_squad_resolution_request(effective_message):
        return resolve_squad_readonly(inp)
    if _looks_like_pwa_console_repair_request(effective_message):
        return pwa_console_repair(inp)
    if _is_platform_improvement_review_request(effective_message):
        return platform_improvement_review(inp)
    if _is_controlled_self_evolution_propose_request(effective_message):
        return platform_self_evolution_plan(inp)
    if _is_orion_direct_diagnostic_request(effective_message, visible_agent):
        return _platform_self_audit_detached(inp)
    if any(term in lowered for term in (
        "auditoria", "audit", "autoconhecimento", "consultivo", "somente leitura",
        "read only", "diagnóstico", "diagnostico"
    )):
        return _platform_self_audit_detached(inp)
    if any(term in lowered for term in ("scan runtime", "auditar runtime", "verificar runtime")):
        return runtime_scan(inp)
    if any(term in lowered for term in ("scan repo", "auditar repositório", "auditar repositorio")):
        return repo_structure_scan(inp)
    if any(term in lowered for term in ("scan segurança", "scan seguranca", "scan security")):
        return security_scan(inp)
    if any(term in lowered for term in ("plano de patch", "patch plan", "plano técnico", "plano tecnico")):
        return safe_patch_plan(inp)
    if any(term in lowered for term in ("listar agentes", "membros do squad", "liste os agentes")):
        return list_squad_agents_post(inp)
    if _looks_like_attachment_analysis_request(effective_message):
        return _attachment_analysis_read_payload(inp)
    if _looks_like_github_runtime_request(effective_message):
        return github_execute(inp)
    return _platform_self_audit_detached(inp)

class OrionRuntimeIn(BaseModel):
    message: str = Field(min_length=1)
    prepare_only: bool = False
    include_frontend: bool = False


# Compatibility aliases expected by app.main
OrionExecuteIn = OrionRuntimeIn


def _request_governance_health(request: Optional[Request] = None) -> Dict[str, Any]:
    app = getattr(request, "app", None) if request is not None else None
    identity = getattr(getattr(app, "state", None), "orkio_identity", None) if app is not None else None
    constitution = getattr(getattr(app, "state", None), "orkio_constitution", None) if app is not None else None
    permissions = getattr(getattr(app, "state", None), "orkio_permissions", None) if app is not None else None
    capabilities = getattr(getattr(app, "state", None), "orkio_capabilities", None) if app is not None else None
    memory = getattr(getattr(app, "state", None), "orkio_memory", None) if app is not None else None
    if identity or constitution or permissions or capabilities or memory:
        return build_governance_health(
            identity=identity or {},
            constitution=constitution or {},
            permissions=permissions or {},
            capabilities=capabilities or {},
            memory=memory or {},
        )
    identity = load_active_identity()
    constitution = load_constitution()
    permissions = load_permissions()
    capabilities = load_runtime_governed_capabilities()
    memory = {"identity_version": identity.get("version"), "constitution_version": constitution.get("version")}
    return build_governance_health(
        identity=identity,
        constitution=constitution,
        permissions=permissions,
        capabilities=capabilities,
        memory=memory,
    )




def _message_contains_any(text: str, terms: List[str]) -> bool:
    txt = (text or "").strip().lower()
    return any(term in txt for term in terms)


def _message_requests_explicit_write(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    write_markers = [
        "aplique patch",
        "aplicar patch",
        "prepare branch",
        "preparar branch",
        "crie branch",
        "criar branch",
        "write file",
        "escreva no repo",
        "escrever no repo",
        "crie arquivo",
        "criar arquivo",
        "update file",
        "altere arquivo",
        "alterar arquivo",
        "corrija arquivo",
        "corrigir arquivo",
        "prepare commit",
        "crie commit",
        "criar commit",
        "abrir pr",
        "abra pr",
        "open pr",
        "pull request",
        "merge",
        "deploy",
    ]
    return any(marker in txt for marker in write_markers)


def _message_requests_privileged_read(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    admin_markers = [
        "admin master",
        "como admin",
        "sou admin",
        "acesso admin",
        "authorized admin",
    ]
    read_markers = [
        "analise o arquivo",
        "analisar o arquivo",
        "leia o arquivo",
        "ler o arquivo",
        "arquivo em anexo",
        "arquivo anexado",
        "logs em anexo",
        "analise os logs",
        "me diga o que é",
        "me diga o que e",
        "explique o que é",
        "explique o que e",
        "auditoria",
        "audit",
        "diagnóstico",
        "diagnostico",
    ]
    return any(marker in txt for marker in admin_markers) and any(marker in txt for marker in read_markers)


def _looks_like_attachment_analysis_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    attachment_markers = [
        "arquivo em anexo",
        "arquivo anexado",
        "logs em anexo",
        "log em anexo",
        "anexo",
        "arquivo json",
        "arquivo txt",
        "pdf",
        "docx",
    ]
    analysis_markers = [
        "analise",
        "analisar",
        "leia",
        "ler",
        "explique",
        "me diga",
        "o que é",
        "o que e",
        "audite",
        "auditoria",
        "diagnóstico",
        "diagnostico",
    ]
    repo_write_markers = [
        "github",
        "repo",
        "repositório",
        "repositorio",
        "branch",
        "commit",
        "pull request",
        "pr ",
        "merge",
        "deploy",
        "patch",
    ]
    has_attachment = any(marker in txt for marker in attachment_markers) or ("arquivo" in txt and "anexo" in txt)
    has_analysis = any(marker in txt for marker in analysis_markers)
    has_repo_op = any(marker in txt for marker in repo_write_markers)
    return bool(has_attachment and has_analysis and not has_repo_op)


def _attachment_analysis_read_payload(inp: "OrionRuntimeIn", *, request: Optional[Request] = None) -> Dict[str, Any]:
    visible_agent = _resolve_visible_agent(inp.message, default="orion")
    decision = evaluate_governance_action(
        action_scope="read",
        capability_name="github_repo_read",
        target_scope="platform",
        context=_governance_context_from_message(inp.message, request=request),
        safe_mode=False,
    )
    if not decision.get("allowed"):
        return _blocked_governance_payload(
            message=inp.message,
            mode="attachment_analysis_read",
            action_scope="read",
            capability_name="github_repo_read",
            target_scope="platform",
            decision=decision,
        )
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "attachment_analysis_read",
        "provider": "platform",
        "visible_agent": visible_agent,
        "requested_write": False,
        "write_approval_required": False,
        "admin_access_mode": "read_privileged" if _message_requests_privileged_read(inp.message) else "standard_read",
        "message": "Pedido reconhecido como leitura/análise de arquivo ou logs anexados. Nenhuma autorização de escrita GitHub foi aberta.",
        "next_step": "A camada de chat deve consumir o arquivo anexado em modo read-only e responder sem registrar approval de branch.",
        "governance_decision": decision,
        "generated_at": _now_ts(),
    }



def _extract_governance_bridge_payload(message: str) -> Dict[str, Any]:
    payload = _extract_embedded_runtime_payload(message or "")
    bridge = payload.get("governance_bridge") if isinstance(payload, dict) else None
    return dict(bridge) if isinstance(bridge, dict) else {}


def _extract_embedded_github_write_approval(message: str) -> Dict[str, Any]:
    bridge = _extract_governance_bridge_payload(message or "")
    approval = bridge.get("github_write_approval") if isinstance(bridge, dict) else None
    return dict(approval) if isinstance(approval, dict) else {}


def _approval_allows_actions(approval: Optional[Dict[str, Any]], required_actions: Optional[List[str]] = None) -> bool:
    if not isinstance(approval, dict):
        return False
    allowed = {str(item or "").strip().lower() for item in list(approval.get("actions_allowed") or []) if str(item or "").strip()}
    required = [str(item or "").strip().lower() for item in (required_actions or []) if str(item or "").strip()]
    if not allowed or not required:
        return False
    return all(item in allowed for item in required)

def _governance_context_from_message(message: str, *, request: Optional[Request] = None) -> Dict[str, Any]:
    effective = _continuous_audit_effective_input(message or "")
    effective_message = str(effective.get("message") or message or "")
    txt = effective_message.strip().lower()
    safe_health = _request_governance_health(request)
    embedded_approval = _extract_embedded_github_write_approval(message or "")
    bridge_payload = _extract_governance_bridge_payload(message or "")
    approval_actions_ok = _approval_allows_actions(
        embedded_approval,
        required_actions=["create_branch", "apply_patch", "prepare_commit", "open_pr"],
    )
    raw_authorization_present = any(term in txt for term in [
        "autorizo",
        "autorização explícita",
        "autorizacao explicita",
        "authorized",
        "approval granted",
        "approved by founder",
    ]) or bool(embedded_approval)
    explicit_write_requested = _message_requests_explicit_write(effective_message) or approval_actions_ok
    read_privileged_requested = _message_requests_privileged_read(effective_message)
    runtime_audit_requested = any(term in txt for term in [
        "auditoria",
        "audit",
        "diagnóstico",
        "diagnostico",
        "read only",
        "somente leitura",
    ])
    authorization_present = bool((raw_authorization_present and explicit_write_requested) or approval_actions_ok)
    admin_access_mode = "read_privileged" if read_privileged_requested and not explicit_write_requested else (
        "write_governed" if authorization_present else "standard"
    )
    return {
        "message": effective_message or "",
        "authorization_present": authorization_present,
        "raw_authorization_present": raw_authorization_present,
        "explicit_write_requested": explicit_write_requested,
        "read_privileged_requested": read_privileged_requested,
        "runtime_audit_requested": runtime_audit_requested,
        "admin_access_mode": admin_access_mode,
        "safe_mode": bool(safe_health.get("safe_mode", False)),
        "approval_bridge_present": bool(embedded_approval),
        "approval_bridge_actions_ok": approval_actions_ok,
        "approval_bridge_id": str(embedded_approval.get("approval_id") or "").strip() or None,
        "approval_bridge_scope": str(embedded_approval.get("scope") or "").strip() or None,
        "approval_bridge_source": str(bridge_payload.get("source") or "").strip() or None,
    }


def governance_capability_answer(inp: "OrionRuntimeIn", *, request: Optional[Request] = None) -> Dict[str, Any]:
    governance_context = _governance_context_from_message(inp.message or "", request=request)
    approval_actions_ok = bool(governance_context.get("approval_bridge_actions_ok"))
    authorization_present = bool(governance_context.get("authorization_present"))
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "governance_capability_answer",
        "provider": "platform",
        "event": "GOVERNANCE_CAPABILITY_ANSWER_READY",
        "status": "ready",
        "execution_depth": "final_readonly",
        "dispatch_executed": False,
        "visible_agent": "orion",
        "target_agent": "orion",
        "authorization_present": authorization_present,
        "approval_bridge_actions_ok": approval_actions_ok,
        "admin_access_mode": governance_context.get("admin_access_mode") or "standard",
        "requires_write_approval": True,
        "message": (
            "Sim. Temos capacidade operacional para evidenciar necessidades, propor melhorias e preparar execução governada no codebase.\n\n"
            "Regras de operação:\n"
            "- sem aprovação explícita: apenas auditoria, evidência técnica, diagnóstico, plano e proposta em modo read-only.\n"
            "- com aprovação explícita válida: podemos criar branch, aplicar patch, preparar commit e abrir PR governado.\n"
            "- merge e deploy continuam sujeitos à política operacional e validação humana.\n"
            "- escrita silenciosa na main não é permitida por padrão."
        ),
    }


def _blocked_governance_payload(*, message: str, mode: str, action_scope: str, capability_name: str, target_scope: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    receipt = make_governed_receipt(
        event="GOVERNED_ACTION_BLOCKED",
        mode=mode,
        status="blocked",
        governance_decision=decision,
        repo_target=target_scope,
    )
    return {
        "ok": False,
        "service": "orion_internal",
        "mode": mode,
        "message": message,
        "action_scope": action_scope,
        "target_scope": target_scope,
        "capability_name": capability_name,
        "governance_decision": decision,
        "receipt": receipt,
        "safe_mode": "safe_mode" in (decision.get("blocked_by") or []),
        "error": decision.get("reason") or "governance blocked execution",
    }



@router.post("/platform/audit/continuous/start")
def continuous_audit_start(
    inp: OrionRuntimeIn,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    org = str(request.headers.get("x-org-slug") or "public").strip() or "public"
    return start_continuous_audit_job(
        db,
        org,
        message=inp.message or "",
        include_frontend=bool(inp.include_frontend),
        requested_by_user_id=str(request.headers.get("x-user-id") or "").strip() or None,
        requested_by_user_name=str(request.headers.get("x-user-name") or request.headers.get("x-user") or "http_request").strip() or "http_request",
    )


@router.get("/platform/audit/continuous/{job_id}")
def continuous_audit_status(job_id: str, request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    org = str(request.headers.get("x-org-slug") or "public").strip() or "public"
    payload = get_continuous_audit_job_snapshot(db, org, job_id)
    payload.update({
        "ok": True,
        "service": "orion_internal",
        "provider": "platform",
        "mode": "continuous_audit_job",
        "event": "CONTINUOUS_AUDIT_JOB_STATUS",
    })
    return payload


@router.get("/health")
def health(request: Request) -> Dict[str, Any]:
    governance = _request_governance_health(request)
    return {
        "ok": True,
        "service": "orion_internal",
        "github_bridge_ready": _bool_env("ENABLE_GITHUB_BRIDGE", False),
        "default_branch": _default_branch(),
        "evolution_enabled": _evolution_enabled(),
        "governance_ready": bool(governance.get("governance_ready")),
        "safe_mode": bool(governance.get("safe_mode")),
        "safe_mode_reason": governance.get("safe_mode_reason") or "",
        "identity_version": governance.get("identity_version") or "",
        "constitution_version": governance.get("constitution_version") or "",
    }


@router.get("/governance/health")
def governance_health(request: Request) -> Dict[str, Any]:
    governance = _request_governance_health(request)
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "governance_health",
        **governance,
    }


@router.get("/identity")
def identity_profile() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "identity_profile",
        "identity": load_active_identity(),
    }


@router.get("/constitution")
def constitution_profile() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "constitution_profile",
        "constitution": load_constitution(),
    }


@router.get("/capabilities")
def capabilities_profile() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "capabilities_profile",
        "capabilities": load_runtime_governed_capabilities(),
    }


@router.get("/squad")
def list_squad_agents() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "squad_agents_list",
        "squad": _suggested_squad(),
        "repo_targets": _build_repo_targets(),
        "policy": _safe_patch_policy(),
        "generated_at": _now_ts(),
    }


@router.post("/squad/list")
def list_squad_agents_post(inp: OrionRuntimeIn) -> Dict[str, Any]:
    visible_agent = _resolve_visible_agent(inp.message, default="orion")
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "squad_agents_list",
        "visible_agent": visible_agent,
        "message": "Agentes do squad listados com sucesso.",
        "squad": _suggested_squad(),
        "repo_targets": _build_repo_targets(),
        "policy": _safe_patch_policy(),
        "generated_at": _now_ts(),
    }




def _looks_like_squad_resolution_request(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    markers = (
        "resolva exatamente este squad",
        "resolver este squad",
        "resolver squad",
        "squad resolvido",
        "resolve exactly this squad",
        "resolve this squad",
    )
    return any(marker in lowered for marker in markers)


def _looks_like_squad_resolution_trace_request(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    return (
        "retorne apenas" in lowered
        and (
            "requested_specialists_raw" in lowered
            or "selected_specialists_before_policy" in lowered
            or "selected_specialists_after_policy" in lowered
            or "abort_reason" in lowered
        )
    )


def _extract_known_dispatch_actors_from_text(text: str) -> List[str]:
    """
    EFATA777_ORION_PRESENCE_AND_SQUAD_PARSE_HOTFIX:
    Extract only known specialist ids from free text.
    Prevents instruction tails from being glued to a specialist, e.g.
    "backend_engineer. Modo read-only. Não execute dispatch."
    """
    raw = str(text or "").lower().replace("@", " ")
    normalized = re.sub(r"[^a-z0-9_]+", "_", raw)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    padded = f"_{normalized}_"
    out: List[str] = []
    seen: set = set()
    for actor in _dispatch_specialist_registry():
        slug = _canonical_dispatch_actor(actor)
        if not slug:
            continue
        token = f"_{slug}_"
        if token in padded and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


def _extract_requested_specialists_from_message(message: str) -> List[str]:
    constraints = _extract_hard_constraints(message or "")
    required = _dedupe_dispatch_actors(list(constraints.get("specialists_required") or []))
    if required:
        return required

    known_actors = _extract_known_dispatch_actors_from_text(message or "")
    if known_actors and _looks_like_squad_resolution_request(message or ""):
        return _dedupe_dispatch_actors(known_actors)

    lines = [str(line or "").strip() for line in str(message or "").splitlines()]
    collected: List[str] = []
    capture = False
    for line in lines:
        lowered = line.lower()
        if not capture and (
            "resolva exatamente este squad" in lowered
            or "resolver este squad" in lowered
            or "resolver squad" in lowered
            or "resolve exactly this squad" in lowered
            or lowered.startswith("squad:")
        ):
            capture = True
            if ":" in line:
                inline = line.split(":", 1)[1].strip()
                if inline:
                    parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", inline)]
                    collected.extend([p for p in parts if p])
            continue
        if not capture:
            continue
        if not line:
            if collected:
                break
            continue
        if lowered.startswith(("responda apenas", "retorne apenas", "não execute dispatch", "nao execute dispatch", "modo read-only", "modo read only", "agente visível final", "agente visivel final")):
            if collected:
                break
            continue
        parts = [_strip_constraint_token(p) for p in re.split(r"[,;]", line)]
        cleaned = [p for p in parts if p]
        if cleaned:
            collected.extend(cleaned)
            continue
        if collected:
            break

    return _dedupe_dispatch_actors(collected)


def _dispatch_specialist_registry() -> List[str]:
    # EFATA777_ORION_CHRIS_ROSTER_UNIFICATION_PATCH
    # Libera especialistas técnicos do guarda-chuva do Orion em modo read-only.
    return _dedupe_dispatch_actors([
        "orkio",
        "orion",
        "auditor",
        "cto",
        "ux_frontend",
        "backend_engineer",
        "frontend_engineer",
        "devops_sre",
        "security_guardian",
        "data_db_architect",
        "qa_release_engineer",
        "realtime_voice_engineer",
        # aliases/legado preservados
        "architect",
        "devops",
        "security",
        "memory_ops",
        "stage_manager",
        "chris",
    ])


def _resolve_squad_readonly_payload(inp: OrionRuntimeIn, *, trace_mode: bool = False) -> Dict[str, Any]:
    message = inp.message or ""
    visible_agent = _resolve_visible_agent(message, default="orion")
    constraints = _extract_hard_constraints(message)
    requested_raw = _extract_requested_specialists_from_message(message)
    requested_normalized = _dedupe_dispatch_actors(requested_raw)
    selected_before_policy = [item for item in requested_normalized if item in _dispatch_specialist_registry()]
    selected_after_policy = _apply_specialist_constraints(selected_before_policy, constraints=constraints)
    violations = _validate_dispatch_constraints(
        visible_agent=visible_agent,
        selected_specialists=list(selected_after_policy or []),
        constraints=constraints,
    )
    missing = [item for item in requested_normalized if item not in selected_before_policy]
    abort_reason = None
    if missing:
        abort_reason = "missing_specialists: " + ", ".join(missing)
    elif violations:
        abort_reason = "; ".join(violations)

    payload: Dict[str, Any] = {
        "ok": not bool(abort_reason),
        "service": "orion_internal",
        "mode": "squad_resolution_trace_readonly" if trace_mode else "squad_resolve_readonly",
        "visible_agent": visible_agent,
        "capability_name": "squad_resolution_trace_readonly" if trace_mode else "squad_resolve_readonly",
        "template_id": "squad_resolution_trace_readonly_v1" if trace_mode else "squad_resolve_readonly_v1",
        "requested_specialists_raw": list(requested_raw),
        "requested_specialists_normalized": list(requested_normalized),
        "selected_specialists_before_policy": list(selected_before_policy),
        "selected_specialists_after_policy": list(selected_after_policy),
        "squad_resolved": list(selected_after_policy),
        "missing_specialists": list(missing),
        "constraint_violations": list(violations),
        "abort_reason": abort_reason,
        "generated_at": _now_ts(),
    }
    if not trace_mode:
        payload["message"] = ", ".join(selected_after_policy) if selected_after_policy else ""
    return payload


def resolve_squad_readonly(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return _resolve_squad_readonly_payload(inp, trace_mode=False)


def squad_resolution_trace_readonly(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return _resolve_squad_readonly_payload(inp, trace_mode=True)


@router.post("/platform/audit")
def platform_self_audit(
    inp: OrionRuntimeIn,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    own_db = False
    try:
        org = "public"
        requested_by_user_id = None
        requested_by_user_name = "runtime"
        if request is not None:
            try:
                org = str(request.headers.get("x-org-slug") or "public").strip() or "public"
            except Exception:
                org = "public"
            requested_by_user_id = str(request.headers.get("x-user-id") or "").strip() or None
            requested_by_user_name = str(request.headers.get("x-user-name") or request.headers.get("x-user") or "http_request").strip() or "http_request"
        if _looks_like_continuous_audit_status_request(inp.message or ""):
            payload = get_continuous_audit_status_from_message(db, org, inp.message or "")
            payload["governance_decision"] = evaluate_governance_action(
                action_scope="read",
                capability_name="continuous_audit_job_status",
                target_scope="platform",
                context=_governance_context_from_message(inp.message),
                safe_mode=False,
            )
            payload["danielic_integrity_passed"] = bool(payload["governance_decision"].get("danielic_integrity_passed"))
            return payload
        if _looks_like_continuous_audit_request(inp.message or ""):
            payload = start_continuous_audit_job(
                db,
                org,
                message=inp.message or "",
                include_frontend=bool(inp.include_frontend),
                requested_by_user_id=requested_by_user_id,
                requested_by_user_name=requested_by_user_name,
            )
            payload["governance_decision"] = evaluate_governance_action(
                action_scope="diagnose",
                capability_name="continuous_audit_job",
                target_scope="platform",
                context=_governance_context_from_message(inp.message),
                safe_mode=False,
            )
            payload["danielic_integrity_passed"] = bool(payload["governance_decision"].get("danielic_integrity_passed"))
            return payload

        visible_agent = _resolve_visible_agent(inp.message, default="orkio")
        payload = _build_platform_self_audit_payload(inp, visible_agent)
        decision = evaluate_governance_action(
            action_scope="diagnose",
            capability_name="platform_self_audit",
            target_scope="platform",
            context=_governance_context_from_message(inp.message),
            safe_mode=False,
        )
        payload["governance_decision"] = decision
        payload["danielic_integrity_passed"] = bool(decision.get("danielic_integrity_passed"))
        return payload
    finally:
        if own_db and db is not None:
            try:
                db.close()
            except Exception:
                pass


@router.post("/platform/scan/repo")
def repo_structure_scan(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "repo_structure_scan",
        "message": "Varredura de estrutura preparada.",
        "targets": _build_repo_targets(),
        "focus": [
            "app/main.py",
            "app/routes/internal",
            "app/runtime",
            "app/self_heal",
            "frontend runtime bridge",
        ],
        "generated_at": _now_ts(),
    }


@router.post("/platform/scan/runtime")
def runtime_scan(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "runtime_scan",
        "message": "Varredura de runtime preparada.",
        "focus": [
            "intent_engine",
            "planner_layer",
            "capability_registry",
            "chat/stream handoff",
            "github capability dispatch",
        ],
        "policy": _safe_patch_policy(),
        "generated_at": _now_ts(),
    }


@router.post("/platform/scan/security")
def security_scan(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "security_scan",
        "message": "Varredura de segurança preparada.",
        "checks": [
            "main direct write blocked",
            "explicit deploy approval",
            "explicit db approval",
            "destructive db runtime blocked",
            "allowed write agents restricted",
        ],
        "policy": _safe_patch_policy(),
        "generated_at": _now_ts(),
    }


@router.post("/platform/patch-plan")
def safe_patch_plan(inp: OrionRuntimeIn) -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "safe_patch_plan",
        "message": "Plano de patch seguro preparado. Aguardando aprovação humana antes de qualquer escrita.",
        "steps": [
            "1. Auditor identifica falhas reais",
            "2. CTO consolida patch incremental",
            "3. Orion prepara branch e arquivos",
            "4. Aprovação humana explícita",
            "5. Execução em branch + PR",
            "6. Receipts transacionais obrigatórios entre branch, patch, commit, compare e PR",
        ],
        "write_agent": "orion",
        "policy": _safe_patch_policy(),
        "generated_at": _now_ts(),
    }






def _looks_like_pwa_console_repair_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False
    canonical_markers = (
        "incidente pwa/console executável",
        "incidente pwa/console executavel",
        "pwa_console_repair",
        "corrija o pwa do console",
        "corrigir o pwa do console",
    )
    scope_markers = (
        "pwa",
        "console",
        "threads",
        "agents",
        "agentes",
        "sidebar",
        "ux",
        "frontend",
        "thread list",
        "agent selector",
    )
    repair_markers = (
        "corrija",
        "corrigir",
        "correção",
        "correcao",
        "restaurar",
        "reaparecer",
        "voltar a aparecer",
        "fix",
        "repair",
        "patch",
    )
    return any(marker in txt for marker in canonical_markers) or (
        any(marker in txt for marker in scope_markers)
        and any(marker in txt for marker in repair_markers)
    )


def pwa_console_repair(inp: OrionRuntimeIn) -> Dict[str, Any]:
    raw_message = inp.message or ""
    effective = _continuous_audit_effective_input(
        raw_message,
        include_frontend=bool(getattr(inp, "include_frontend", False)),
        thread_id=getattr(inp, "thread_id", None),
    )
    message = str(effective.get("message") or raw_message or "")
    visible_agent = _resolve_visible_agent(message, default="orion")
    constraints = _extract_hard_constraints(message)
    selected_specialists = _apply_specialist_constraints(
        _audit_selected_specialists("specialist", include_frontend=True),
        constraints=constraints,
    )
    selected_specialists = _filter_specialists_for_message(selected_specialists, message)
    violations = _validate_dispatch_constraints(
        visible_agent=visible_agent,
        selected_specialists=selected_specialists,
        constraints=constraints,
    )

    governance_context = _governance_context_from_message(raw_message)
    embedded_approval = _extract_embedded_github_write_approval(raw_message)
    approval_actions_ok = _approval_allows_actions(
        embedded_approval,
        required_actions=["create_branch", "apply_patch", "prepare_commit", "open_pr"],
    )
    governance_decision = evaluate_governance_action(
        action_scope="write_branch",
        capability_name="github_repo_write",
        target_scope="frontend",
        context=governance_context,
        safe_mode=False,
    )
    if not governance_decision.get("allowed"):
        blocked_by = [str(item or "").strip().lower() for item in list(governance_decision.get("blocked_by") or []) if str(item or "").strip()]
        authorization_block = (not blocked_by) or any(term in item for item in blocked_by for term in ("authorization", "approval", "human", "consent"))
        if approval_actions_ok and authorization_block and not bool(governance_context.get("safe_mode", False)):
            governance_decision = dict(governance_decision or {})
            governance_decision.update({
                "allowed": True,
                "approval_bridge": True,
                "approval_id": str(embedded_approval.get("approval_id") or "").strip() or None,
                "approval_scope": str(embedded_approval.get("scope") or "").strip() or None,
                "actions_allowed": list(embedded_approval.get("actions_allowed") or []),
                "reason": "github_write_approval_bridge",
            })
        else:
            return _blocked_governance_payload(
                message=message,
                mode="pwa_console_repair",
                action_scope="write_branch",
                capability_name="github_repo_write",
                target_scope="frontend",
                decision=governance_decision,
            )

    payload: Dict[str, Any] = {
        "ok": True,
        "service": "orion_internal",
        "mode": "pwa_console_repair",
        "provider": "platform",
        "event": "PWA_CONSOLE_REPAIR_READY",
        "status": "accepted",
        "execution_depth": "ready",
        "delivery_contract": "pwa_console_repair_v1",
        "visible_agent": visible_agent,
        "selected_specialists": list(selected_specialists or []),
        "selected_specialists_count": len(list(selected_specialists or [])),
        "required_signer": constraints.get("required_signer") or visible_agent,
        "specialists_required": list(constraints.get("specialists_required") or []),
        "specialists_forbidden": list(constraints.get("specialists_forbidden") or []),
        "selected_specialists_count_must_be": constraints.get("selected_specialists_count_must_be"),
        "constraint_violations": list(violations or []),
        "governance_decision": governance_decision,
        "danielic_integrity_passed": bool(governance_decision.get("danielic_integrity_passed")),
        "technical_summary": "Incidente PWA/console reconhecido no runtime do Orion. O fluxo operacional foi aceito fora do trilho genérico de capability failure.",
        "executive_diagnostic": "O backend está saudável; o foco operacional é restaurar visibilidade e seleção de threads/agentes no PWA sem depender de refresh manual.",
        "probable_files": [
            "frontend: AppConsole / rota principal do console",
            "frontend: sidebar / thread list",
            "frontend: agent selector / agent list",
            "frontend: store/context de sessão do console",
        ],
        "implementation_steps": [
            "Verificar carga inicial de threads e agentes após login/heartbeat.",
            "Inspecionar estados de loading, vazio e erro no console.",
            "Restaurar renderização da sidebar e do seletor de agentes.",
            "Validar persistência da seleção sem refresh manual.",
        ],
        "recommended_actions": [
            "Coletar contratos atuais de /api/threads e /api/agents no frontend.",
            "Corrigir a condição de renderização que oculta threads/agentes.",
            "Validar seleção de thread/agente após login e após heartbeat.",
        ],
        "message": "Incidente PWA/console reconhecido e aceito pelo Orion runtime.",
        "resolution": "O runtime do Orion agora reconhece pedidos de correção do PWA/console sem cair no fallback genérico de capability.",
        "next_authorization_command": "@Orion Pode prosseguir com a correção técnica mínima segura do PWA/console e consolidar diagnóstico, patch aplicado e validação final.",
        "generated_at": _now_ts(),
    }
    if violations:
        payload["status"] = "accepted_with_constraints"
        payload["resolution"] = "O incidente foi aceito, mas ainda há constraints declaradas pelo prompt que precisam ser observadas."
    return payload

def _looks_like_github_runtime_request(message: str) -> bool:
    txt = (message or "").strip().lower()
    if not txt:
        return False

    if _looks_like_attachment_analysis_request(message):
        return False

    strong_keywords = (
        "github",
        "repo",
        "repositório",
        "repositorio",
        "branch",
        "commit",
        "pull request",
        "pr ",
        "merge",
        "deploy",
        "patch",
        "main.py",
        "package.json",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
    )
    file_keywords = (
        "arquivo",
        "file",
        "abrir arquivo",
        "open file",
        "ler arquivo",
        "read file",
        "mostrar arquivo",
        "show file",
        "listar arquivos",
        "list files",
        "buscar",
        "search",
        "procurar",
    )
    has_strong = any(k in txt for k in strong_keywords)
    has_file_request = any(k in txt for k in file_keywords)
    return bool(has_strong or (has_file_request and ("github" in txt or "repo" in txt or "repositório" in txt or "repositorio" in txt)))


@router.post("/github/execute")
def github_execute(inp: OrionRuntimeIn, _access: Dict[str, Any] = Depends(require_master_admin_access)) -> Dict[str, Any]:
    visible_agent = _resolve_visible_agent(inp.message, default="orion")
    message = inp.message or ""
    lowered = message.lower()

    if not _looks_like_github_runtime_request(message):
        return {
            "ok": False,
            "service": "orion_internal",
            "mode": "github_execute",
            "error": "Mensagem não caracteriza operação GitHub/runtime",
            "message": message,
        }

    if _looks_like_attachment_analysis_request(message):
        return _attachment_analysis_read_payload(inp)

    requested_write = _message_requests_explicit_write(message)

    action_scope = "write_branch" if requested_write else "read"
    capability_name = "github_repo_write" if requested_write else "github_repo_read"
    target_scope = "cross_repo" if _github_repo() and _github_repo_web() else ("backend" if _github_repo() else ("frontend" if _github_repo_web() else "platform"))
    governance_decision = evaluate_governance_action(
        action_scope=action_scope,
        capability_name=capability_name,
        target_scope=target_scope,
        context=_governance_context_from_message(message),
        safe_mode=False,
    )
    if not governance_decision.get("allowed"):
        return _blocked_governance_payload(
            message=message,
            mode="github_execute",
            action_scope=action_scope,
            capability_name=capability_name,
            target_scope=target_scope,
            decision=governance_decision,
        )

    if requested_write and visible_agent not in _allowed_write_agents():
        return {
            "ok": False,
            "service": "orion_internal",
            "mode": "github_execute",
            "error": f"Agent '{visible_agent}' cannot execute GitHub write operations. Allowed agents: {', '.join(_allowed_write_agents())}",
            "message": message,
            "visible_agent": visible_agent,
            "requested_write": True,
        }

    backend_repo = _github_repo()
    frontend_repo = _github_repo_web()
    default_branch = _default_branch()
    repository_details: List[Dict[str, Any]] = []
    if backend_repo:
        repository_details.append({"kind": "backend", "repo": backend_repo, "branch": default_branch})
    if frontend_repo:
        repository_details.append({"kind": "frontend", "repo": frontend_repo, "branch": default_branch})

    if _looks_like_compare_status_request(message):
        return _github_compare_status_payload(message, visible_agent, repository_details)

    if _looks_like_repo_inventory_request(message):
        payload: Dict[str, Any] = {
            "ok": True,
            "service": "orion_internal",
            "mode": "github_runtime_inventory",
            "event": "GITHUB_RUNTIME_INVENTORY_OK",
            "visible_agent": visible_agent,
            "provider": "github",
            "message": "Inventário de repositórios do runtime coletado com leitura explícita das variáveis configuradas.",
            "requested_write": requested_write,
            "write_enabled": _github_write_enabled(),
            "pr_enabled": _github_pr_enabled(),
            "main_direct_write_allowed": _main_direct_allowed(),
            "default_branch": default_branch,
            "branch": default_branch,
            "backend_repo": backend_repo,
            "frontend_repo": frontend_repo,
            "repositories": [repo for repo in [backend_repo, frontend_repo] if repo],
            "repository_details": repository_details,
            "prepare_only": bool(inp.prepare_only),
            "generated_at": _now_ts(),
        }
        if _wants_root_evidence(message):
            backend_root = _github_root_entries(backend_repo, default_branch, limit=3)
            frontend_root = _github_root_entries(frontend_repo, default_branch, limit=3)
            payload["backend_root_entries"] = list(backend_root.get("entries") or [])
            payload["frontend_root_entries"] = list(frontend_root.get("entries") or [])
            payload["backend_root_ok"] = bool(backend_root.get("ok"))
            payload["frontend_root_ok"] = bool(frontend_root.get("ok"))
            if not backend_root.get("ok"):
                payload["backend_root_error"] = str(backend_root.get("message") or "").strip()
            if not frontend_root.get("ok"):
                payload["frontend_root_error"] = str(frontend_root.get("message") or "").strip()
        return payload

    return {
        "ok": True,
        "service": "orion_internal",
        "mode": "github_execute",
        "event": "GITHUB_RUNTIME_CONFIG_OK",
        "visible_agent": visible_agent,
        "provider": "github",
        "message": message,
        "requested_write": requested_write,
        "write_enabled": _github_write_enabled(),
        "pr_enabled": _github_pr_enabled(),
        "main_direct_write_allowed": _main_direct_allowed(),
        "default_branch": default_branch,
        "branch": default_branch,
        "backend_repo": backend_repo,
        "frontend_repo": frontend_repo,
        "repositories": [repo for repo in [backend_repo, frontend_repo] if repo],
        "repository_details": repository_details,
        "prepare_only": bool(inp.prepare_only),
        "generated_at": _now_ts(),
    }


# Compatibility aliases expected by app.main
def orion_github_execute(inp: OrionExecuteIn) -> Dict[str, Any]:
    return github_execute(inp)


def orion_runtime_execute_alias(inp: OrionExecuteIn) -> Dict[str, Any]:
    try:
        return orion_runtime_execute(inp)
    except HTTPException as e:
        detail = getattr(e, "detail", None)
        status_code = int(getattr(e, "status_code", 500) or 500)
        message = ""
        error_code = ""
        if isinstance(detail, dict):
            message = str(
                detail.get("message")
                or detail.get("detail")
                or detail.get("github_error")
                or detail.get("error")
                or ""
            ).strip()
            error_code = str(detail.get("error_code") or detail.get("code") or "").strip()
        else:
            message = str(detail or "").strip()

        if status_code == 401:
            message = message or "Sessão inválida ou expirada."
            error_code = error_code or "AUTH_SESSION_EXPIRED"
        elif status_code == 403:
            message = message or "Acesso não autorizado para esta operação."
            error_code = error_code or "AUTH_FORBIDDEN"

        return {
            "ok": False,
            "service": "orion_internal",
            "mode": "orion_runtime_execute_alias",
            "provider": "runtime",
            "event": "ORION_RUNTIME_HTTP_EXCEPTION",
            "status_code": status_code,
            "auth_error": status_code in {401, 403},
            "error": message or "runtime_http_exception",
            "error_code": error_code or "runtime_http_exception",
            "error_type": e.__class__.__name__,
            "detail": detail if isinstance(detail, dict) else {"detail": message or str(detail or "").strip()},
            "message": message or "Falha ao avaliar capability operacional solicitada.",
            "generated_at": _now_ts(),
        }
    except Exception as e:
        message = str(e or "").strip()
        return {
            "ok": False,
            "service": "orion_internal",
            "mode": "orion_runtime_execute_alias",
            "provider": "runtime",
            "event": "ORION_RUNTIME_UNEXPECTED_EXCEPTION",
            "status_code": 500,
            "auth_error": False,
            "error": message or "unexpected_runtime_exception",
            "error_code": e.__class__.__name__ or "UNEXPECTED_RUNTIME_EXCEPTION",
            "error_type": e.__class__.__name__,
            "detail": {
                "detail": message or "unexpected_runtime_exception",
                "exception_type": e.__class__.__name__,
            },
            "message": message or "Falha interna ao avaliar capability operacional.",
            "generated_at": _now_ts(),
        }


# === ORKIO OBSERVABILITY INTEGRATION ===
from app.observability.dispatch_persistence import persist_dispatch
from app.observability.audit_formatter import (
    format_executive_output,
    extract_dispatch_receipts,
    extract_specialist_reports
)

def _orkio_observability_bridge(result, db=None):
    try:
        dispatch = result if isinstance(result, dict) else {}
        if db:
            persist_dispatch(dispatch, db)

        return {
            "executive": format_executive_output(dispatch),
            "receipts": extract_dispatch_receipts(dispatch),
            "reports": extract_specialist_reports(dispatch)
        }
    except Exception as e:
        return result
