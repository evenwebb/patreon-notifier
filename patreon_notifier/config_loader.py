"""
Load user configuration from the repository root.

Looks for ``config.py`` (gitignored), then falls back to ``config.example.py``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module_from_path(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name!r} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project_root() -> Path:
    """Directory containing ``config.py`` / ``config.example.py`` (repo root)."""
    return Path(__file__).resolve().parent.parent


def load_config(root: Path | None = None) -> ModuleType:
    """
    Load configuration as a module.

    Args:
        root: Project root; defaults to the parent of the ``patreon_notifier`` package.

    Priority:
        1) ``config.py`` if present
        2) ``config.example.py``
    """
    base_dir = project_root() if root is None else root.resolve()

    config_py = base_dir / "config.py"
    if config_py.exists():
        return _load_module_from_path("config", config_py)

    config_example_py = base_dir / "config.example.py"
    if config_example_py.exists():
        return _load_module_from_path("config_example", config_example_py)

    raise FileNotFoundError(
        "No configuration file found. Expected either 'config.py' or 'config.example.py' "
        f"under {base_dir}."
    )


config = load_config()
