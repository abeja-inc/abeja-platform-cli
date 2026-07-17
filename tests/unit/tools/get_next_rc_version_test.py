import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[3] / "tools" / "get_next_rc_version.py"
SPEC = importlib.util.spec_from_file_location("get_next_rc_version", MODULE_PATH)
get_next_rc_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(get_next_rc_version)


class PyPIResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


def test_get_pypi_versions_returns_release_names(monkeypatch):
    response = PyPIResponse(b'{"releases":{"2.2.8rc1":[],"2.2.7":[]}}')
    monkeypatch.setattr(get_next_rc_version.urllib.request, "urlopen", lambda *args, **kwargs: response)

    assert get_next_rc_version.get_pypi_versions() == ["2.2.8rc1", "2.2.7"]


def test_get_pypi_versions_raises_on_request_error(monkeypatch):
    def raise_request_error(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(get_next_rc_version.urllib.request, "urlopen", raise_request_error)

    with pytest.raises(RuntimeError, match="Could not fetch versions from PyPI: offline"):
        get_next_rc_version.get_pypi_versions()


def test_get_pypi_versions_raises_when_releases_are_missing(monkeypatch):
    response = PyPIResponse(b'{"info":{}}')
    monkeypatch.setattr(get_next_rc_version.urllib.request, "urlopen", lambda *args, **kwargs: response)

    with pytest.raises(RuntimeError, match="PyPI response does not contain a releases object"):
        get_next_rc_version.get_pypi_versions()


def test_get_version_from_poetry(monkeypatch):
    command = ["poetry", "version", "--short"]

    def return_version(*args, **kwargs):
        assert args == (command,)
        assert kwargs == {
            "cwd": get_next_rc_version.PROJECT_ROOT,
            "check": True,
            "stdout": get_next_rc_version.subprocess.PIPE,
            "text": True,
        }
        return get_next_rc_version.subprocess.CompletedProcess(command, 0, stdout="2.2.8\n")

    monkeypatch.setattr(get_next_rc_version.subprocess, "run", return_version)

    assert get_next_rc_version.get_version_from_poetry() == "2.2.8"


def test_get_version_from_poetry_rejects_empty_output(monkeypatch):
    result = get_next_rc_version.subprocess.CompletedProcess([], 0, stdout="\n")
    monkeypatch.setattr(get_next_rc_version.subprocess, "run", lambda *args, **kwargs: result)

    with pytest.raises(ValueError, match="Poetry returned an empty project version"):
        get_next_rc_version.get_version_from_poetry()


def test_main_fails_when_poetry_command_fails(monkeypatch, capsys):
    error = get_next_rc_version.subprocess.CalledProcessError(
        returncode=1,
        cmd=["poetry", "version", "--short"],
    )

    def raise_poetry_error():
        raise error

    monkeypatch.setattr(get_next_rc_version, "get_version_from_poetry", raise_poetry_error)

    assert get_next_rc_version.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "returned non-zero exit status 1" in captured.err


@pytest.mark.parametrize(
    "existing_versions, expected",
    [
        ([], "2.2.8rc1"),
        (["2.2.8rc1", "2.2.8rc3", "2.2.8", "2.2.9rc9", "invalid"], "2.2.8rc4"),
    ],
)
def test_get_next_rc_version(existing_versions, expected):
    assert get_next_rc_version.get_next_rc_version("2.2.8", existing_versions) == expected


def test_main_prints_next_rc_version(monkeypatch, capsys):
    monkeypatch.setattr(get_next_rc_version, "get_version_from_poetry", lambda: "2.2.8")
    monkeypatch.setattr(get_next_rc_version, "get_pypi_versions", lambda: ["2.2.8rc1"])

    assert get_next_rc_version.main() == 0

    captured = capsys.readouterr()
    assert captured.out == "2.2.8rc2"
    assert captured.err == ""


def test_main_fails_without_printing_rc_version(monkeypatch, capsys):
    monkeypatch.setattr(get_next_rc_version, "get_version_from_poetry", lambda: "2.2.8")

    def raise_lookup_error():
        raise RuntimeError("Could not fetch versions from PyPI: offline")

    monkeypatch.setattr(get_next_rc_version, "get_pypi_versions", raise_lookup_error)

    assert get_next_rc_version.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Could not fetch versions from PyPI: offline\n"
