"""Point d'entrée en ligne de commande du serveur MCP.

    python -m vivado_mcp --workspace ~/mon_projet                # stdio
    python -m vivado_mcp --workspace ~/mon_projet --transport http --port 8000
    python -m vivado_mcp --workspace ~/mon_projet --selftest      # verification locale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Settings
from .tools import FpgaTools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vivado-mcp",
        description="Serveur MCP pour Vivado / Vitis / simulateurs HDL (voir mcp/README.md).",
    )
    parser.add_argument("--workspace", default=None,
                        help="racine du projet FPGA (toutes les ecritures y sont confinees)")
    parser.add_argument("--tool-root", default=None,
                        help="racine d'installation AMD, ex. /tools/Xilinx (Vivado/Vitis)")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "http", "sse"],
                        help="stdio (defaut, recommandé) ou http pour un serveur partagé")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--selftest", action="store_true",
                        help="n'ouvre pas de transport : affiche l'environnement detecté et sort")
    return parser


def cli_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = Settings.from_env(workspace=args.workspace, tool_root=args.tool_root)
    if not settings.workspace.exists():
        print(f"workspace inexistant : {settings.workspace}", file=sys.stderr)
        return 2

    if args.selftest:
        tools = FpgaTools(settings)
        print(json.dumps({
            "workspace": str(settings.workspace),
            "runs_dir": str(settings.runs_dir),
            "env": json.loads(tools.env_info(deep=False)),
        }, indent=2, ensure_ascii=False))
        return 0

    from .server import build_server      # import tardif : fastmcp peut etre absent

    server = build_server(settings)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport=args.transport, host=args.host, port=args.port)
    return 0


def main() -> int:
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
