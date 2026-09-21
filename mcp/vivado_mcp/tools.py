"""Outils réels du serveur MCP, sans dépendance à une bibliothèque MCP.

Séparer la logique du transport permet de la tester sans client MCP et de
l'exposer aussi bien via fastmcp (paquet autonome) que via le `Server` bas
niveau du SDK officiel, ou même en ligne de commande pour déboguer.

Chaque méthode publique correspond à un outil MCP ; voir `server.py` pour la
description destinée au LLM.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import Settings
from .jobs import JobManager
from .reports import parse_cocotb_results, read_text, summarize_log, to_json
from .safety import check_binary, resolve_in_workspace, write_tcl

QUICK_VERSION_COMMANDS: tuple[tuple[str, list[str], str], ...] = (
    ("vivado", ["vivado", "-version"], "AMD/Xilinx Vivado"),
    ("vitis", ["vitis", "-version"], "AMD/Xilinx Vitis"),
    ("xsct", ["xsct", "-version"], "Xilinx XSCT (Vitis classique)"),
    ("xsim", ["xsim", "--version"], "Xilinx XSim"),
    ("ghdl", ["ghdl", "--version"], "GHDL (simulateur VHDL libre)"),
    ("iverilog", ["iverilog", "-V"], "Icarus Verilog"),
    ("verilator", ["verilator", "--version"], "Verilator"),
    ("vsim", ["vsim", "-version"], "Questa/ModelSim"),
    ("cocotb-config", ["cocotb-config", "--version"], "cocotb (framework Python)"),
    ("tclsh", ["tclsh"], "Tcl"),
    ("make", ["make", "--version"], "GNU make"),
)


class FpgaTools:
    """Implémentation de tous les outils exposés au LLM."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobManager(settings.runs_dir, max_log_bytes=settings.max_log_bytes)

    # ------------------------------------------------------------------ #
    # Fichiers
    # ------------------------------------------------------------------ #
    def project_tree(self, path: str = ".", depth: int = 3, max_entries: int = 400) -> str:
        """Arborescence du projet (les dossiers de build sont ignorés)."""
        root = resolve_in_workspace(self.settings.workspace, path, must_exist=True)
        ignored = {
            ".git", "sim_build", ".Xil", ".runs", ".sim", ".cache", "__pycache__",
            ".ip_user_files", "xsim.dir", "work", ".mcp_runs", "_dbg",
        }
        lines: list[str] = []
        count = 0

        def walk(directory: Path, prefix: str, level: int) -> None:
            nonlocal count
            if level > depth or count >= max_entries:
                return
            try:
                entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if entry.name in ignored or count >= max_entries:
                    continue
                count += 1
                lines.append(f"{prefix}{entry.name}{'/' if entry.is_dir() else ''}")
                if entry.is_dir():
                    walk(entry, prefix + "  ", level + 1)

        lines.append(f"{root}/")
        walk(root, "  ", 1)
        if count >= max_entries:
            lines.append(f"... [tronque a {max_entries} entrees]")
        return "\n".join(lines)

    def read_text_file(self, path: str, max_bytes: int = 200_000) -> str:
        """Contenu d'un fichier texte du projet."""
        target = resolve_in_workspace(self.settings.workspace, path, must_exist=True)
        if target.is_dir():
            raise IsADirectoryError(f"{target} est un dossier ; utiliser project_tree")
        return read_text(target, max_bytes=max_bytes)

    def write_text_file(self, path: str, content: str, overwrite: bool = True) -> str:
        """Écrit un fichier (VHDL, XDC, Tcl, Python...) dans le projet."""
        target = resolve_in_workspace(self.settings.workspace, path)
        if target.exists() and not overwrite:
            raise FileExistsError(f"{target} existe deja (overwrite=False)")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
        return f"{target} written ({len(content)} characters)"

    def grep(self, pattern: str, path: str = ".", glob: str = "*", max_hits: int = 100) -> str:
        """Recherche un motif (regex) dans les fichiers texte du projet."""
        import re

        root = resolve_in_workspace(self.settings.workspace, path, must_exist=True)
        rx = re.compile(pattern)
        hits: list[str] = []
        candidates = [root] if root.is_file() else sorted(root.rglob(glob))
        for file in candidates:
            if not file.is_file() or file.stat().st_size > 2_000_000:
                continue
            if any(part in {".git", "sim_build", "__pycache__", ".Xil"} for part in file.parts):
                continue
            try:
                text = read_text(file, max_bytes=2_000_000)
            except OSError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{file.relative_to(self.settings.workspace)}:{n}: {line.strip()[:200]}")
                    if len(hits) >= max_hits:
                        return "\n".join(hits) + f"\n... [tronque a {max_hits} resultats]"
        return "\n".join(hits) if hits else "aucun resultat"

    # ------------------------------------------------------------------ #
    # Environnement
    # ------------------------------------------------------------------ #
    def env_info(self, deep: bool = False) -> str:
        """Détecte les outils EDA disponibles et leur version.

        `deep=True` exécute aussi `vivado -version` / `vitis -version`, ce qui
        prend plusieurs secondes (chargement des bibliothèques AMD).
        """
        report: dict[str, object] = {
            "workspace": str(self.settings.workspace),
            "runs_dir": str(self.settings.runs_dir),
            "tool_root": str(self.settings.tool_root) if self.settings.tool_root else None,
            "python": f"{sys.version.split()[0]} ({sys.executable})",
            "tools": {},
        }
        tools: dict[str, dict] = {}
        for name, cmd, label in QUICK_VERSION_COMMANDS:
            path = shutil.which(name, path=self.settings.base_env().get("PATH"))
            entry: dict[str, object] = {"label": label, "path": path, "found": bool(path)}
            if path and deep:
                try:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=120,
                        env=self.settings.base_env(),
                    )
                    head = (proc.stdout or proc.stderr or "").strip().splitlines()[:3]
                    entry["version"] = " | ".join(head) if head else f"code retour {proc.returncode}"
                except (OSError, subprocess.TimeoutExpired) as exc:
                    entry["version"] = f"echec de detection : {exc}"
            tools[name] = entry
        report["tools"] = tools
        report["notes"] = [
            "cocotb ne supporte pas XSim : pour du VHDL sans licence, utiliser GHDL + cocotb.",
            "Vitis >= 2023.2 : IDE unifie (commande 'vitis -s script'). Vitis <= 2023.1 : 'xsct script.tcl'.",
            "En mode batch, ajouter -nolog -nojournal pour ne pas polluer le projet.",
        ]
        return json.dumps(report, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Jobs
    # ------------------------------------------------------------------ #
    def _run(self, kind: str, binary: str, args: list[str], cwd: Path,
             timeout_s: int | None = None, log_name: str | None = None) -> dict:
        check_binary(binary, self.settings.allowed_binaries)
        exe = self.settings.resolve_binary(binary)
        if exe is None:
            raise FileNotFoundError(
                f"{binary} introuvable dans le PATH. Indiquer la racine d'installation AMD "
                f"via FPGA_MCP_TOOL_ROOT, ou sourcer settings64.sh de Vivado avant de lancer le serveur."
            )
        job = self.jobs.start(
            kind=kind,
            argv=[exe, *args],
            cwd=cwd,
            env=self.settings.base_env(),
            timeout_s=timeout_s or self.settings.timeout_s,
            log_name=log_name,
        )
        return job.summary()

    def vivado_run(
        self,
        tcl: str | None = None,
        script_path: str | None = None,
        tclargs: list[str] | None = None,
        project_dir: str | None = None,
        timeout_s: int | None = None,
        name: str | None = None,
    ) -> dict:
        """Lance Vivado en mode batch sur un script Tcl (fourni en texte ou en fichier).

        Mode batch uniquement : jamais d'IHM, jamais de session interactive.
        """
        if bool(tcl) == bool(script_path):
            raise ValueError("fournir EXACTEMENT l'un des deux : tcl (texte) ou script_path")

        cwd = resolve_in_workspace(self.settings.workspace, project_dir or ".", must_exist=True)
        if tcl is not None:
            script = write_tcl(self.settings.workspace, name or "llm_script.tcl", tcl)
        else:
            script = resolve_in_workspace(self.settings.workspace, script_path, must_exist=True)

        args = ["-mode", "batch", "-source", str(script), "-nolog", "-nojournal", "-notrace"]
        args += ["-tclargs", *(tclargs or [])]
        return self._run("vivado", "vivado", args, cwd, timeout_s, log_name=None)

    def vitis_run(
        self,
        tcl: str | None = None,
        script_path: str | None = None,
        workspace_dir: str | None = None,
        unified: bool = False,
        timeout_s: int | None = None,
    ) -> dict:
        """Lance Vitis en ligne de commande.

        `unified=False` (Vivado/Vitis <= 2023.1) : `xsct <script.tcl>`.
        `unified=True`  (Vitis >= 2023.2)        : `vitis -s <script>`.
        """
        if bool(tcl) == bool(script_path):
            raise ValueError("fournir EXACTEMENT l'un des deux : tcl (texte) ou script_path")

        cwd = resolve_in_workspace(self.settings.workspace, workspace_dir or ".", must_exist=True)
        if tcl is not None:
            script = write_tcl(self.settings.workspace, "llm_vitis_script.tcl", tcl)
        else:
            script = resolve_in_workspace(self.settings.workspace, script_path, must_exist=True)

        if unified:
            return self._run("vitis", "vitis", ["-s", str(script)], cwd, timeout_s)
        return self._run("xsct", "xsct", [str(script)], cwd, timeout_s)

    def cocotb_run(
        self,
        tb_dir: str,
        sim: str = "ghdl",
        testcase: str | None = None,
        waves: bool = False,
        seed: int = 1234,
        timeout_s: int | None = None,
        extra_args: list[str] | None = None,
    ) -> dict:
        """Lance un testbench cocotb (`make` dans tb_dir) et renvoie le job créé."""
        cwd = resolve_in_workspace(self.settings.workspace, tb_dir, must_exist=True)
        env_overrides = {
            "SIM": sim,
            "WAVES": "1" if waves else "0",
            "COCOTB_RANDOM_SEED": str(seed),
        }
        if testcase:
            env_overrides["COCOTB_TESTCASE"] = testcase
        args = [*(extra_args or [])]

        check_binary("make", self.settings.allowed_binaries)
        exe = self.settings.resolve_binary("make")
        assert exe is not None
        env = self.settings.base_env()
        env.update(env_overrides)
        job = self.jobs.start(
            kind=f"cocotb-{sim}",
            argv=[exe, *args],
            cwd=cwd,
            env=env,
            timeout_s=timeout_s or min(self.settings.timeout_s, 1800),
        )
        summary = job.summary()
        summary["hint"] = (
            "apres la fin du job, appeler cocotb_results(tb_dir) pour le detail "
            "PASS/FAIL, et job_log(job_id) pour la trace."
        )
        return summary

    def job_status(self, job_id: str, wait_s: int = 0) -> str:
        """État d'un job (option : attendre jusqu'à `wait_s` secondes)."""
        if wait_s:
            return to_json(self.jobs.wait(job_id, max_wait_s=float(wait_s)))
        return to_json(self.jobs.get(job_id).summary())

    def job_list(self, limit: int = 20) -> str:
        """Liste des jobs récents (le plus récent d'abord)."""
        return to_json({"jobs": self.jobs.list_jobs(limit)})

    def job_log(self, job_id: str, pattern: str | None = None, tail: int = 200,
                errors_only: bool = False, context: int = 2) -> str:
        """Extrait d'un log de job : erreurs/avertissements résumés et lignes filtrées.

        `pattern` est une expression régulière ; `errors_only=True` renvoie
        uniquement les lignes qui ressemblent à des erreurs.
        """
        job = self.jobs.get(job_id)
        scan = job.scan()
        result: dict[str, object] = {
            "job": job.summary(),
            "error_count": scan["error_count"],
            "warning_count": scan["warning_count"],
            "errors": scan["errors"],
            "warnings": scan["warnings"],
        }
        if pattern:
            result["matches"] = job.matches(pattern)[-tail:]
        elif not errors_only:
            result["tail"] = scan["tail"][-tail:]
        return to_json(result)

    def job_cancel(self, job_id: str) -> str:
        """Arrête un job (SIGTERM sur le groupe de processus, puis SIGKILL)."""
        return to_json(self.jobs.cancel(job_id))

    # ------------------------------------------------------------------ #
    # Rapports
    # ------------------------------------------------------------------ #
    def report_summary(self, path: str) -> str:
        """Analyse un rapport ou un log Vivado (messages, timing, utilisation)."""
        target = resolve_in_workspace(self.settings.workspace, path, must_exist=True)
        if target.is_dir():
            raise IsADirectoryError(f"{target} est un dossier : donner un fichier de rapport")
        result = summarize_log(target)
        result["messages"].pop("messages", None)          # detail complet via parse séparé
        return to_json(result)

    def cocotb_results(self, tb_dir: str = ".") -> str:
        """Lit results.xml d'un testbench cocotb et renvoie le verdict par test."""
        cwd = resolve_in_workspace(self.settings.workspace, tb_dir, must_exist=True)
        candidates = [cwd / "results.xml", *(p for p in cwd.rglob("results.xml") if p.is_file())]
        for candidate in candidates:
            if candidate.exists():
                payload = parse_cocotb_results(candidate)
                payload["file"] = str(candidate)
                return to_json(payload)
        return to_json({"parsed": False, "note": f"aucun results.xml sous {cwd}"})

    def project_status(self, project_dir: str = ".") -> str:
        """Résumé d'un projet Vivado : runs terminés, timing, utilisation, erreurs.

        Ne lance rien : lit les rapports déjà écrits par des jobs précédents.
        """
        root = resolve_in_workspace(self.settings.workspace, project_dir, must_exist=True)
        runs = sorted({p.parent.name for p in root.rglob("runme.log")})
        payload: dict[str, object] = {
            "project_dir": str(root),
            "runs_found": runs,
            "artefacts": {},
        }
        for name in ("timing", "utilization", "drc"):
            files = sorted(root.rglob(f"*{name}*.rpt"))
            payload["artefacts"][name] = [str(p.relative_to(root)) for p in files[-3:]]
        summary_files = sorted(root.rglob("timing_summary.rpt"))
        if summary_files:
            payload["timing"] = summarize_log(summary_files[-1])["timing"]
        bitstreams = sorted(root.rglob("*.bit")) + sorted(root.rglob("*.pdi"))
        payload["bitstreams"] = [str(p.relative_to(root)) for p in bitstreams]
        return to_json(payload)

    # ------------------------------------------------------------------ #
    # Matériel (actions à confirmer)
    # ------------------------------------------------------------------ #
    def list_hw_targets(self, timeout_s: int = 120) -> dict:
        """Liste les cibles JTAG visibles (hw_server local)."""
        tcl = (
            "open_hw_manager\n"
            "connect_hw_server -url localhost:3121\n"
            "foreach t [get_hw_targets] { puts \"TARGET $t\" }\n"
            "close_hw_manager\n"
        )
        return self.vivado_run(tcl=tcl, name="list_hw_targets.tcl", timeout_s=timeout_s)

    def program_fpga(self, bitstream: str, device: str | None = None, confirm: bool = False,
                     timeout_s: int = 600) -> dict:
        """Programme le FPGA via JTAG. ACTION MATÉRIELLE : `confirm=True` obligatoire."""
        if not confirm:
            return {
                "refused": True,
                "reason": (
                    "program_fpga modifie le FPGA : rappeler a l'utilisateur l'effet exact "
                    "(carte reprogrammee, design en cours perdu) puis relancer avec confirm=True"
                ),
            }
        target = resolve_in_workspace(self.settings.workspace, bitstream, must_exist=True)
        device = device or "xc7z020_1"        # a remplacer par [get_hw_devices] sur la vraie carte
        tcl = (
            "open_hw_manager\n"
            "connect_hw_server -allow_non_jtag\n"
            "set dev [lindex [get_hw_devices] 0]\n"
            f"current_hw_device $dev ; set_property PROGRAM.FILE {{{target}}} $dev\n"
            "program_hw_devices $dev\n"
            "close_hw_manager\n"
        )
        return self.vivado_run(tcl=tcl, name="program.tcl", timeout_s=timeout_s)

    # ------------------------------------------------------------------ #
    # Divers
    # ------------------------------------------------------------------ #
    def wait_for_job(self, job_id: str, max_wait_s: int = 60) -> str:
        """Attend la fin d'un job (borné) puis renvoie son résumé et ses erreurs."""
        summary = self.jobs.wait(job_id, max_wait_s=float(max_wait_s))
        scan = self.jobs.get(job_id).scan()
        return to_json({"job": summary, "errors": scan["errors"], "error_count": scan["error_count"]})

    def sleep_until_ready(self, seconds: float = 1.0) -> str:
        """Petite attente explicite (utile entre deux étapes dépendantes)."""
        seconds = max(0.0, min(seconds, 30.0))
        time.sleep(seconds)
        return f"attente de {seconds} s terminee"
