from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class GovernanceDecision(BaseModel):
    action_scope: str
    capability_name: Optional[str] = None
    target_scope: str = "platform"
    allowed: bool
    mission_alignment: bool
    constitution_alignment: bool
    authority_check: bool
    user_protection_check: bool
    truthfulness_check: bool
    authorization_check: bool
    integrity_under_pressure_check: bool
    corruption_resistance_check: bool
    discernment_depth_check: bool
    covenant_fidelity_check: bool
    requires_human_authorization: bool
    authorization_present: bool
    blocked_by: List[str] = []
    reason: str
    constitution_version: str = "v1"
    danielic_integrity_passed: bool = False
