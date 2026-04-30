from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.orkio_receipts import build_governed_receipt


def make_governed_receipt(
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
    return build_governed_receipt(
        event=event,
        mode=mode,
        status=status,
        governance_decision=governance_decision,
        repo_target=repo_target,
        branch=branch,
        files_changed=files_changed,
        commit_created=commit_created,
        pull_request_opened=pull_request_opened,
        merge_executed=merge_executed,
        deploy_executed=deploy_executed,
    )
