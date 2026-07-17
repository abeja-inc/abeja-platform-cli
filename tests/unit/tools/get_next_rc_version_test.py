import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[3] / "tools" / "get_next_rc_version.py"
SPEC = importlib.util.spec_from_file_location("get_next_rc_version", MODULE_PATH)
get_next_rc_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(get_next_rc_version)


def test_get_pypi_versions_raises_on_request_error(monkeypatch):
    def raise_request_error(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(get_next_rc_version.urllib.request, "urlopen", raise_request_error)

    with pytest.raises(RuntimeError, match="Could not fetch versions from PyPI: offline"):
        get_next_rc_version.get_pypi_versions()


def test_main_fails_without_printing_rc_version(monkeypatch, capsys):
    monkeypatch.setattr(get_next_rc_version, "get_version_from_pyproject", lambda: "2.2.8")

    def raise_lookup_error():
        raise RuntimeError("Could not fetch versions from PyPI: offline")

    monkeypatch.setattr(get_next_rc_version, "get_pypi_versions", raise_lookup_error)

    assert get_next_rc_version.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Could not fetch versions from PyPI: offline\n"
