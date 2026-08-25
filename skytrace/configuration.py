"""Configuration loading for the integrated SkyTrace pipeline."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "default.yaml"


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the default profile and optionally apply a YAML profile override."""
    try:
        import yaml
    except ImportError as exc:  # Kept explicit for fresh-machine diagnostics.
        raise RuntimeError("PyYAML is required to read SkyTrace configuration. Run pip install -r requirements.txt.") from exc

    default_path = DEFAULT_CONFIG_PATH
    try:
        default_document = yaml.safe_load(default_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise RuntimeError(f"Could not read default configuration: {default_path}") from exc
    if not isinstance(default_document, dict):
        raise RuntimeError(f"Configuration must contain a mapping: {default_path}")
    if path is None or Path(path).resolve() == default_path.resolve():
        return default_document
    profile_path = Path(path)
    try:
        profile_document = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise RuntimeError(f"Could not read configuration: {profile_path}") from exc
    if not isinstance(profile_document, dict):
        raise RuntimeError(f"Configuration must contain a mapping: {profile_path}")
    return _merge(default_document, profile_document)


def configuration_for_report(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to persist; configured paths remain relative when possible."""
    return copy.deepcopy(config)
