import stat
import sys
import tempfile
from pathlib import Path

import pytest

from src import config as config_module
from src.config import _harden_env_file_permissions

# La restricción de permisos vía chmod(0o600) solo es verificable en un
# filesystem POSIX real: Windows no distingue bits owner/group/other, así
# que estas dos pruebas se saltan ahí (la lógica de decisión sí se prueba
# en test_noop_on_windows, que no depende del filesystem subyacente).
_HOST_IS_WINDOWS = sys.platform.startswith("win")


@pytest.mark.skipif(_HOST_IS_WINDOWS, reason="chmod en Windows no soporta bits POSIX group/other")
def test_hardens_world_readable_env_file_on_posix(monkeypatch):
    monkeypatch.setattr(config_module, "_is_windows", lambda: False)
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text("TELEGRAM_BOT_TOKEN=x\n")
        env_path.chmod(0o644)  # legible por group/other: debe corregirse

        _harden_env_file_permissions(env_path)

        mode = stat.S_IMODE(env_path.stat().st_mode)
        assert mode == 0o600


@pytest.mark.skipif(_HOST_IS_WINDOWS, reason="chmod en Windows no soporta bits POSIX group/other")
def test_leaves_already_restricted_env_file_untouched(monkeypatch):
    monkeypatch.setattr(config_module, "_is_windows", lambda: False)
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text("TELEGRAM_BOT_TOKEN=x\n")
        env_path.chmod(0o600)

        _harden_env_file_permissions(env_path)

        mode = stat.S_IMODE(env_path.stat().st_mode)
        assert mode == 0o600


def test_noop_on_windows(monkeypatch):
    monkeypatch.setattr(config_module, "_is_windows", lambda: True)
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text("TELEGRAM_BOT_TOKEN=x\n")

        _harden_env_file_permissions(env_path)  # no debe lanzar ni intentar chmod


def test_noop_when_file_does_not_exist(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_is_windows", lambda: False)
    _harden_env_file_permissions(tmp_path / "no-existe.env")
