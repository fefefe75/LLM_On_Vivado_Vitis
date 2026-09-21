"""Barrières de sécurité du serveur MCP.

Un serveur MCP est piloté par un LLM : on considère donc son entrée comme non
fiable. Trois règles, appliquées partout :

1. Aucune écriture hors de la racine du projet (`workspace`).
2. Aucun binaire hors liste blanche, et JAMAIS de shell=True.
3. Toute saisie Tcl/texte écrite par le LLM est déposée dans un fichier
   temporaire du projet, jamais interpolée dans une ligne de commande.

PORTÉE EXACTE, à ne pas surestimer : ces règles confinent les OUTILS DE FICHIERS et
la liste des binaires. Elles ne rendent pas le serveur étanche : le Tcl soumis à
`vivado_run`/`vitis_run` est un langage complet (`exec` inclus), et `cocotb_run`
exécute le `make` du dossier de testbench — donc le Makefile que l'agent vient
d'écrire. Voir « What this does NOT protect against » dans `mcp/README.md`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Motifs interdits dans un chemin relatif fourni par le LLM.
_FORBIDDEN = ("..",)


class PathRefused(PermissionError):
    """Levé quand un accès sortirait de l'espace autorisé."""


def _reject_weird(raw: str) -> None:
    if "\x00" in raw:
        raise PathRefused("chemin contenant un octet nul")
    if raw.startswith("~"):
        raise PathRefused("les chemins '~' ne sont pas acceptés : utiliser un chemin relatif au projet")


def resolve_in_workspace(workspace: Path, candidate: str | Path, *, must_exist: bool = False) -> Path:
    """Résout `candidate` dans `workspace` et refuse toute évasion.

    Chemins absolus : acceptés seulement s'ils sont déjà sous `workspace`.
    Chemins relatifs : résolus depuis `workspace`, `..` interdit.
    """
    raw = str(candidate)
    _reject_weird(raw)

    p = Path(raw)
    if p.is_absolute():
        resolved = p.expanduser().resolve()
    else:
        if any(part in _FORBIDDEN for part in p.parts):
            raise PathRefused(f"chemin relatif contenant '..' : {raw}")
        resolved = (workspace / p).resolve()

    # compare en chemins réels (resolve() a déjà suivi les liens symboliques)
    ws = workspace.resolve()
    if resolved != ws and ws not in resolved.parents:
        raise PathRefused(f"chemin hors du projet autorisé ({ws}) : {resolved}")

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"introuvable : {resolved} (racine autorisée : {ws})")
    return resolved


def check_binary(name: str, allowlist: tuple[str, ...]) -> None:
    """Refuse un binaire hors liste blanche ou un nom contenant un séparateur."""
    if not name or os.sep in name or "/" in name:
        raise PermissionError(f"nom de binaire invalide : {name!r}")
    if name not in allowlist:
        raise PermissionError(
            f"binaire {name!r} refusé ; autorisés : {', '.join(sorted(allowlist))}"
        )


def write_tcl(workspace: Path, name: str, tcl_source: str) -> Path:
    """Écrit un script Tcl fourni par le LLM dans le projet, avec un nom sûr.

    Renvoie le chemin du script. Le nom est nettoyé : la fonction refuse toute
    composante de chemin et n'accepte qu'un identifiant simple.
    """
    safe = "".join(c for c in Path(name).name if c.isalnum() or c in "._-")
    if not safe or not safe.endswith(".tcl"):
        if not safe:
            safe = "llm_script.tcl"
        elif not safe.endswith(".tcl"):
            safe += ".tcl"
    scripts_dir = workspace / "scripts" / "generated"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    target = scripts_dir / safe
    # écriture atomique : un job ne doit jamais lire un fichier à moitié écrit
    fd, tmp = tempfile.mkstemp(dir=scripts_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tcl_source)
            if not tcl_source.endswith("\n"):
                fh.write("\n")
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target
