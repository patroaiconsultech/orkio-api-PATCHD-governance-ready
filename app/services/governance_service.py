from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Optional

from app.core.orkio_constitution import load_constitution
from app.core.orkio_identity import load_identity
from app.core.orkio_permissions import get_permission_rule, load_permissions
from app.services.capability_service import resolve_capability_profile


def _message_text(context: Optional[Dict[str, Any]]) -> str:
    return str((context or {}).get("message") or "").strip().lower()


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms if term)


def _truthfulness_check(text: str) -> bool:
    risky = [
        "oculte",
        "hide this",
        "esconda",
        "finja",
        "fingir",
        "burlar",
        "bypass",
        "sem deixar rastro",
        "without approval",
    ]
    return not _contains_any(text, risky)


def _protection_check(text: str) -> bool:
    harmful = [
        "deploy direto",
        "merge direto na main",
        "force push main",
        "destructive db",
        "drop production",
    ]
    return not _contains_any(text, harmful)


def _integrity_under_pressure_check(text: str) -> bool:
    pressure_markers = ["a qualquer custo", "sem autorização", "ignore a política", "ignore policy"]
    return not _contains_any(text, pressure_markers)


def _corruption_resistance_check(text: str) -> bool:
    corruption_markers = ["manipular", "enganar", "explorar vulnerabilidade", "exploit the user"]
    return not _contains_any(text, corruption_markers)


def _discernment_depth_check(text: str, context: Optional[Dict[str, Any]]) -> bool:
    if not text:
        return True
    if "?" in text:
        return True
    summary = str((context or {}).get("summary") or "")
    return bool(summary) or len(text.split()) >= 3


def _covenant_fidelity_check(text: str) -> bool:
    forbidden = ["trair a constituição", "betray the constitution", "violar a lei", "ignore christ principles"]
    return not _contains_any(text, forbidden)


def build_governance_health(
    *,
    identity: Optional[Dict[str, Any]],
    constitution: Optional[Dict[str, Any]],
    permissions: Optional[Dict[str, Any]],
    capabilities: Optional[Dict[str, Any]],
    memory: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    identity_loaded = bool(identity)
    constitution_loaded = bool(constitution)
    permissions_loaded = bool(permissions)
    capabilities_loaded = bool(capabilities)
    memory_loaded = bool(memory)
    governance_ready = all([identity_loaded, constitution_loaded, permissions_loaded, capabilities_loaded, memory_loaded])
    reason = "" if governance_ready else (
        "identity_not_loaded" if not identity_loaded else
        "constitution_not_loaded" if not constitution_loaded else
        "permissions_not_loaded" if not permissions_loaded else
        "capabilities_not_loaded" if not capabilities_loaded else
        "memory_not_loaded"
    )
    return {
        "identity_loaded": identity_loaded,
        "constitution_loaded": constitution_loaded,
        "permissions_loaded": permissions_loaded,
        "capabilities_loaded": capabilities_loaded,
        "memory_loaded": memory_loaded,
        "governance_ready": governance_ready,
        "safe_mode": not governance_ready,
        "safe_mode_reason": reason,
        "identity_version": str((identity or {}).get("version") or ""),
        "constitution_version": str((constitution or {}).get("version") or ""),
    }


def evaluate_governance_action(
    *,
    action_scope: str,
    capability_name: Optional[str],
    target_scope: str,
    context: Optional[Dict[str, Any]] = None,
    safe_mode: bool = False,
) -> Dict[str, Any]:
    context = deepcopy(context or {})
    identity = load_identity()
    constitution = load_constitution()
    permissions = load_permissions()
    permission_rule = get_permission_rule(action_scope)
    capability = resolve_capability_profile(capability_name)
    text = _message_text(context)

    requires_human_authorization = bool(
        permission_rule.get("requires_authorization")
        or capability.get("requires_authorization")
        or action_scope in {"write_branch", "open_pr", "merge", "deploy"}
    )
    authorization_present = bool(context.get("authorization_present")) or _boolish(context.get("explicit_authorization"))
    mission_alignment = bool(identity.get("mission"))
    constitution_alignment = bool(constitution.get("principles"))
    authority_check = bool(permission_rule.get("allowed", False))
    user_protection_check = _protection_check(text)
    truthfulness_check = _truthfulness_check(text)
    integrity_under_pressure_check = _integrity_under_pressure_check(text)
    corruption_resistance_check = _corruption_resistance_check(text)
    discernment_depth_check = _discernment_depth_check(text, context)
    covenant_fidelity_check = _covenant_fidelity_check(text)

    blocked_by = []
    if safe_mode:
        blocked_by.append("safe_mode")
    if not mission_alignment:
        blocked_by.append("mission_alignment_failed")
    if not constitution_alignment:
        blocked_by.append("constitution_alignment_failed")
    if not authority_check:
        blocked_by.append("authority_check_failed")
    if not user_protection_check:
        blocked_by.append("user_protection_check_failed")
    if not truthfulness_check:
        blocked_by.append("truthfulness_check_failed")
    if not integrity_under_pressure_check:
        blocked_by.append("integrity_under_pressure_check_failed")
    if not corruption_resistance_check:
        blocked_by.append("corruption_resistance_check_failed")
    if not discernment_depth_check:
        blocked_by.append("discernment_depth_check_failed")
    if not covenant_fidelity_check:
        blocked_by.append("covenant_fidelity_check_failed")
    if requires_human_authorization and not authorization_present:
        blocked_by.append("authorization_required")

    allowed = not blocked_by
    reason = "ação compatível com identidade, constituição e escopo autorizado"
    if blocked_by:
        reason = "execução bloqueada por governança: " + ", ".join(blocked_by)

    return {
        "action_scope": action_scope,
        "capability_name": capability_name,
        "target_scope": target_scope,
        "allowed": allowed,
        "mission_alignment": mission_alignment,
        "constitution_alignment": constitution_alignment,
        "authority_check": authority_check,
        "user_protection_check": user_protection_check,
        "truthfulness_check": truthfulness_check,
        "authorization_check": authorization_present or not requires_human_authorization,
        "integrity_under_pressure_check": integrity_under_pressure_check,
        "corruption_resistance_check": corruption_resistance_check,
        "discernment_depth_check": discernment_depth_check,
        "covenant_fidelity_check": covenant_fidelity_check,
        "requires_human_authorization": requires_human_authorization,
        "authorization_present": authorization_present,
        "blocked_by": blocked_by,
        "reason": reason,
        "constitution_version": str(constitution.get("version") or permissions.get("version") or "v1"),
        "danielic_integrity_passed": bool(
            integrity_under_pressure_check
            and corruption_resistance_check
            and discernment_depth_check
            and covenant_fidelity_check
        ),
    }
