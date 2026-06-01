"""Library reporter — aggregate statistics from the indexer DB and command outputs.

Reads health metrics from :class:`~personalscraper.insights.models.AnalysisResult`
(produced by :func:`~personalscraper.insights.analytics.analyze`) and supplementary
command outputs (validation, recommendations, rescrape) to produce a comprehensive
library health report with clear explanations and suggested remediation commands.

The DB-backed :class:`AnalysisResult` is the source of totals, NFO / artwork
metrics, disk distribution, and per-item size data. Scan-issue data
(``actors_dir_present``, ``junk_files``, etc.) and ``actors_dir_count`` are
persisted in the indexer's ``item_issue`` table and surfaced here via
``AnalysisResult.scan_issues`` / ``actors_dir_count`` so the report can flag
dirty directories without re-walking the disks. ``library-clean`` remains the
user-driven action that resolves them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.dispatch.disk_scanner import DiskStatus
    from personalscraper.insights.models import AnalysisResult

# Human-readable explanations for scan issues
_ISSUE_EXPLANATIONS: dict[str, str] = {
    "actors_dir_present": "Dossiers .actors/ (images d'acteurs créées par MediaElch, inutilisées par Plex)",
    "junk_files": "Fichiers parasites (.DS_Store, Thumbs.db, ._* resource forks macOS)",
    "bad_dir_naming": "Nom de dossier sans (Année) — format attendu: Titre (2024)",
    "release_group_artifact": "Dossiers vides laissés par des releases torrent",
    "empty_subdir": "Sous-dossiers vides (saisons supprimées ou incomplètes)",
    "ntfs_unsafe_name": 'Noms contenant des caractères interdits sur NTFS (<>:"/\\|?*)',
}

# Human-readable explanations for validation errors
_VALIDATION_EXPLANATIONS: dict[str, str] = {
    "episode_renamed": "Épisodes pas au format S01E01 - Titre.mkv (noms originaux du torrent)",
    "category": "NFO sans genre → impossible de vérifier la bonne catégorie",
    "nfo_valid": "NFO présent mais XML cassé (souvent & non-échappé par MediaElch)",
    "poster_present": "Pas d'image poster",
    "nfo_present": "Pas de fichier .nfo du tout",
    "dir_naming": "Nom de dossier sans (Année)",
    "video_present": "Pas de fichier vidéo (audiobooks ou dossiers vides)",
    "no_empty_dirs": "Sous-dossiers vides à l'intérieur",
    "nfo_ids": "NFO sans identifiant TMDB ni IMDB",
    "season_structure": "Pas de dossier Saison XX/ dans une série",
    "season_posters": "Poster de saison manquant",
    "artwork_landscape": "Image landscape/thumb manquante",
    "not_sample": "Fichier vidéo très petit (possible sample)",
    "episode_nfo": "NFO d'épisode manquant",
    "ntfs_safe_names": "Noms de fichiers non compatibles NTFS",
}

# Suggested fix commands per issue type
_ISSUE_FIXES: dict[str, str] = {
    "actors_dir_present": "personalscraper library-clean --only actors --apply",
    "junk_files": "personalscraper library-clean --only junk --apply",
    "release_group_artifact": "personalscraper library-clean --only release --apply",
    "empty_subdir": "personalscraper library-clean --only empty --apply",
}

_VALIDATION_FIXES: dict[str, str] = {
    "nfo_present": "personalscraper library-rescrape --only nfo",
    "nfo_valid": "personalscraper library-rescrape --only nfo",
    "poster_present": "personalscraper library-rescrape --only artwork",
    "no_empty_dirs": "personalscraper library-clean --only empty --apply",
    "dir_naming": "personalscraper library-validate --fix --apply",
    "episode_renamed": "personalscraper library-rescrape --only episodes",
    "nfo_ids": "personalscraper library-rescrape --only nfo",
}


@dataclass
class LibraryReport:
    """Aggregated library health report.

    Attributes:
        generated_at: ISO 8601 timestamp.
        total_items: Total media items across all disks.
        total_size_gb: Total library size in GB.
        items_per_disk: Item count per disk.
        items_per_category: Item count per category.
        size_per_disk_gb: Total size per disk in GB.
        actors_dir_count: Number of items with .actors/ directories.
        nfo_valid_count: Items with valid NFOs.
        nfo_invalid_count: Items with missing or invalid NFOs.
        poster_missing_count: Items without poster artwork.
        scan_issues: Issue type -> count from scan data.
        validation_errors: Error type -> count from validation data.
        validation_warnings: Warning type -> count from validation data.
        codec_distribution: File count per video codec.
        audio_distribution: File count per audio profile.
        analysis_item_count: Number of items analyzed by ffprobe.
        analysis_file_count: Number of files analyzed by ffprobe.
        top_largest: Top 20 largest items (path, size_gb).
        recommendation_count: Total recommendations.
        estimated_savings_gb: Estimated savings from all recommendations.
        recommendations_by_priority: Recommendation count per priority.
        recommendation_details: Top recommendations (title, priority, reasons).
        validation_valid: Items passing validation.
        validation_fixable: Items that can be auto-fixed.
        validation_issues: Items failing validation.
        disk_free_gb: Free space per disk in GB.
        cleanable_count: Items that library-clean would remove.
        cleanable_bytes: Bytes that library-clean would free.
    """

    generated_at: str = ""
    total_items: int = 0
    total_size_gb: float = 0.0
    items_per_disk: dict[str, int] = field(default_factory=dict)
    items_per_category: dict[str, int] = field(default_factory=dict)
    size_per_disk_gb: dict[str, float] = field(default_factory=dict)
    actors_dir_count: int = 0
    nfo_valid_count: int = 0
    nfo_invalid_count: int = 0
    poster_missing_count: int = 0
    scan_issues: dict[str, int] = field(default_factory=dict)
    validation_errors: dict[str, int] = field(default_factory=dict)
    validation_warnings: dict[str, int] = field(default_factory=dict)
    codec_distribution: dict[str, int] = field(default_factory=dict)
    audio_distribution: dict[str, int] = field(default_factory=dict)
    analysis_item_count: int = 0
    analysis_file_count: int = 0
    top_largest: list[tuple[str, float]] = field(default_factory=list)
    recommendation_count: int = 0
    estimated_savings_gb: float = 0.0
    recommendations_by_priority: dict[str, int] = field(default_factory=dict)
    recommendation_details: list[dict[str, Any]] = field(default_factory=list)
    validation_valid: int = 0
    validation_fixable: int = 0
    validation_issues: int = 0
    disk_free_gb: dict[str, float] = field(default_factory=dict)
    cleanable_count: int = 0
    cleanable_bytes: int = 0
    rescrape_fixed: int = 0
    rescrape_skipped: int = 0
    rescrape_errors: int = 0
    rescrape_nfo_count: int = 0
    rescrape_artwork_count: int = 0
    rescrape_episodes_count: int = 0


def generate_report(
    analysis_result: AnalysisResult | None = None,
    validation_data: dict[str, Any] | None = None,
    recommendation_data: dict[str, Any] | None = None,
    disk_statuses: list[DiskStatus] | None = None,
    rescrape_data: dict[str, Any] | None = None,
) -> LibraryReport:
    """Generate a library health report from the indexer DB analysis and JSON data.

    Each parameter is optional — report includes whatever data is available.
    ``analysis_result`` is produced by :func:`~personalscraper.insights.analytics.analyze`
    and is the single source of truth for totals, NFO / artwork status, disk
    distribution, and per-item sizes.  Supplementary JSON files (validation,
    recommendations, rescrape) are individual command outputs that this report
    aggregates when present.

    Args:
        analysis_result: DB-backed library summary from ``analytics.analyze(conn)``.
            Supplies totals, disk / category distribution, top-largest items,
            NFO status counts, artwork presence, and season poster gaps.
        validation_data: Parsed library_validation.json (output of library-validate).
        recommendation_data: Parsed library_recommendations.json (output of library-recommend).
        disk_statuses: List of DiskStatus objects for live free space.
        rescrape_data: Parsed library_rescrape.json (output of library-rescrape).

    Returns:
        LibraryReport with aggregated statistics.
    """
    report = LibraryReport(generated_at=datetime.now(tz=timezone.utc).isoformat())

    # --- DB-backed analysis result: totals, distribution, NFO/artwork metrics
    if analysis_result is not None:
        report.total_items = analysis_result.total_items
        report.total_size_gb = analysis_result.total_size_gb
        report.items_per_disk = dict(analysis_result.items_per_disk)
        report.items_per_category = dict(analysis_result.items_per_category)
        report.size_per_disk_gb = dict(analysis_result.size_per_disk_gb)
        report.top_largest = list(analysis_result.top_largest)

        report.nfo_valid_count = analysis_result.nfo.valid
        report.nfo_invalid_count = analysis_result.nfo.invalid + analysis_result.nfo.missing
        report.poster_missing_count = analysis_result.artwork.poster_missing

        # Directory-hygiene issues are now persisted in ``item_issue`` and
        # surfaced via ``AnalysisResult.scan_issues`` / ``actors_dir_count``.
        # ``Counter.most_common()`` on a dict returns descending counts so
        # the SCAN section in ``format_report_text`` lists the heaviest
        # issue type first.
        if analysis_result.scan_issues:
            report.scan_issues = dict(Counter(analysis_result.scan_issues).most_common())
        report.actors_dir_count = analysis_result.actors_dir_count

    # --- Disk free space (from live DiskStatus objects) ---
    if disk_statuses:
        for ds in disk_statuses:
            if hasattr(ds, "config") and hasattr(ds, "free_space_gb"):
                report.disk_free_gb[ds.config.id] = round(ds.free_space_gb, 1)

    # --- Validation data ---
    if validation_data:
        report.validation_valid = validation_data.get("valid_count", 0)
        report.validation_fixable = validation_data.get("fixed_count", 0)
        report.validation_issues = validation_data.get("issues_count", 0)

        error_counter: Counter[str] = Counter()
        warning_counter: Counter[str] = Counter()
        for item in validation_data.get("items", []):
            for e in item.get("errors", []):
                error_counter[e] += 1
            for w in item.get("warnings", []):
                warning_counter[w] += 1
        report.validation_errors = dict(error_counter.most_common())
        report.validation_warnings = dict(warning_counter.most_common())

    # --- Recommendation data ---
    if recommendation_data:
        report.recommendation_count = recommendation_data.get("total_recommendations", 0)
        report.estimated_savings_gb = recommendation_data.get("estimated_total_savings_gb", 0.0)

        priority_counter: Counter[str] = Counter()
        details = []
        for rec in recommendation_data.get("items", []):
            priority_counter[rec.get("priority", "unknown")] += 1
            details.append(
                {
                    "title": rec.get("title", "?"),
                    "priority": rec.get("priority", "?"),
                    "codec": rec.get("current", {}).get("codec", "?"),
                    "resolution": rec.get("current", {}).get("resolution", "?"),
                    "size_gb": rec.get("current", {}).get("size_gb", 0),
                    "audio_profile": rec.get("current", {}).get("audio_profile", "?"),
                    "reasons": rec.get("reasons", []),
                    "savings_gb": rec.get("estimated_savings_gb", 0),
                }
            )
        report.recommendations_by_priority = dict(priority_counter)
        report.recommendation_details = details

    # --- Rescrape data ---
    if rescrape_data:
        report.rescrape_fixed = rescrape_data.get("fixed_count", 0)
        report.rescrape_skipped = rescrape_data.get("skipped_count", 0)
        report.rescrape_errors = rescrape_data.get("error_count", 0)

        for item in rescrape_data.get("items", []):
            for action in item.get("actions_taken", []):
                if action == "nfo_regenerated":
                    report.rescrape_nfo_count += 1
                elif action == "artwork_downloaded":
                    report.rescrape_artwork_count += 1
                elif action == "episodes_renamed":
                    report.rescrape_episodes_count += 1

    return report


def format_report_text(report: LibraryReport) -> str:
    """Format a LibraryReport as a detailed, clear human-readable report.

    Includes explanations for each metric, suggested remediation commands,
    and aggregated data from all library commands.

    Args:
        report: Report to format.

    Returns:
        Formatted multi-line string.
    """
    sep = "=" * 70
    sub = "-" * 50
    lines: list[str] = []

    lines.append(sep)
    lines.append("  RAPPORT DE SANTÉ DE LA MÉDIATHÈQUE")
    lines.append(f"  Généré le {report.generated_at}")
    lines.append(sep)
    lines.append("")

    # --- Overview ---
    lines.append(f"  Total: {report.total_items} items, {report.total_size_gb:.1f} GB")
    lines.append("")

    # --- Disks ---
    if report.items_per_disk:
        lines.append(f"  {sub}")
        lines.append("  DISQUES")
        lines.append(f"  {sub}")
        for disk in sorted(report.items_per_disk):
            count = report.items_per_disk[disk]
            size = report.size_per_disk_gb.get(disk, 0)
            free = report.disk_free_gb.get(disk)
            free_str = f", {free:.0f} GB libre" if free is not None else ""
            pct = (count * 100 // report.total_items) if report.total_items else 0
            lines.append(f"    {disk}: {count} items ({size:.0f} GB{free_str}) [{pct}%]")
        lines.append("")

    # --- Categories ---
    if report.items_per_category:
        lines.append(f"  {sub}")
        lines.append("  CATÉGORIES")
        lines.append(f"  {sub}")
        for cat, count in sorted(report.items_per_category.items(), key=lambda x: -x[1]):
            lines.append(f"    {cat}: {count}")
        lines.append("")

    # === SECTION 1: SCAN ===
    if report.scan_issues:
        lines.append(sep)
        lines.append("  1. SCAN — Problèmes détectés dans la bibliothèque")
        lines.append(sep)
        lines.append("")
        for issue, count in report.scan_issues.items():
            explanation = _ISSUE_EXPLANATIONS.get(issue, issue)
            pct_str = f" ({count * 100 // report.total_items}%)" if report.total_items else ""
            lines.append(f"    {issue}: {count}{pct_str}")
            lines.append(f"      → {explanation}")
            fix = _ISSUE_FIXES.get(issue)
            if fix:
                lines.append(f"      ✓ Corriger: {fix}")
            lines.append("")

        # Total cleanable summary
        cleanable = sum(report.scan_issues.get(k, 0) for k in _ISSUE_FIXES)
        if cleanable:
            lines.append(f"    Nettoyable automatiquement: {cleanable} problèmes")
            lines.append("    ✓ Tout nettoyer: personalscraper library-clean --apply")
            lines.append("")

    # === SECTION 2: VALIDATION ===
    if report.validation_valid or report.validation_issues:
        total_v = report.validation_valid + report.validation_issues
        pct_valid = (report.validation_valid * 100 // total_v) if total_v else 0
        lines.append(sep)
        lines.append("  2. VALIDATION — Conformité des métadonnées")
        lines.append(sep)
        lines.append("")
        lines.append(f"    Conformes: {report.validation_valid} ({pct_valid}%)")
        lines.append(f"    Non-conformes: {report.validation_issues} ({100 - pct_valid}%)")
        lines.append("")

        if report.validation_errors:
            lines.append(f"    {sub}")
            lines.append("    Erreurs (non-conformités)")
            lines.append(f"    {sub}")
            for err, count in report.validation_errors.items():
                explanation = _VALIDATION_EXPLANATIONS.get(err, err)
                lines.append(f"      {err}: {count}")
                lines.append(f"        → {explanation}")
                fix = _VALIDATION_FIXES.get(err)
                if fix:
                    lines.append(f"        ✓ {fix}")
                lines.append("")

        if report.validation_warnings:
            lines.append(f"    {sub}")
            lines.append("    Avertissements (qualité améliorable)")
            lines.append(f"    {sub}")
            for warn, count in report.validation_warnings.items():
                explanation = _VALIDATION_EXPLANATIONS.get(warn, warn)
                lines.append(f"      {warn}: {count}")
                lines.append(f"        → {explanation}")
            lines.append("")

        # Rescrape summary
        rescrape = report.validation_errors.get("nfo_present", 0) + report.validation_errors.get("nfo_valid", 0)
        if rescrape:
            lines.append(f"    ⚠ {rescrape} items auraient besoin d'un re-scrape (NFO manquant ou cassé)")
            lines.append("      ✓ Corriger: personalscraper library-rescrape --dry-run")
            lines.append("")

    # === SECTION 3: ANALYSE ENCODING ===
    if report.analysis_item_count:
        lines.append(sep)
        lines.append("  3. ANALYSE — Encodage vidéo (ffprobe)")
        lines.append(sep)
        lines.append("")
        coverage = (report.analysis_item_count * 100 // report.total_items) if report.total_items else 0
        lines.append(
            f"    Analysés: {report.analysis_item_count} items, "
            f"{report.analysis_file_count} fichiers ({coverage}% de la bibliothèque)"
        )
        if coverage < 100:
            lines.append("    ⚠ Analyse partielle. Compléter: personalscraper library-analyze --incremental")
        lines.append("")

        if report.codec_distribution:
            lines.append("    Codecs vidéo:")
            total_files = sum(report.codec_distribution.values())
            for codec, count in sorted(report.codec_distribution.items(), key=lambda x: -x[1]):
                pct = count * 100 // total_files if total_files else 0
                lines.append(f"      {codec}: {count} fichiers ({pct}%)")
            lines.append("")

        if report.audio_distribution:
            lines.append("    Profils audio:")
            for profile, count in sorted(report.audio_distribution.items(), key=lambda x: -x[1]):
                labels = {
                    "multi": "MULTI (multi-langues)",
                    "vf": "VF (français)",
                    "vostfr": "VOSTFR (VO + sous-titres FR)",
                    "vo": "VO (version originale)",
                }
                label = labels.get(profile, profile)
                lines.append(f"      {label}: {count} fichiers")
            lines.append("")

    # === SECTION 4: RECOMMANDATIONS ===
    if report.recommendation_count:
        lines.append(sep)
        lines.append("  4. RECOMMANDATIONS — Re-téléchargements suggérés")
        lines.append(sep)
        lines.append("")
        lines.append(f"    Total: {report.recommendation_count} items à améliorer")
        lines.append(f"    Économie potentielle: ~{report.estimated_savings_gb:.1f} GB")
        lines.append("")

        for prio in ("high", "medium", "low"):
            count = report.recommendations_by_priority.get(prio, 0)
            if count:
                labels = {"high": "🔴 Haute", "medium": "🟡 Moyenne", "low": "🔵 Basse"}
                lines.append(f"    {labels.get(prio, prio)}: {count}")

        lines.append("")
        lines.append("    Détail:")
        for rec in report.recommendation_details:
            prio_mark = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(rec["priority"], "?")
            lines.append(
                f"      {prio_mark} {rec['title']} — {rec['codec']} {rec['resolution']} "
                f"{rec['size_gb']:.1f}GB {rec['audio_profile']}"
            )
            for reason in rec["reasons"]:
                lines.append(f"           → {reason}")

        lines.append("")
        lines.append("    ✓ Exporter: personalscraper library-recommend --export csv")
        lines.append("")

    # === SECTION 5: TOP 20 ===
    if report.top_largest:
        lines.append(sep)
        lines.append("  5. TOP 20 — Plus gros items")
        lines.append(sep)
        lines.append("")
        for i, (title, size) in enumerate(report.top_largest, 1):
            lines.append(f"    {i:>2}. {size:>7.1f} GB  {title}")
        lines.append("")

    # === SECTION 6: RESCRAPE ===
    if report.rescrape_fixed or report.rescrape_skipped or report.rescrape_errors:
        total_r = report.rescrape_fixed + report.rescrape_skipped + report.rescrape_errors
        lines.append(sep)
        lines.append("  6. RESCRAPE — Réparations API (TMDB/TVDB)")
        lines.append(sep)
        lines.append("")
        lines.append(
            f"    Réparés: {report.rescrape_fixed}  Ignorés: {report.rescrape_skipped}  "
            f"Erreurs: {report.rescrape_errors}  (total: {total_r})"
        )
        lines.append("")
        if report.rescrape_nfo_count:
            lines.append(f"    NFO régénérés: {report.rescrape_nfo_count}")
        if report.rescrape_artwork_count:
            lines.append(f"    Artwork téléchargé: {report.rescrape_artwork_count}")
        if report.rescrape_episodes_count:
            lines.append(f"    Épisodes renommés: {report.rescrape_episodes_count}")
        if report.rescrape_skipped:
            lines.append(f"    ⚠ {report.rescrape_skipped} items ignorés (confiance trop basse ou non trouvé)")
            lines.append("      ✓ Réessayer: personalscraper library-rescrape --interactive")
        lines.append("")

    # === ACTIONS SUGGÉRÉES ===
    lines.append(sep)
    lines.append("  ACTIONS SUGGÉRÉES")
    lines.append(sep)
    lines.append("")

    actions = []
    if report.scan_issues.get("actors_dir_present", 0):
        n = report.scan_issues["actors_dir_present"]
        actions.append(f"  1. Supprimer {n} dossiers .actors/ inutiles (~5 GB)")
        actions.append("     → personalscraper library-clean --only actors --apply")
    if report.scan_issues.get("junk_files", 0):
        n = report.scan_issues["junk_files"]
        actions.append(f"  2. Supprimer {n} fichiers parasites (.DS_Store, ._*, Thumbs.db)")
        actions.append("     → personalscraper library-clean --only junk --apply")
    # NFO presence/validity gap. ``nfo_invalid_count`` aggregates DB rows where
    # ``nfo_status`` is missing OR invalid (analyzer.nfo.invalid + analyzer.nfo.missing)
    # — we surface it here so a freshly-loaded library that never went through
    # validate.json still reports the rescrape opportunity.
    rescrape = report.validation_errors.get("nfo_present", 0) + report.validation_errors.get("nfo_valid", 0)
    if not rescrape and report.nfo_invalid_count:
        rescrape = report.nfo_invalid_count
    if rescrape:
        actions.append(f"  3. Re-scraper {rescrape} items (NFO manquant ou XML invalide)")
        actions.append("     → personalscraper library-rescrape --dry-run")
    if report.poster_missing_count:
        actions.append(f"  3b. Récupérer l'artwork manquant pour {report.poster_missing_count} items (poster absent)")
        actions.append("     → personalscraper library-rescrape --only artwork")
    if report.analysis_item_count and report.total_items and report.analysis_item_count < report.total_items:
        remaining = report.total_items - report.analysis_item_count
        actions.append(f"  4. Compléter l'analyse ffprobe ({remaining} items restants)")
        actions.append("     → personalscraper library-analyze --incremental")
    if report.recommendation_count:
        actions.append(f"  5. Examiner {report.recommendation_count} recommandations de re-téléchargement")
        actions.append("     → personalscraper library-recommend --export csv")

    if actions:
        lines.extend(actions)
    else:
        lines.append("  Aucune action nécessaire. La bibliothèque est en bon état.")

    lines.append("")
    return "\n".join(lines)
