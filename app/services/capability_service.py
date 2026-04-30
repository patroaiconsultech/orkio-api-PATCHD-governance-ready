from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from app.core.orkio_capabilities import load_governed_capabilities


def load_runtime_governed_capabilities(existing_registry: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    governed = load_governed_capabilities()
    existing_registry = existing_registry or {}
    for agent_name, meta in existing_registry.items():
        for capability_name in meta.get("capabilities") or []:
            capability_name = str(capability_name or "").strip()
            if capability_name and capability_name not in governed:
                governed[capability_name] = {
                    "purpose": f"runtime capability declared by {agent_name}",
                    "risk_level": "medium" if "write" in capability_name or "pr_" in capability_name else "low",
                    "requires_authorization": ("write" in capability_name or "pr_" in capability_name or capability_name in {"merge", "deploy"}),
                    "allowed_targets": ["platform"],
                    "writes_repository": "write" in capability_name,
                    "opens_pull_request": "pr_" in capability_name,
                    "allows_merge": capability_name == "merge",
                    "allows_deploy": capability_name == "deploy",
                    "governed": True,
                }
    return deepcopy(governed)


def resolve_capability_profile(capability_name: Optional[str], capability_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    capability_map = capability_map or load_runtime_governed_capabilities()
    if not capability_name:
        return {}
    return deepcopy(capability_map.get(str(capability_name).strip(), {}))
