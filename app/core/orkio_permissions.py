from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


ORKIO_PERMISSION_MATRIX: Dict[str, Any] = {
    "version": "v1",
    "rules": {
        "read": {"allowed": True, "requires_authorization": False, "separate_authorization": False},
        "diagnose": {"allowed": True, "requires_authorization": False, "separate_authorization": False},
        "propose_patch": {"allowed": True, "requires_authorization": False, "separate_authorization": False},
        "write_branch": {"allowed": True, "requires_authorization": True, "separate_authorization": False},
        "open_pr": {"allowed": True, "requires_authorization": True, "separate_authorization": False},
        "merge": {"allowed": False, "requires_authorization": True, "separate_authorization": True},
        "deploy": {"allowed": False, "requires_authorization": True, "separate_authorization": True},
    },
    "active": True,
}


def load_permissions() -> Dict[str, Any]:
    return deepcopy(ORKIO_PERMISSION_MATRIX)


def get_permission_rule(action_scope: str) -> Dict[str, Any]:
    rules = ORKIO_PERMISSION_MATRIX.get("rules") or {}
    rule = rules.get(action_scope) or {}
    return {
        "allowed": bool(rule.get("allowed", False)),
        "requires_authorization": bool(rule.get("requires_authorization", False)),
        "separate_authorization": bool(rule.get("separate_authorization", False)),
    }
