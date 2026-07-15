"""Maintenance action registry — typed models for the 25 ``library-*`` CLI commands.

Each :class:`MaintenanceAction` entry models a single Typer-registered
``library-*`` command with its risk classification, dry-run capability,
long-running flag, and curated targeting options for the S3 web UI.

Category mapping (from module to registry category):

* ``query.py`` (status/search/show) → ``"query"``
* ``scan.py`` (index/init-canonical/scan/backfill-ids) → ``"scan"``
* ``maintenance.py`` (verify/repair) → ``"repair"``
* ``maintenance.py`` (clean/validate) → ``"clean"``
* ``analyze.py`` (analyze/recommend/rescrape/report) → ``"analyze"``
* ``audit.py`` (reconcile/ghost-audit/relink) → ``"fix"`` (reconcile and relink
  are mutating repairs; ghost-audit is ro diagnostics mapped to ``"query"``)
* ``doctor.py`` → ``"query"`` (read-only health diagnostics)
* ``gc.py`` → ``"fix"`` (mutating cleanup of ``index_outbox``)
* ``fix_canonical_provider.py`` → ``"fix"``
* ``fix_nfo.py`` → ``"fix"``
* ``fix_orphan_files.py`` → ``"fix"``
* ``fix_season_counts.py`` → ``"fix"``
* ``dedup_titles.py`` → ``"fix"``
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel


class ActionOption(BaseModel):
    """A single targeting option for a maintenance action.

    Models one CLI flag or positional argument. The ``type`` field drives
    the form control rendered in the web UI (text input, number input,
    checkbox, or dropdown). Enum values are the valid choices for a
    ``select`` / dropdown control.

    Attributes:
        name: CLI-facing name (flag name without leading dashes, or
            positional arg name). Used as the JSON key in ``options_json``.
        type: Form-control type — ``"str"`` for text, ``"int"`` for number,
            ``"bool"`` for checkbox, ``"enum"`` for dropdown.
        enum_values: Valid choices when ``type="enum"``. ``None`` otherwise.
        default: Default value matching the CLI default. ``None`` when the
            CLI has no default (optional flags) or when the value is a
            required positional.
        required: ``True`` for mandatory positional arguments (e.g.
            ``library-search``'s ``query``). ``False`` for optional flags.
        label: French label for the web UI form field.
        help: French help text / placeholder for the web UI form field.
    """

    name: str
    type: Literal["str", "int", "bool", "enum"]
    enum_values: list[str] | None = None
    default: str | int | bool | None = None
    required: bool = False
    label: str
    help: str


class MaintenanceAction(BaseModel):
    """A single maintenance action backed by a ``library-*`` CLI command.

    Each entry in :data:`REGISTRY` maps 1:1 to a Typer-registered
    ``library-*`` command. The web UI reads the registry to render the
    action panels and the ``POST /api/maintenance/run`` endpoint uses it
    to validate incoming requests and build the subprocess invocation.

    Attributes:
        id: Kebab-case CLI command name (e.g. ``"library-index"``).
        title: Short French label for the web UI action card / button.
        description: One-line French description of what the command does.
        category: UI grouping — ``"query"`` (read-only info), ``"scan"``
            (indexer scans), ``"repair"`` (repair-queue based fixes),
            ``"clean"`` (filesystem cleanup), ``"analyze"`` (insights),
            ``"fix"`` (targeted DB/filesystem repairs).
        risk: Write-impact classification — ``"ro"`` (read-only, safe to
            run anytime), ``"write"`` (mutates DB or filesystem but is
            reversible / non-destructive), ``"destructive"`` (deletes files,
            drops rows, or truncates data — needs confirmation UI).
        long_running: ``True`` when the command walks disks, makes network
            calls, or processes the full library. The web UI uses this to
            route execution through the S2 subprocess + lock path and show
            a progress indicator.
        dry_run: ``"supported"`` when the CLI exposes ``--dry-run`` or an
            ``--apply`` flag whose absence means dry-run. ``"unsupported"``
            otherwise. The web UI sends ``dry_run`` separately; this field
            tells it whether to show the toggle.
        options: Curated list of high-value targeting flags/arguments.
            Plumbing flags (``--config``, ``--db``, ``--wait-for-lock``,
            ``--confirm-bulk-change``, ``--list-checks``, ``--export``,
            ``--backfill-streams``, ``--rebuild``, ``--no-enqueue``,
            ``--interactive``, ``--read-only``, ``--enqueue-repairs``,
            ``--clean-fk-orphans``, ``--purge-unrecoverable``,
            ``--purge-release-orphans``, ``--from-index``, ``--fix``) are
            excluded — the web layer handles them separately or they are
            irrelevant outside a terminal.
    """

    id: str
    title: str
    description: str
    category: Literal["query", "scan", "repair", "clean", "analyze", "fix"]
    risk: Literal["ro", "write", "destructive"]
    long_running: bool
    dry_run: Literal["unsupported", "supported"]
    options: list[ActionOption]


def canonical_options_json(options: dict[str, object]) -> str:
    """Serialize validated options to canonical JSON (sorted keys, no spaces).

    The canonical form is what ``POST /api/maintenance/run`` stores in the
    ``options_json`` column of ``pipeline_run`` and what the 428
    precondition compares by string equality.

    Args:
        options: A dictionary of validated key-value pairs representing
            CLI flags/arguments for a maintenance action.

    Returns:
        A canonical JSON string with keys sorted alphabetically and no
        whitespace between tokens, suitable for deterministic string
        comparison.
    """
    return json.dumps(options, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Registry — 25 library-* commands registered on the Typer app.
# Ground truth: @app.command decorators in personalscraper/commands/library/*.py
# (NOT __all__, which is stale at 23 entries).
# ---------------------------------------------------------------------------

REGISTRY: list[MaintenanceAction] = [
    # ── query.py (3 commands) ─────────────────────────────────────────────
    MaintenanceAction(
        id="library-status",
        title="État de la bibliothèque",
        description="Affiche le résumé du dernier scan d'indexation terminé.",
        category="query",
        risk="ro",
        long_running=False,
        dry_run="unsupported",
        options=[],
    ),
    MaintenanceAction(
        id="library-search",
        title="Recherche dans la bibliothèque",
        description="Recherche des médias indexés avec le langage de requête flex-attr.",
        category="query",
        risk="ro",
        long_running=False,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="query",
                type="str",
                required=True,
                label="Requête",
                help="Chaîne de recherche, ex. 'year:2024 disk:Disk1 -nfo:valid'",
            ),
            ActionOption(
                name="limit",
                type="int",
                default=50,
                label="Limite",
                help="Nombre maximum de résultats à retourner.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-show",
        title="Détail d'un élément",
        description="Affiche toutes les données stockées pour un média (ID DB).",
        category="query",
        risk="ro",
        long_running=False,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="item_id",
                type="int",
                required=True,
                label="ID de l'élément",
                help="Identifiant media_item dans la base indexer.",
            ),
        ],
    ),
    # ── scan.py (4 commands) ──────────────────────────────────────────────
    MaintenanceAction(
        id="library-index",
        title="Indexer la bibliothèque",
        description="Lance un scan complet ou rapide des disques et met à jour l'index.",
        category="scan",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="mode",
                type="enum",
                enum_values=["full", "quick", "incremental", "enrich"],
                default="full",
                label="Mode de scan",
                help=(
                    "Stratégie de scan : full (complet), quick (Merkle rapide), "
                    "incremental (fichiers modifiés), enrich (ffprobe seulement)."
                ),
            ),
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Restreindre le scan à ce disque (label configuré).",
            ),
            ActionOption(
                name="budget",
                type="int",
                label="Budget (secondes)",
                help="Limite de temps en secondes pour le scan.",
            ),
            ActionOption(
                name="no-budget",
                type="bool",
                default=False,
                label="Sans budget",
                help="Désactiver la limite de temps (annule --budget et la config).",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-init-canonical",
        title="Initialiser le provider canonique",
        description="Peuple canonical_provider et external_ids_json depuis les fichiers NFO.",
        category="scan",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[],
    ),
    MaintenanceAction(
        id="library-scan",
        title="Scan complet (alias)",
        description="Alias visible de library-index --mode full. Parcourt tous les disques.",
        category="scan",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Restreindre le scan à ce disque (label configuré).",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-backfill-ids",
        title="Backfill des IDs croisés",
        description="Remplit les IDs cross-provider et les ratings manquants via TMDB/TVDB/OMDb.",
        category="scan",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="show",
                type="str",
                label="Série",
                help="Restreindre le backfill à une seule série (titre exact).",
            ),
            ActionOption(
                name="ids-only",
                type="bool",
                default=False,
                label="IDs seulement",
                help="Backfill uniquement les IDs provider, pas les ratings.",
            ),
            ActionOption(
                name="ratings-only",
                type="bool",
                default=False,
                label="Ratings seulement",
                help="Backfill uniquement les ratings, pas les IDs provider.",
            ),
        ],
    ),
    # ── maintenance.py (4 commands) ───────────────────────────────────────
    MaintenanceAction(
        id="library-verify",
        title="Vérifier les fichiers",
        description="Re-stat chaque fichier indexé et signale les divergences dans la repair_queue.",
        category="repair",
        risk="write",
        long_running=True,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Restreindre la vérification à ce disque.",
            ),
            ActionOption(
                name="budget",
                type="int",
                label="Budget (secondes)",
                help="Limite de temps en secondes ; peut reprendre au prochain lancement.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-repair",
        title="Réparer (repair queue)",
        description="Vide la repair_queue dans la limite du budget temps. FIFO, reprenable.",
        category="repair",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="budget",
                type="int",
                default=60,
                label="Budget (secondes)",
                help="Temps maximum alloué à la réparation (défaut : 60s).",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-clean",
        title="Nettoyer les disques",
        description="Supprime les répertoires .actors/, dossiers vides et fichiers junk des disques.",
        category="clean",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="only",
                type="enum",
                enum_values=["actors", "empty", "junk", "release", "orphans"],
                label="Type de nettoyage",
                help="Cibler un type spécifique : actors, empty, junk, release, orphans.",
            ),
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Nettoyer uniquement ce disque.",
            ),
            ActionOption(
                name="category",
                type="str",
                label="Catégorie",
                help="Nettoyer uniquement cette catégorie de média.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-validate",
        title="Valider la bibliothèque",
        description="Vérifie la conformité des NFO, artworks et nommages des éléments.",
        category="clean",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Valider uniquement ce disque.",
            ),
            ActionOption(
                name="category",
                type="str",
                label="Catégorie",
                help="Valider uniquement cette catégorie.",
            ),
            ActionOption(
                name="check",
                type="str",
                label="Vérifications",
                help="Lister les vérifications à exécuter (répétable). Vide = toutes.",
            ),
        ],
    ),
    # ── audit.py (3 commands) ─────────────────────────────────────────────
    MaintenanceAction(
        id="library-reconcile",
        title="Réconcilier index ↔ disques",
        description="Détecte les divergences entre l'index et les fichiers sans rescan complet.",
        category="fix",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="scope",
                type="enum",
                enum_values=[
                    "merkle",
                    "dispatch_path",
                    "enrich",
                    "release",
                    "season",
                    "item",
                    "path_missing",
                ],
                label="Portée",
                help="Détecteurs à exécuter (répétable). Vide = tous.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-ghost-audit",
        title="Audit des fichiers fantômes",
        description="Détecte les entrées fantômes NTFS-via-macFUSE sur les disques.",
        category="query",
        risk="ro",
        long_running=True,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Auditer uniquement ce disque.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-relink",
        title="Relier les fichiers orphelins",
        description="Relie les media_file sans release_id à leur media_release.",
        category="fix",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[],
    ),
    MaintenanceAction(
        id="library-refresh-path",
        title="Rafraîchir un dossier renommé",
        description=(
            "Réconciliation d'index ciblée après un rename/move manuel : invalide le "
            "sous-arbre, rescanne le disque propriétaire, relie et répare les compteurs."
        ),
        category="fix",
        risk="write",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="path",
                type="str",
                required=True,
                label="Chemin absolu",
                help="Chemin absolu du dossier média renommé/déplacé.",
            ),
        ],
    ),
    # ── analyze.py (4 commands) ───────────────────────────────────────────
    MaintenanceAction(
        id="library-analyze",
        title="Analyser la bibliothèque",
        description="Résumé des codecs, audio et sous-titres depuis les streams enrichis.",
        category="analyze",
        risk="ro",
        long_running=True,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Analyser uniquement ce disque.",
            ),
            ActionOption(
                name="category",
                type="str",
                label="Catégorie",
                help="Analyser uniquement cette catégorie.",
            ),
            ActionOption(
                name="max-items",
                type="int",
                label="Nb max d'éléments",
                help="Limiter le nombre d'éléments analysés.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-recommend",
        title="Recommandations",
        description="Génère des recommandations de re-téléchargement (codec, taille, priorité).",
        category="analyze",
        risk="ro",
        long_running=True,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="sort",
                type="enum",
                enum_values=["priority", "size", "codec"],
                default="priority",
                label="Tri",
                help="Critère de tri : priority, size, codec.",
            ),
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Filtrer sur ce disque.",
            ),
            ActionOption(
                name="category",
                type="str",
                label="Catégorie",
                help="Filtrer sur cette catégorie.",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-rescrape",
        title="Re-scraper des éléments",
        description="Re-scrape ciblé des éléments via TMDB/TVDB (NFO, artwork, épisodes).",
        category="analyze",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[
            ActionOption(
                name="only",
                type="enum",
                enum_values=["nfo", "artwork", "episodes"],
                label="Cible",
                help="Ne réparer que : nfo, artwork, episodes.",
            ),
            ActionOption(
                name="disk",
                type="str",
                label="Disque",
                help="Re-scraper uniquement ce disque.",
            ),
            ActionOption(
                name="category",
                type="str",
                label="Catégorie",
                help="Re-scraper uniquement cette catégorie.",
            ),
            ActionOption(
                name="max-items",
                type="int",
                label="Nb max d'éléments",
                help="Limiter le nombre d'éléments à traiter.",
            ),
            ActionOption(
                name="item-id",
                type="int",
                label="ID de l'élément",
                help="Re-scraper exactement cet élément par ID DB (ignore le prédicat needs-rescrape).",
            ),
        ],
    ),
    MaintenanceAction(
        id="library-report",
        title="Rapport de bibliothèque",
        description="Affiche les statistiques et l'état de santé global de la bibliothèque.",
        category="analyze",
        risk="ro",
        long_running=True,
        dry_run="unsupported",
        options=[],
    ),
    # ── doctor.py (1 command) ─────────────────────────────────────────────
    MaintenanceAction(
        id="library-doctor",
        title="Diagnostic de la base",
        description="Exécute une suite de vérifications sur la base indexer (intégrité, FK, dérive…).",
        category="query",
        risk="ro",
        long_running=False,
        dry_run="unsupported",
        options=[
            ActionOption(
                name="repair-queue-threshold",
                type="int",
                default=100,
                label="Seuil repair_queue",
                help="Nb max de lignes pending dans repair_queue avant avertissement.",
            ),
            ActionOption(
                name="outbox-lag-threshold-s",
                type="int",
                default=3600,
                label="Seuil lag outbox (s)",
                help="Âge max en secondes de la plus vieille ligne pending dans index_outbox.",
            ),
            ActionOption(
                name="canonical-threshold-pct",
                type="int",
                default=50,
                label="Seuil canonical_provider (%)",
                help="Pourcentage minimum d'éléments devant avoir canonical_provider.",
            ),
            ActionOption(
                name="stuck-scan-threshold-s",
                type="int",
                default=3600,
                label="Seuil scan bloqué (s)",
                help="Délai en secondes après lequel un scan_run 'running' est considéré bloqué.",
            ),
        ],
    ),
    # ── gc.py (1 command) ─────────────────────────────────────────────────
    MaintenanceAction(
        id="library-gc",
        title="Nettoyage de l'outbox",
        description="Supprime les vieilles lignes index_outbox (status=done) pour éviter la croissance infinie.",
        category="fix",
        risk="write",
        long_running=False,
        dry_run="supported",
        options=[
            ActionOption(
                name="older-than-days",
                type="int",
                default=30,
                label="Ancienneté (jours)",
                help="Supprimer les lignes traitées il y a plus de N jours (défaut : 30).",
            ),
        ],
    ),
    # ── fix_canonical_provider.py (1 command) ─────────────────────────────
    MaintenanceAction(
        id="library-fix-canonical-provider",
        title="Corriger canonical_provider",
        description="Répare les valeurs incorrectes de canonical_provider (shows→tvdb, movies→tmdb).",
        category="fix",
        risk="write",
        long_running=False,
        dry_run="supported",
        options=[],
    ),
    # ── fix_nfo.py (1 command) ────────────────────────────────────────────
    MaintenanceAction(
        id="library-fix-nfo",
        title="Réparer les NFO malformés",
        description="Tronque le contenu hors-racine XML dans les fichiers NFO (liens TVDB parasites).",
        category="fix",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[],
    ),
    # ── fix_orphan_files.py (1 command) ───────────────────────────────────
    MaintenanceAction(
        id="library-fix-orphan-files",
        title="Réparer les fichiers orphelins",
        description="Relie les media_file sans release_id à leur media_release (2 niveaux : item + épisode).",
        category="fix",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[],
    ),
    # ── fix_season_counts.py (1 command) ──────────────────────────────────
    MaintenanceAction(
        id="library-fix-season-counts",
        title="Corriger le compte d'épisodes",
        description="Recalcule season.episode_count pour les saisons dont le cache a dérivé.",
        category="fix",
        risk="write",
        long_running=False,
        dry_run="supported",
        options=[],
    ),
    # ── dedup_titles.py (1 command) ───────────────────────────────────────
    MaintenanceAction(
        id="library-dedup-titles",
        title="Dédupliquer les titres",
        description="Fusionne les media_item dont le titre ne diffère que par la normalisation NFD/NFC.",
        category="fix",
        risk="destructive",
        long_running=True,
        dry_run="supported",
        options=[],
    ),
]
