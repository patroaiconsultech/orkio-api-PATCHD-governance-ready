from __future__ import annotations

from typing import Any, Dict

from app.core.orkio_identity import load_identity


def load_active_identity() -> Dict[str, Any]:
    return load_identity()
