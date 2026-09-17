"""Serveur MCP exposant Vivado / Vitis / simulation à un agent LLM.

Cible : le paquet autonome `fastmcp` (>= 2.3), qui fonctionne avec n'importe quel
client MCP (Claude Desktop, VS Code/Copilot, Cline, Continue, Hermes, ...).

Lancement :
    python -m vivado_mcp --workspace /chemin/du/projet            # stdio (defaut)
    python -m vivado_mcp --workspace /chemin/du/projet --transport http --port 8000

Les descriptions des outils sont destinées au LLM : elles disent QUAND l'utiliser,
pas seulement ce qu'il fait. Garder cette discipline en ajoutant des outils.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .config import Settings
from .tools import FpgaTools

INSTRUCTIONS = """\
Serveur de pilotage d'outils FPGA (AMD/Xilinx Vivado, Vitis, simulateurs HDL).

Boucle de travail attendue :
 1. env_info()                 -> quels outils sont reellement installes
 2. project_tree() / read_text_file() -> etat du projet
 3. write_text_file()          -> ecrire un module VHDL, un testbench, un .xdc
 4. cocotb_run() puis cocotb_results() -> VERIFIER PAR SIMULATION (obligatoire)
 5. vivado_run(script_path="scripts/build.tcl") -> synthese/implementation/bitstream
 6. job_status()/job_log()     -> suivre et diagnostiquer
 7. report_summary()/project_status() -> timing, utilisation, erreurs

Regles :
 - Ne jamais affirmer qu'un design fonctionne sans un log de simulation ou de build.
 - Les jobs sont asynchrones : job_status renvoie immediatement, job_log donne les
   erreurs filtrees (ne jamais coller 5000 lignes brutes a l'utilisateur).
 - program_fpga est une action materielle : elle exige confirm=True et l'accord
   explicite de l'utilisateur.
 - Toutes les ecritures restent dans le workspace du serveur.
"""


def build_server(settings: Settings | None = None) -> FastMCP:
    """Construit le serveur MCP et enregistre les outils."""
    tools = FpgaTools(settings or Settings.from_env())

    mcp = FastMCP(name="vivado-vitis", instructions=INSTRUCTIONS)

    # ---------------- fichiers ----------------
    @mcp.tool()
    def project_tree(
        path: Annotated[str, Field(description="dossier a explorer, relatif au workspace")] = ".",
        depth: Annotated[int, Field(ge=1, le=8, description="profondeur maximale")] = 3,
    ) -> str:
        """Arborescence du projet : a appeler EN PREMIER pour comprendre la structure."""
        return tools.project_tree(path, depth)

    @mcp.tool()
    def read_text_file(
        path: Annotated[str, Field(description="fichier a lire (VHDL, XDC, Tcl, log...)")],
        max_bytes: Annotated[int, Field(ge=100, le=2_000_000)] = 200_000,
    ) -> str:
        """Lit un fichier texte du projet (tronque a max_bytes)."""
        return tools.read_text_file(path, max_bytes)

    @mcp.tool()
    def write_text_file(
        path: Annotated[str, Field(description="chemin de destination dans le workspace")],
        content: Annotated[str, Field(description="contenu complet du fichier")],
        overwrite: bool = True,
    ) -> str:
        """Écrit (ou remplace) un fichier : VHDL, XDC, Tcl, Python, C, Makefile..."""
        return tools.write_text_file(path, content, overwrite)

    @mcp.tool()
    def grep(
        pattern: Annotated[str, Field(description="expression reguliere recherchee")],
        path: str = ".",
        glob: str = "*",
        max_hits: Annotated[int, Field(ge=1, le=500)] = 100,
    ) -> str:
        """Recherche un motif dans les fichiers du projet (entites, ports, signaux, erreurs)."""
        return tools.grep(pattern, path, glob, max_hits)

    # ---------------- environnement ----------------
    @mcp.tool()
    def env_info(
        deep: Annotated[bool, Field(description="True = execute vivado -version (lent)")] = False,
    ) -> str:
        """Liste les outils EDA disponibles (Vivado, Vitis, xsct, GHDL, cocotb...) et leur version.

        A appeler avant de proposer un flux de travail : tout ce qui n'est pas
        installe ici ne doit pas etre prescrit a l'aveugle.
        """
        return tools.env_info(deep)

    # ---------------- jobs ----------------
    @mcp.tool()
    def vivado_run(
        tcl: Annotated[str | None, Field(description="script Tcl en texte (alternative a script_path)")] = None,
        script_path: Annotated[str | None, Field(description="script Tcl existant dans le projet")] = None,
        tclargs: Annotated[list[str] | None, Field(description="arguments passes a -tclargs")] = None,
        project_dir: Annotated[str | None, Field(description="repertoire d'execution (cwd)")] = None,
        timeout_s: Annotated[int | None, Field(ge=5, le=86_400)] = None,
        name: Annotated[str | None, Field(description="nom du fichier Tcl genere")] = None,
    ) -> dict:
        """Lance Vivado en mode batch sur un script Tcl (synthèse, implémentation, bitstream, rapports).

        Renvoie un job : suivre avec job_status, lire les erreurs avec job_log.
        Fournir soit `tcl` (texte), soit `script_path` (fichier existant), jamais les deux.
        """
        return tools.vivado_run(tcl, script_path, tclargs, project_dir, timeout_s, name)

    @mcp.tool()
    def vitis_run(
        tcl: Annotated[str | None, Field(description="script (texte) a executer")] = None,
        script_path: Annotated[str | None, Field(description="script existant dans le projet")] = None,
        workspace_dir: str | None = None,
        unified: Annotated[bool, Field(description="True = Vitis >= 2023.2 (vitis -s), False = xsct <= 2023.1")] = False,
        timeout_s: Annotated[int | None, Field(ge=5, le=86_400)] = None,
    ) -> dict:
        """Lance Vitis en ligne de commande (création de plateforme/app, build, download).

        Deux générations incompatibles : `unified=False` -> `xsct script.tcl` (<= 2023.1),
        `unified=True` -> `vitis -s script` (>= 2023.2). L'export XSA doit exister avant.
        """
        return tools.vitis_run(tcl, script_path, workspace_dir, unified, timeout_s)

    @mcp.tool()
    def cocotb_run(
        tb_dir: Annotated[str, Field(description="dossier du testbench contenant le Makefile")],
        sim: Annotated[str, Field(description="ghdl | icarus | verilator | questa")] = "ghdl",
        testcase: Annotated[str | None, Field(description="nom d'un seul test a executer")] = None,
        waves: bool = False,
        seed: int = 1234,
        timeout_s: Annotated[int | None, Field(ge=5, le=14_400)] = None,
    ) -> dict:
        """Lance un testbench cocotb (`make`) : la vérification par simulation avant toute synthèse.

        cocotb ne supporte pas XSim : utiliser ghdl (VHDL, libre), icarus/verilator
        (Verilog) ou questa (licence). Le verdict se lit ensuite via cocotb_results.
        """
        return tools.cocotb_run(tb_dir, sim, testcase, waves, seed, timeout_s)

    @mcp.tool()
    def job_status(
        job_id: str,
        wait_s: Annotated[int, Field(ge=0, le=600, description="0 = retour immediat")] = 0,
    ) -> str:
        """État d'un job : running / ok / failed / timeout / cancelled + code retour et durée."""
        return tools.job_status(job_id, wait_s)

    @mcp.tool()
    def job_list(limit: Annotated[int, Field(ge=1, le=100)] = 20) -> str:
        """Liste les jobs récents : utile quand l'identifiant d'un job a été perdu."""
        return tools.job_list(limit)

    @mcp.tool()
    def job_log(
        job_id: str,
        pattern: Annotated[str | None, Field(description="regex de filtrage des lignes")] = None,
        tail: Annotated[int, Field(ge=1, le=2000)] = 200,
        errors_only: bool = False,
    ) -> str:
        """Diagnostic d'un job : erreurs et avertissements extraits du log (+ lignes filtrées).

        C'est l'outil à utiliser quand un build échoue : il évite de rapatrier le log entier.
        """
        return tools.job_log(job_id, pattern, tail, errors_only)

    @mcp.tool()
    def job_cancel(job_id: str) -> str:
        """Arrête un job en cours (SIGTERM sur le groupe de processus, puis SIGKILL)."""
        return tools.job_cancel(job_id)

    # ---------------- rapports ----------------
    @mcp.tool()
    def report_summary(
        path: Annotated[str, Field(description="fichier de rapport ou log Vivado")],
    ) -> str:
        """Analyse un rapport Vivado : messages ERROR/WARNING par code, WNS/TNS/WHS/THS, ressources."""
        return tools.report_summary(path)

    @mcp.tool()
    def cocotb_results(
        tb_dir: Annotated[str, Field(description="dossier du testbench")] = ".",
    ) -> str:
        """Verdict PASS/FAIL par test d'un testbench cocotb (lecture de results.xml + messages d'échec)."""
        return tools.cocotb_results(tb_dir)

    @mcp.tool()
    def project_status(project_dir: str = ".") -> str:
        """État d'un projet Vivado : runs présents, timing, utilisation, bitstreams. Ne lance rien."""
        return tools.project_status(project_dir)

    # ---------------- matériel ----------------
    @mcp.tool()
    def list_hw_targets(timeout_s: Annotated[int, Field(ge=5, le=600)] = 120) -> dict:
        """Liste les cibles JTAG visibles (connexion au hw_server local)."""
        return tools.list_hw_targets(timeout_s)

    @mcp.tool()
    def program_fpga(
        bitstream: Annotated[str, Field(description="fichier .bit ou .pdi a charger")],
        device: Annotated[str | None, Field(description="nom du device si plusieurs")] = None,
        confirm: Annotated[bool, Field(description="True = l'utilisateur a explicitement accepte")] = False,
        timeout_s: Annotated[int, Field(ge=5, le=3600)] = 600,
    ) -> dict:
        """Programme le FPGA par JTAG. ACTION MATÉRIELLE : demander l'accord, puis confirm=True."""
        return tools.program_fpga(bitstream, device, confirm, timeout_s)

    @mcp.tool()
    def wait_for_job(job_id: str, max_wait_s: Annotated[int, Field(ge=1, le=600)] = 60) -> str:
        """Attend (borné) la fin d'un job et renvoie son résumé + ses erreurs."""
        return tools.wait_for_job(job_id, max_wait_s)

    return mcp


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande (voir __main__.py)."""
    from .__main__ import cli_main

    return cli_main(argv)
