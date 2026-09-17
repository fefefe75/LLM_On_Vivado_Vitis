"""Test de fumée du serveur MCP : il doit vraiment démarrer et répondre.

Deux niveaux :
 1. en mémoire (Client(serveur)) — rapide, vérifie le catalogue d'outils ;
 2. via un VRAI sous-processus stdio (`python -m vivado_mcp`) — vérifie que le
    chemin d'installation réel (config CLI, transport, JSON) fonctionne.

Les appels asyncio sont lancés avec asyncio.run pour ne pas dépendre de
pytest-asyncio.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

MCP_DIR = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS = {
    "project_tree",
    "read_text_file",
    "write_text_file",
    "grep",
    "env_info",
    "vivado_run",
    "vitis_run",
    "cocotb_run",
    "job_status",
    "job_list",
    "job_log",
    "job_cancel",
    "report_summary",
    "cocotb_results",
    "project_status",
    "list_hw_targets",
    "program_fpga",
    "wait_for_job",
}


def _payload(result) -> dict | str:
    """Extrait le contenu d'un résultat d'outil, quelle que soit la version de fastmcp.

    Les outils renvoient une chaîne JSON : `result.data` peut donc être cette
    chaîne (pas encore désérialisée) ou un objet structuré.
    """
    data = getattr(result, "data", None)
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    if data not in (None, {}, []):
        return data
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return str(result)


def test_server_exposes_expected_tools(tmp_path: Path) -> None:
    from vivado_mcp.config import Settings
    from vivado_mcp.server import build_server

    server = build_server(Settings.from_env(workspace=str(tmp_path)))

    async def run() -> set[str]:
        async with Client(server) as client:
            tools = await client.list_tools()
            return {tool.name for tool in tools}

    names = asyncio.run(run())
    missing = EXPECTED_TOOLS - names
    assert not missing, f"outils manquants : {missing}"


def test_stdio_subprocess_end_to_end(tmp_path: Path) -> None:
    """Le serveur doit démarrer en sous-processus et répondre à env_info."""
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "top.vhd").write_text("entity top is end entity;\n", encoding="utf-8")

    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "vivado_mcp", "--workspace", str(tmp_path)],
        env={**os.environ, "PYTHONPATH": str(MCP_DIR)},
        cwd=str(MCP_DIR),
    )

    async def run() -> tuple[set[str], dict]:
        async with Client(transport) as client:
            names = {tool.name for tool in await client.list_tools()}
            env = await client.call_tool("env_info", {"deep": False})
            return names, env

    names, env_result = asyncio.run(run())
    assert "vivado_run" in names

    payload = _payload(env_result)
    assert isinstance(payload, dict), payload
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["tools"]["make"]["found"] is True


def test_stdio_reports_refused_path(tmp_path: Path) -> None:
    """Une tentative de sortie du workspace doit remonter comme erreur d'outil."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "vivado_mcp", "--workspace", str(tmp_path)],
        env={**os.environ, "PYTHONPATH": str(MCP_DIR)},
        cwd=str(MCP_DIR),
    )

    async def run() -> bool:
        async with Client(transport) as client:
            try:
                await client.call_tool("read_text_file", {"path": "/etc/passwd"})
                return True
            except Exception:
                return False

    assert asyncio.run(run()) is False, "la lecture hors workspace aurait du être refusée"


def test_selftest_cli(tmp_path: Path) -> None:
    """`python -m vivado_mcp --selftest` doit sortir en 0 avec un JSON valide."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "vivado_mcp", "--workspace", str(tmp_path), "--selftest"],
        cwd=str(MCP_DIR),
        env={**os.environ, "PYTHONPATH": str(MCP_DIR)},
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["workspace"] == str(tmp_path.resolve())
    assert "tools" in payload["env"]


@pytest.mark.parametrize("arg", ["--workspace", "--transport", "--tool-root"])
def test_cli_flags_documented(arg: str) -> None:
    """Les options de la ligne de commande existent (garde-fou anti-dérive)."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "vivado_mcp", "--help"],
        cwd=str(MCP_DIR),
        env={**os.environ, "PYTHONPATH": str(MCP_DIR)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    assert arg in proc.stdout
