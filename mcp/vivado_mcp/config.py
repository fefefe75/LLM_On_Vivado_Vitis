"""Configuration du serveur MCP.

Tout est surchargeable par variables d'environnement (aucun secret ici) :

    FPGA_MCP_WORKSPACE   racine autorisée en écriture (défaut : cwd)
    FPGA_MCP_RUNS_DIR    dossier des jobs/logs (défaut : <workspace>/.mcp_runs)
    FPGA_MCP_TOOL_ROOT   racine d'installation AMD (ex. /tools/Xilinx)
    FPGA_MCP_TIMEOUT     délai max par job, en secondes (défaut 3600)
    XILINX_VIVADO/VITIS  respectés s'ils sont déjà définis
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# --- binaires autorisés ------------------------------------------------------
# Le serveur refuse tout binaire hors de cette liste : c'est la barrière la plus
# importante, car un serveur MCP est piloté par un LLM.
EDA_BINARIES: tuple[str, ...] = (
    "vivado",
    "vivado_lab",
    "vitis",
    "vitis_hls",
    "v++",
    "xsct",
    "xsim",
    "xvlog",
    "xvhdl",
    "xelab",
    "xsc",
    "bootgen",
    "hw_server",
    "updatemem",
    "ghdl",
    "iverilog",
    "vvp",
    "verilator",
    "questasim",
    "vsim",
    "vlog",
    "vcom",
    "make",
    "cmake",
    "gcc",
    "g++",
    "tclsh",
    "python3",
)

# Outils qui modifient le matériel : ils exigent une confirmation explicite.
DANGEROUS_BINARIES: tuple[str, ...] = ("vivado", "vitis", "xsct", "hw_server")


@dataclass
class Settings:
    """Réglages résolus du serveur (immutables après construction)."""

    workspace: Path
    runs_dir: Path
    tool_root: Path | None = None
    timeout_s: int = 3600
    max_output_bytes: int = 200_000
    max_log_bytes: int = 50_000_000
    allow_outside_workspace_read: bool = False
    allowed_binaries: tuple[str, ...] = field(default=EDA_BINARIES)

    @classmethod
    def from_env(cls, workspace: str | None = None, tool_root: str | None = None) -> "Settings":
        ws = Path(workspace or os.environ.get("FPGA_MCP_WORKSPACE") or os.getcwd()).expanduser().resolve()
        runs = Path(os.environ.get("FPGA_MCP_RUNS_DIR") or (ws / ".mcp_runs")).expanduser().resolve()
        root = tool_root or os.environ.get("FPGA_MCP_TOOL_ROOT")
        return cls(
            workspace=ws,
            runs_dir=runs,
            tool_root=Path(root).expanduser().resolve() if root else None,
            timeout_s=int(os.environ.get("FPGA_MCP_TIMEOUT", "3600")),
        )

    # -- environnement des sous-processus ------------------------------------
    def _tool_bin_dir(self, name: str, executable: str | None = None) -> Path | None:
        """Trouve le dossier bin de Vivado/Vitis, quelle que soit la disposition.

        Arborescences rencontrees en pratique :
          * <tool_root>/<Outil>/<version>/bin  (install complete AMD, /tools/Xilinx)
          * <tool_root>/<version>/<Outil>/bin  (install "par version", ex.
            ~/vivado/2025.2/Vivado/bin)
          * <tool_root>/<Outil>/bin            (Vitis, dont bin/ EST le bon dossier)

        Piege verifie : `<Outil>/*/bin` peut matcher un sous-dossier interne
        (ex. Vitis/vitis-server/bin, Vitis/aietools/bin) AVANT le vrai bin. On
        garde donc tous les candidats et on choisit celui qui contient vraiment
        l'executable demande.
        """
        if not self.tool_root:
            return None
        exe = executable or name.lower()
        patterns = (f"{name}/bin", f"{name}/*/bin", f"*/{name}/bin")
        candidates: list[Path] = []
        for pattern in patterns:
            candidates += [
                path for path in sorted(self.tool_root.glob(pattern), reverse=True)
                if path.is_dir() and path not in candidates
            ]
        for candidate in candidates:
            if (candidate / exe).exists():
                return candidate
        return candidates[0] if candidates else None

    def base_env(self) -> dict[str, str]:
        """Environnement propre pour lancer un outil EDA.

        On reproduit l'effet minimal de `settings64.sh` (que l'on ne peut pas
        sourcer : ce n'est pas un format de configuration) : PATH + les variables
        XILINX_VIVADO / XILINX_VITIS / XILINX_HLS attendues par les outils.
        """
        env = dict(os.environ)
        # Le serveur est BATCH-ONLY : on neutralise DISPLAY pour qu'aucun outil
        # ne tente d'ouvrir une IHM (xsim -gui, Vivado IDE) derriere le dos de
        # l'agent. Les actions graphiques restent a l'humain.
        env["DISPLAY"] = ""
        env.setdefault("LC_ALL", "C.UTF-8")

        for tool, executable, variable in (
            ("Vivado", "vivado", "XILINX_VIVADO"),
            ("Vitis", "vitis", "XILINX_VITIS"),
            ("Vitis_HLS", "vitis_hls", "XILINX_HLS"),
        ):
            bin_dir = self._tool_bin_dir(tool, executable)
            if bin_dir is None:
                continue
            env[variable] = str(bin_dir.parent)
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        return env

    def resolve_binary(self, name: str) -> str | None:
        """Chemin absolu d'un binaire autorisé, ou None."""
        if name not in self.allowed_binaries:
            raise PermissionError(
                f"binaire '{name}' hors de la liste blanche "
                f"(autorisés : {', '.join(self.allowed_binaries)})"
            )
        found = shutil.which(name, path=self.base_env().get("PATH"))
        return found


def default_settings() -> Settings:
    """Réglages utilisés par défaut dans le serveur MCP."""
    return Settings.from_env()
