"""
Shared configuration loader with `${ENV_VAR:default}` placeholder resolution.

The YAML configuration uses values such as::

    xgboost_model_path: ${XGB_MODEL_PATH:models/tci_degradation_xgb.model}
    api.port: ${API_PORT:8000}

Plain ``yaml.safe_load`` passes these through verbatim, so the literal string
``${XGB_MODEL_PATH:models/tci_degradation_xgb.model}`` would be handed to the
filesystem and the model load would fail. This loader resolves such
placeholders at load time:

* If ``ENV_VAR`` is set in the environment, its value is used.
* Otherwise the ``default`` after the colon is used.
* If there is no colon, the whole placeholder is the variable name and resolves
  to an empty string when unset.

Resolution is applied recursively across nested dicts and lists. Non-string
scalars (booleans, ints, floats) are returned untouched.
"""
from __future__ import annotations

import os
import re
from typing import Any

import yaml

_PLACEHOLDER = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def _resolve(value: Any) -> Any:
    """Recursively resolve ${VAR:default} placeholders in a config tree."""
    if isinstance(value, str):
        def _replace(match: "re.Match[str]") -> str:
            var_name = match.group(1)
            default = match.group(2)
            return os.environ.get(var_name, default if default is not None else "")
        return _PLACEHOLDER.sub(_replace, value)
    if isinstance(value, dict):
        return {key: _resolve(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_resolve(item) for item in value]
    return value


def load_config(path: str = "config/settings.yaml") -> dict:
    """Load a YAML config file and resolve any ${ENV_VAR:default} placeholders."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except Exception:  # pragma: no cover - defensive; prefer empty config
        return {}
    return _resolve(raw)


def resolve_placeholders(value: Any) -> Any:
    """Public helper: resolve placeholders in an already-parsed config fragment."""
    return _resolve(value)
