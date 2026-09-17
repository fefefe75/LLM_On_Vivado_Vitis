"""Tests des barrières de sécurité (sans Vivado, sans MCP)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vivado_mcp.config import EDA_BINARIES, Settings
from vivado_mcp.safety import PathRefused, check_binary, resolve_in_workspace, write_tcl


def test_resolve_relative_inside(tmp_path: Path) -> None:
    (tmp_path / "rtl").mkdir()
    assert resolve_in_workspace(tmp_path, "rtl") == (tmp_path / "rtl").resolve()


def test_resolve_absolute_inside(tmp_path: Path) -> None:
    target = tmp_path / "tb" / "test_x.py"
    target.parent.mkdir()
    target.write_text("# test\n")
    assert resolve_in_workspace(tmp_path, target, must_exist=True) == target.resolve()


@pytest.mark.parametrize("candidate", [
    "../secret.txt",
    "rtl/../../secret.txt",
    "/etc/passwd",
    "~/secret",
])
def test_escapes_are_refused(tmp_path: Path, candidate: str) -> None:
    with pytest.raises(PathRefused):
        resolve_in_workspace(tmp_path, candidate)


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    """Un lien symbolique ne doit pas permettre de sortir du workspace."""
    outside = tmp_path.parent / "hors_projet"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "lien"
    if link.exists():
        link.unlink()
    link.symlink_to(outside)
    with pytest.raises(PathRefused):
        resolve_in_workspace(tmp_path, "lien/fichier.txt")


def test_missing_file_reports_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_in_workspace(tmp_path, "absent.vhd", must_exist=True)
    assert str(tmp_path) in str(excinfo.value)


def test_null_byte_refused(tmp_path: Path) -> None:
    with pytest.raises(PathRefused):
        resolve_in_workspace(tmp_path, "rtl/a\x00b.vhd")


def test_check_binary_allowlist() -> None:
    check_binary("vivado", EDA_BINARIES)          # dans la liste : OK
    with pytest.raises(PermissionError):
        check_binary("rm", EDA_BINARIES)          # hors liste : refusé
    with pytest.raises(PermissionError):
        check_binary("/usr/bin/vivado", EDA_BINARIES)   # chemin absolu : refusé
    with pytest.raises(PermissionError):
        check_binary("", EDA_BINARIES)


def test_write_tcl_sanitises_name(tmp_path: Path) -> None:
    script = write_tcl(tmp_path, "../../evil tcl.tcl", "puts hello")
    assert script.parent == tmp_path / "scripts" / "generated"
    assert script.name == "evil tcl.tcl".replace(" ", "_") or "evil" in script.name
    assert tmp_path in script.parents                # jamais hors du projet
    assert script.read_text().startswith("puts hello")


def test_write_tcl_forces_extension(tmp_path: Path) -> None:
    script = write_tcl(tmp_path, "build", "puts ok")
    assert script.name == "build.tcl"


def test_write_tcl_overwrites_atomically(tmp_path: Path) -> None:
    first = write_tcl(tmp_path, "a.tcl", "puts 1")
    second = write_tcl(tmp_path, "a.tcl", "puts 2")
    assert first == second
    assert second.read_text().strip() == "puts 2"
    leftovers = list((tmp_path / "scripts" / "generated").glob("*.tmp"))
    assert leftovers == []


def test_settings_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FPGA_MCP_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FPGA_MCP_TIMEOUT", "42")
    settings = Settings.from_env()
    assert settings.workspace == tmp_path.resolve()
    assert settings.runs_dir == tmp_path.resolve() / ".mcp_runs"
    assert settings.timeout_s == 42


def test_settings_env_for_batch(tmp_path: Path) -> None:
    settings = Settings.from_env(workspace=str(tmp_path))
    env = settings.base_env()
    assert env["DISPLAY"] == ""            # force le mode batch
    assert env.get("LC_ALL") == "C.UTF-8"
