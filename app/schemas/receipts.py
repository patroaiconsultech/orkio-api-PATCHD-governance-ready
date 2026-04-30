from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class GovernedReceipt(BaseModel):
    event: str
    mode: str
    repo_target: Optional[str] = None
    branch: Optional[str] = None
    files_changed: List[str] = []
    commit_created: bool = False
    pull_request_opened: bool = False
    merge_executed: bool = False
    deploy_executed: bool = False
    governance_passed: bool = False
    constitution_version: Optional[str] = None
    permission_scope: Optional[str] = None
    danielic_integrity_passed: bool = False
    status: str
    governance_decision: Dict[str, Any] = {}
