from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH_ENV = "PMS_CONFIG"
_DEFAULT_CONFIG_PATH = "config.yaml"

_config: dict[str, Any] | None = None


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def load_config(path: Path | None = None) -> dict[str, Any]:
    global _config
    if path is None:
        path = Path(os.environ.get(_CONFIG_PATH_ENV, _DEFAULT_CONFIG_PATH))
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    _config = _expand_env_vars(raw)
    return _config


def get_config() -> dict[str, Any]:
    global _config
    if _config is None:
        load_config()
    return _config


def get_config_path() -> str:
    return os.environ.get(_CONFIG_PATH_ENV, _DEFAULT_CONFIG_PATH)
