from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.orkio_memory import initialize_live_memory_state, update_live_memory


def bootstrap_live_memory(
    *,
    identity: Dict[str, Any],
    constitution: Dict[str, Any],
    permissions: Dict[str, Any],
    capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    return initialize_live_memory_state(
        identity=identity,
        constitution=constitution,
        permissions=permissions,
        capabilities=capabilities,
    )


def push_runtime_state(
    memory: Dict[str, Any],
    *,
    action_scope: Optional[str] = None,
    governance_decision: Optional[Dict[str, Any]] = None,
    receipt: Optional[Dict[str, Any]] = None,
    safe_mode: Optional[bool] = None,
    safe_mode_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return update_live_memory(
        memory,
        action_scope=action_scope,
        governance_decision=governance_decision,
        receipt=receipt,
        safe_mode=safe_mode,
        safe_mode_reason=safe_mode_reason,
    )
