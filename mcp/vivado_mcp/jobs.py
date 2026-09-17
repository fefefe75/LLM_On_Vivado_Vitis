"""Gestion des jobs EDA (synthèse, implémentation, simulation, Vitis...).

Un job Vivado dure de quelques secondes à plusieurs heures : le serveur MCP doit
donc rendre la main immédiatement et laisser le LLM sonder l'avancement.

Modèle :
    start()  -> Job (identifiant court), le processus tourne en tâche de fond
    status() -> état, code retour, progression déduite du log
    log()    -> lignes filtrées (ERROR/WARNING) + statistiques
    cancel() -> SIGTERM sur le groupe de processus, puis SIGKILL après un délai

Aucun shell n'est utilisé : argv est une liste, exécutée directement.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

# Lignes qui comptent pour un agent : erreurs bloquantes et avertissements.
ERROR_PATTERNS = (
    re.compile(r"^\s*ERROR:", re.I),
    re.compile(r"\bERROR\b.*\[.*\d+-\d+\]"),          # message Vivado numéroté
    re.compile(r"CRITICAL WARNING:", re.I),
    re.compile(r"^\s*Traceback \(most recent call last\)"),
    re.compile(r"\bAssertionError\b"),
    # "FAIL"/"FAILED" en échec, mais PAS le résumé cocotb "TESTS=3 PASS=3 FAIL=0"
    re.compile(r"\b(?:FAILED|FAIL(?!\s*=\s*\d))\b"),
    re.compile(r"cannot find entity", re.I),
    re.compile(r"^\s*make(\[\d+\])?: \*\*\*"),
)
WARNING_PATTERNS = (
    re.compile(r"^\s*WARNING:", re.I),
    re.compile(r"^\s*\[.*\d+-\d+\]\s*WARNING", re.I),
    re.compile(r"\bWarning\b.*\bW\d+\b"),
)

_TERMINAL = ("ok", "failed", "timeout", "cancelled", "error")


@dataclass
class Job:
    """État d'un job EDA, partagé entre le thread lecteur et les outils MCP."""

    id: str
    kind: str
    argv: list[str]
    cwd: str
    log_path: Path
    started_at: float
    timeout_s: int
    status: str = "running"
    returncode: int | None = None
    finished_at: float | None = None
    pid: int | None = None
    progress: str | None = None
    error: str | None = None
    tail: deque[str] = field(default_factory=lambda: deque(maxlen=400))
    lines: int = 0
    bytes_written: int = 0
    _proc: subprocess.Popen | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # -- lecture d'état -------------------------------------------------------
    @property
    def duration_s(self) -> float:
        return (self.finished_at or time.time()) - self.started_at

    def summary(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "returncode": self.returncode,
            "duration_s": round(self.duration_s, 1),
            "log": str(self.log_path),
            "progress": self.progress,
            "error": self.error,
            "command": " ".join(self.argv),
            "cwd": self.cwd,
        }

    # -- helpers ---------------------------------------------------------------
    def matches(self, pattern: str | None) -> list[str]:
        rx = re.compile(pattern, re.I) if pattern else None
        out: list[str] = []
        with self._lock:
            for line in list(self.tail):
                if rx is None or rx.search(line):
                    out.append(line.rstrip("\n"))
        return out

    def scan(self) -> dict:
        """Compte erreurs et avertissements dans les dernières lignes."""
        errors: list[str] = []
        warnings: list[str] = []
        with self._lock:
            lines = list(self.tail)
        for line in lines:
            if any(p.search(line) for p in ERROR_PATTERNS):
                errors.append(line.rstrip())
            elif any(p.search(line) for p in WARNING_PATTERNS):
                warnings.append(line.rstrip())
        return {
            "errors": errors[-40:],
            "error_count": len(errors),
            "warnings": warnings[-20:],
            "warning_count": len(warnings),
            "tail": lines[-30:],
        }


class JobManager:
    """Lance et suit les processus EDA. Un seul objet par serveur MCP."""

    def __init__(self, runs_dir: Path, max_log_bytes: int = 50_000_000,
                 kill_grace_s: float = 8.0) -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.max_log_bytes = max_log_bytes
        self.kill_grace_s = kill_grace_s
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # -- lancement -------------------------------------------------------------
    def start(self, kind: str, argv: list[str], cwd: Path, env: dict[str, str],
              timeout_s: int, log_name: str | None = None) -> Job:
        job_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}-{uuid.uuid4().hex[:6]}"
        log_path = self.runs_dir / (log_name or f"{job_id}.log")

        job = Job(id=job_id, kind=kind, argv=list(argv), cwd=str(cwd),
                  log_path=log_path, started_at=time.time(), timeout_s=timeout_s)

        try:
            proc = subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                errors="replace",
                # nouveau groupe : permet de tuer toute la descendance d'un job
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            job.status = "error"
            job.error = f"binaire introuvable : {exc}"
            job.finished_at = time.time()
            with self._lock:
                self._jobs[job_id] = job
            return job

        job._proc = proc
        job.pid = proc.pid
        with self._lock:
            self._jobs[job_id] = job

        threading.Thread(target=self._reader, args=(job,), daemon=True,
                         name=f"reader-{job_id}").start()
        threading.Thread(target=self._watchdog, args=(job,), daemon=True,
                         name=f"watchdog-{job_id}").start()
        return job

    # -- threads internes ------------------------------------------------------
    def _reader(self, job: Job) -> None:
        assert job._proc is not None and job._proc.stdout is not None
        fh = open(job.log_path, "w", encoding="utf-8", errors="replace")
        try:
            for line in job._proc.stdout:
                job.lines += 1
                with job._lock:
                    job.tail.append(line)
                    m = re.search(r"\[(\d+)%\]|(\d+) %|Finished (\w+)", line)
                    if m:
                        job.progress = m.group(0).strip()
                if job.bytes_written < self.max_log_bytes:
                    fh.write(line)
                    job.bytes_written += len(line)
                elif job.bytes_written < self.max_log_bytes + 1:
                    fh.write("... [tronque : limite de taille de log atteinte]\n")
                    job.bytes_written += 1
        finally:
            fh.close()
            rc = job._proc.wait()
            with job._lock:
                job.returncode = rc
                if job.status == "running":
                    job.status = "ok" if rc == 0 else "failed"
                job.finished_at = time.time()
            self._persist(job)

    def _watchdog(self, job: Job) -> None:
        deadline = job.started_at + job.timeout_s
        while time.time() < deadline:
            if job.status in _TERMINAL:
                return
            time.sleep(0.5)
        if job.status == "running":
            job.error = f"delai de {job.timeout_s} s depasse : processus tue"
            job.status = "timeout"
            self._kill(job)

    def _kill(self, job: Job) -> None:
        proc = job._proc
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=self.kill_grace_s)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=self.kill_grace_s)
            except subprocess.TimeoutExpired:
                job.error = (job.error or "") + " | le processus resiste au SIGKILL"

    # -- persistance -----------------------------------------------------------
    def _persist(self, job: Job) -> None:
        try:
            meta = self.runs_dir / f"{job.id}.json"
            meta.write_text(json.dumps(job.summary(), indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    def prune(self, keep: int = 50) -> list[str]:
        """Supprime les logs des jobs les plus anciens (hors jobs en cours)."""
        done = [j for j in self._jobs.values() if j.status in _TERMINAL]
        done.sort(key=lambda j: j.started_at)
        removed: list[str] = []
        for job in done[:-keep] if keep >= 0 else done:
            for path in (job.log_path, self.runs_dir / f"{job.id}.json"):
                try:
                    path.unlink()
                    removed.append(str(path))
                except OSError:
                    pass
            self._jobs.pop(job.id, None)
        return removed

    # -- API -------------------------------------------------------------------
    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            known = ", ".join(sorted(self._jobs)[-10:]) or "aucun"
            raise KeyError(f"job inconnu : {job_id} (jobs connus : {known})")
        return job

    def list_jobs(self, limit: int = 20) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)
        return [j.summary() for j in jobs[:limit]]

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        if job.status in _TERMINAL:
            return {"id": job_id, "status": job.status, "note": "deja termine"}
        job.status = "cancelled"
        self._kill(job)
        return {"id": job_id, "status": job.status, "duration_s": round(job.duration_s, 1)}

    def wait(self, job_id: str, max_wait_s: float = 30.0) -> dict:
        """Attend (borné) la fin d'un job — utile pour les jobs courts."""
        job = self.get(job_id)
        deadline = time.time() + max_wait_s
        while time.time() < deadline and job.status not in _TERMINAL:
            time.sleep(0.25)
        return job.summary()
