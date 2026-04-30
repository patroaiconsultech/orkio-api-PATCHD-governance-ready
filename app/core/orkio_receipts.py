from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


def build_governed_receipt(
    *,
    event: str,
    mode: str,
    status: str,
    governance_decision: Dict[str, Any],
    repo_target: Optional[str] = None,
    branch: Optional[str] = None,
    files_changed: Optional[List[str]] = None,
    commit_created: bool = False,
    pull_request_opened: bool = False,
    merge_executed: bool = False,
    deploy_executed: bool = False,
) -> Dict[str, Any]:
    decision = deepcopy(governance_decision or {})
    return {
        "event": event,
        "mode": mode,
        "repo_target": repo_target,
        "branch": branch,
        "files_changed": list(files_changed or []),
        "commit_created": bool(commit_created),
        "pull_request_opened": bool(pull_request_opened),
        "merge_executed": bool(merge_executed),
        "deploy_executed": bool(deploy_executed),
        "governance_passed": bool(decision.get("allowed")),
        "constitution_version": str(decision.get("constitution_version") or "v1"),
        "permission_scope": decision.get("action_scope"),
        "danielic_integrity_passed": bool(decision.get("danielic_integrity_passed", False)),
        "status": status,
        "governance_decision": decision,
    }
