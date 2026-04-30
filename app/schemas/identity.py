from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel


class IdentityProfile(BaseModel):
    name: str
    version: str
    nature: str
    mission: str
    vision: str
    tone: List[str]
    core_promise: str
    spiritual_governance: Dict[str, str]
    created_by: str
    active: bool = True
