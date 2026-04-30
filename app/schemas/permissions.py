from __future__ import annotations

from pydantic import BaseModel


class PermissionRule(BaseModel):
    allowed: bool
    requires_authorization: bool = False
    separate_authorization: bool = False
