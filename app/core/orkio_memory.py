from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional
import time


def initialize_live_memory_state(
    *,
    identity: Dict[str, Any],
    constitution: Dict[str, Any],
    permissions: Dict[str, Any],
    capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "identity_version": identity.get("version") or "unknown",
        "constitution_version": constitution.get("version") or "unknown",
        "permissions_version": permissions.get("version") or "unknown",
        "capabilities_loaded_count": len(capabilities or {}),
        "current_authority_scope": deepcopy((permissions or {}).get("rules") or {}),
        "safe_mode": False,
        "safe_mode_reason": "",
        "last_governance_decision": None,
        "last_receipt": None,
        "last_action_scope": None,
        "updated_at": int(time.time()),
    }


def update_live_memory(
    memory: Dict[str, Any],
    *,
    action_scope: Optional[str] = None,
    governance_decision: Optional[Dict[str, Any]] = None,
    receipt: Optional[Dict[str, Any]] = None,
    safe_mode: Optional[bool] = None,
    safe_mode_reason: Optional[str] = None,
) -> Dict[str, Any]:
    out = deepcopy(memory or {})
    if action_scope is not None:
        out["last_action_scope"] = action_scope
    if governance_decision is not None:
        out["last_governance_decision"] = deepcopy(governance_decision)
    if receipt is not None:
        out["last_receipt"] = deepcopy(receipt)
    if safe_mode is not None:
        out["safe_mode"] = bool(safe_mode)
    if safe_mode_reason is not None:
        out["safe_mode_reason"] = str(safe_mode_reason or "")
    out["updated_at"] = int(time.time())
    return out
