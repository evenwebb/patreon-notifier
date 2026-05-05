from pathlib import Path

import pytest

from patreon_notifier.config_loader import load_config


def test_load_example_config_from_custom_root(tmp_path: Path) -> None:
    repo_dir = Path(__file__).resolve().parents[1]
    (tmp_path / "config.example.py").write_text(
        (repo_dir / "config.example.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert hasattr(cfg, "APPRISE_URLS")


def test_load_config_raises_when_no_config_files(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No configuration file found"):
        load_config(tmp_path)
