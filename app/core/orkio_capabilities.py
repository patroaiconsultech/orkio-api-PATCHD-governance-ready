from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


ORKIO_GOVERNED_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "platform_self_audit": {
        "purpose": "auditar a plataforma em modo leitura",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["platform", "backend", "frontend"],
        "writes_repository": False,
        "opens_pull_request": False,
        "allows_merge": False,
        "allows_deploy": False,
        "governed": True,
    },
    "github_repo_read": {
        "purpose": "ler repositórios e comparar estado de PR",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "writes_repository": False,
        "opens_pull_request": False,
        "allows_merge": False,
        "allows_deploy": False,
        "governed": True,
    },
    "github_pr_compare_status": {
        "purpose": "comparar branch/PR em modo leitura",
        "risk_level": "low",
        "requires_authorization": False,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "writes_repository": False,
        "opens_pull_request": False,
        "allows_merge": False,
        "allows_deploy": False,
        "governed": True,
    },
    "github_repo_write": {
        "purpose": "aplicar patch em branch governada",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "writes_repository": True,
        "opens_pull_request": False,
        "allows_merge": False,
        "allows_deploy": False,
        "governed": True,
    },
    "github_pr_prepare": {
        "purpose": "preparar ou abrir PR governada",
        "risk_level": "medium",
        "requires_authorization": True,
        "allowed_targets": ["backend", "frontend", "cross_repo"],
        "writes_repository": True,
        "opens_pull_request": True,
        "allows_merge": False,
        "allows_deploy": False,
        "governed": True,
    },
}


def load_governed_capabilities() -> Dict[str, Dict[str, Any]]:
    return deepcopy(ORKIO_GOVERNED_CAPABILITIES)
