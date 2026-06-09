from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote


RUNTIME_FEATURE_FLAGS_VERSION = "AO51_RUNTIME_FEATURE_FLAGS_V1_PREMIUM"


_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled", "enable"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "disabled", "disable"}


def _env_raw(name: str, default: Any = "") -> str:
    value = os.getenv(str(name), default)
    return str(value if value is not None else "").strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = _env_raw(name, "true" if default else "false").lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    return bool(default)


def env_str(name: str, default: str = "") -> str:
    value = _env_raw(name, default)
    return value if value else str(default or "")


def env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = env_str(name, default).strip().lower()
    return value if value in allowed else default


def normalize_whatsapp_number(value: Any = "") -> str:
    raw = str(value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or "5551989697605"


def is_public_orkio_policy_enabled() -> bool:
    return env_bool("ORKIO_PUBLIC_ORKIO_POLICY_ENABLED", True)


def is_public_chris_policy_enabled() -> bool:
    return env_bool("ORKIO_PUBLIC_CHRIS_POLICY_ENABLED", True)


def is_public_orion_policy_enabled() -> bool:
    return env_bool("ORKIO_PUBLIC_ORION_POLICY_ENABLED", True)


def is_amcham_public_journey_enabled() -> bool:
    return env_bool("ORKIO_AMCHAM_PUBLIC_JOURNEY_ENABLED", True)


def is_orion_technical_squad_enabled() -> bool:
    return env_bool("ORKIO_ORION_TECH_SQUAD_ENABLED", True)


def is_platform_self_improvement_enabled() -> bool:
    return env_bool("ORKIO_PLATFORM_SELF_IMPROVEMENT_ENABLED", True)


def is_chris_business_squad_enabled() -> bool:
    return env_bool("ORKIO_CHRIS_BUSINESS_SQUAD_ENABLED", False)


def is_business_self_improvement_enabled() -> bool:
    return env_bool("ORKIO_BUSINESS_SELF_IMPROVEMENT_ENABLED", False)


def is_consultive_success_enabled() -> bool:
    return env_bool("ORKIO_CONSULTIVE_SUCCESS_ENABLED", True)


def get_consultive_team_label() -> str:
    return env_str(
        "ORKIO_CONSULTIVE_TEAM_LABEL",
        "Equipe consultiva premium ORKIO/PATROAI",
    )


def get_consultive_whatsapp_number() -> str:
    return normalize_whatsapp_number(env_str("ORKIO_CONSULTIVE_WHATSAPP_NUMBER", "5551989697605"))


def get_consultive_whatsapp_text() -> str:
    return env_str(
        "ORKIO_CONSULTIVE_WHATSAPP_TEXT",
        "Olá, quero conversar com a equipe ORKIO/PATROAI sobre agentes personalizados para minha empresa.",
    )


def get_consultive_whatsapp_url() -> str:
    number = get_consultive_whatsapp_number()
    text = quote(get_consultive_whatsapp_text())
    return f"https://wa.me/{number}?text={text}"


def get_governed_self_improvement_mode() -> str:
    return env_choice(
        "ORKIO_GOVERNED_SELF_IMPROVEMENT_MODE",
        "readonly",
        {"off", "readonly", "proposal_only", "approved_apply"},
    )


def is_agent_auto_write_allowed() -> bool:
    return env_bool("ORKIO_ALLOW_AGENT_AUTO_WRITE", False)


def is_agent_auto_deploy_allowed() -> bool:
    return env_bool("ORKIO_ALLOW_AGENT_AUTO_DEPLOY", False)


def is_agent_auto_pr_allowed() -> bool:
    return env_bool("ORKIO_ALLOW_AGENT_AUTO_PR", False)


def get_policy_log_level() -> str:
    return env_choice("ORKIO_POLICY_LOG_LEVEL", "info", {"debug", "info", "warning", "error"})


def runtime_feature_flags_snapshot() -> dict[str, Any]:
    """Small readonly snapshot useful for diagnostics.

    Never include secrets or tokens here.
    """
    return {
        "version": RUNTIME_FEATURE_FLAGS_VERSION,
        "public_orkio_policy_enabled": is_public_orkio_policy_enabled(),
        "public_chris_policy_enabled": is_public_chris_policy_enabled(),
        "public_orion_policy_enabled": is_public_orion_policy_enabled(),
        "amcham_public_journey_enabled": is_amcham_public_journey_enabled(),
        "orion_technical_squad_enabled": is_orion_technical_squad_enabled(),
        "platform_self_improvement_enabled": is_platform_self_improvement_enabled(),
        "chris_business_squad_enabled": is_chris_business_squad_enabled(),
        "business_self_improvement_enabled": is_business_self_improvement_enabled(),
        "consultive_success_enabled": is_consultive_success_enabled(),
        "consultive_team_label": get_consultive_team_label(),
        "consultive_whatsapp_number": get_consultive_whatsapp_number(),
        "governed_self_improvement_mode": get_governed_self_improvement_mode(),
        "allow_agent_auto_write": is_agent_auto_write_allowed(),
        "allow_agent_auto_deploy": is_agent_auto_deploy_allowed(),
        "allow_agent_auto_pr": is_agent_auto_pr_allowed(),
        "policy_log_level": get_policy_log_level(),
    }
