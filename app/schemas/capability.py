from __future__ import annotations

from typing import List
from pydantic import BaseModel


class CapabilityDefinition(BaseModel):
    purpose: str
    risk_level: str
    requires_authorization: bool
    allowed_targets: List[str]
    writes_repository: bool = False
    opens_pull_request: bool = False
    allows_merge: bool = False
    allows_deploy: bool = False
    governed: bool = True
