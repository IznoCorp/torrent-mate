#!/usr/bin/env python3
"""Exécutable de complétude de la spine — « tout doit être daté, et différenciable ».

Ce garde-fou existe à cause d'un échec de méthode, pas d'un défaut de code : le même bug
(« Récupéré · inconnue », « Ingéré · inconnue ») a été remonté **trois fois** par
l'opérateur, et déclaré corrigé trois fois — parce que chaque vérification portait sur les
champs qui venaient d'être touchés, jamais sur les quatre étapes ensemble ni sur l'écran.
``grabbed_at`` n'avait tout simplement jamais été mesuré.

Le script pose donc les deux seules questions que l'opérateur pose devant l'écran :

1. **Est-ce daté ?** Pour chaque étape inconnue d'un parcours, il va chercher si une
   source existe malgré tout. Une étape inconnue **alors qu'elle est récupérable** est une
   anomalie : la réparation n'est pas finie. Une étape inconnue **sans aucune source** est
   un constat prouvé, et n'est pas comptée.
2. **Est-ce différenciable ?** Deux acquisitions du même feuilleton doivent pouvoir être
   distinguées à l'écran. Une ligne de série sans saison/épisode alors que sa ligne
   ``wanted`` les porte est une anomalie : quatre cartes « Silo » identiques se lisent
   comme des doublons.

Les sources interrogées, par étape :

===============  ==========================================================
``grabbed_at``   ``seed_obligation.added_at`` (posée au grab), sinon
                 ``wanted.last_search_at`` — le grab suit immédiatement la
                 recherche qui l'a produit (écart mesuré ≤ 25 s sur 35 cas).
``ingested_at``  ``ingested_torrents.json`` (date exacte par hash), sinon
                 l'étape ``ingest`` du run qui a porté la release.
``scraped_at``   l'étape ``scrape`` de ce même run.
``saison/épisode`` la ligne ``wanted`` du hash.
===============  ==========================================================

Code de sortie = nombre d'anomalies ; 0 = la spine est complète et lisible.

Usage:
    python scripts/check-spine-complete.py
    python scripts/check-spine-complete.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass


@dataclass
class Gap:
    """Un manque RÉPARABLE sur un parcours (une anomalie comptée).

    Attributes:
        info_hash: Le parcours concerné.
        title: Le titre du suivi, tel que la carte l'affiche.
        field: Le champ manquant (``grabbed_at`` / ``ingested_at`` / ``scraped_at`` /
            ``identity``).
        source: La source qui pourrait le remplir — donc la preuve que ce n'est pas
            « perdu » mais « pas encore repris ».
    """

    info_hash: str
    title: str
    field: str
    source: str

    def line(self) -> str:
        """Rend l'anomalie en une ligne lisible."""
        return f"❌ [{self.field}] {self.title} ({self.info_hash[:12]}…) : récupérable via {self.source}"


def _iso_to_epoch(raw: object) -> int | None:
    """Parse une date ISO-8601 en epoch, ou None si illisible."""
    import datetime as _dt

    if not isinstance(raw, str):
        return None
    try:
        return int(_dt.datetime.fromisoformat(raw).timestamp())
    except ValueError:
        return None


def _runs_by_release(indexer_conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Indexe ``{nom de release: {étape: epoch}}`` depuis le journal des runs.

    L'étape d'ingestion de chaque run nomme, dans ses ``reasons``, les releases qu'elle a
    copiées ; le même run les a ensuite scrapées. Le nom de release rattache donc un
    torrent à son run, et les instants par étape de ce run datent son parcours.

    Args:
        indexer_conn: Connexion ouverte sur ``library.db``.

    Returns:
        L'index par nom de release ; vide en cas d'erreur de lecture.
    """
    index: dict[str, dict[str, int]] = {}
    try:
        rows = indexer_conn.execute(
            "SELECT steps_json FROM pipeline_run WHERE steps_json IS NOT NULL ORDER BY started_at ASC"
        ).fetchall()
    except sqlite3.Error:
        return index
    for (steps_json,) in rows:
        try:
            steps = json.loads(steps_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(steps, list):
            continue
        stages: dict[str, int] = {}
        reasons: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            ended = step.get("ended_at")
            if isinstance(ended, (int, float)):
                stages[str(step.get("name"))] = int(ended)
            if step.get("name") == "ingest":
                reasons = [str(r) for r in (step.get("reasons") or [])]
        for reason in reasons:
            name = reason.split(" → ")[0].split(":")[0].strip()
            if name:
                index.setdefault(name, stages)
    return index


def collect_gaps(
    acquire_conn: sqlite3.Connection,
    indexer_conn: sqlite3.Connection,
    ingest_tracker: dict[str, dict[str, object]] | None = None,
) -> list[Gap]:
    """Confronte chaque parcours à ses sources et rend les manques RÉPARABLES.

    Cœur pur — aucune configuration, aucune I/O au-delà des connexions ouvertes — pour
    que les tests l'exercent directement sur des bases temporaires.

    Args:
        acquire_conn: Connexion sur ``acquire.db``.
        indexer_conn: Connexion sur ``library.db`` (journal des runs).
        ingest_tracker: ``ingested_torrents.json`` déjà chargé, ou None.

    Returns:
        Les manques réparables, dans l'ordre des parcours.
    """
    acquire_conn.row_factory = sqlite3.Row
    tracker = {k.lower(): v for k, v in (ingest_tracker or {}).items()}
    runs = _runs_by_release(indexer_conn)

    obligations: dict[str, int] = {}
    for row in acquire_conn.execute("SELECT info_hash, added_at FROM seed_obligation"):
        h = (row["info_hash"] or "").lower()
        obligations[h] = min(obligations.get(h, row["added_at"]), row["added_at"])

    wanted: dict[str, sqlite3.Row] = {}
    for row in acquire_conn.execute(
        "SELECT grabbed_hash, kind, season, episode, last_search_at FROM wanted "
        "WHERE grabbed_hash IS NOT NULL AND grabbed_hash != ''"
    ):
        wanted.setdefault(row["grabbed_hash"].lower(), row)

    titles = {r["id"]: r["title"] for r in acquire_conn.execute("SELECT id, title FROM followed_series")}
    columns = {r[1] for r in acquire_conn.execute("PRAGMA table_info('staging_provenance')")}

    gaps: list[Gap] = []
    for row in acquire_conn.execute("SELECT * FROM staging_provenance ORDER BY rowid"):
        h = (row["info_hash"] or "").lower()
        title = titles.get(row["followed_id"], "(sans suivi)") if row["followed_id"] is not None else "(sans suivi)"
        w = wanted.get(h)
        entry = tracker.get(h) or {}
        release = entry.get("name")
        stages = runs.get(release, {}) if isinstance(release, str) else {}

        if row["grabbed_at"] is None:
            if h in obligations:
                gaps.append(Gap(h, title, "grabbed_at", "seed_obligation.added_at"))
            elif w is not None and w["last_search_at"] is not None:
                gaps.append(Gap(h, title, "grabbed_at", "wanted.last_search_at"))
        if row["ingested_at"] is None:
            if _iso_to_epoch(entry.get("date")) is not None:
                gaps.append(Gap(h, title, "ingested_at", "ingested_torrents.json"))
            elif "ingest" in stages:
                gaps.append(Gap(h, title, "ingested_at", "pipeline_run (étape ingest)"))
        if row["scraped_at"] is None and "scrape" in stages:
            gaps.append(Gap(h, title, "scraped_at", "pipeline_run (étape scrape)"))

        # L'ORDRE du workflow (§14.2) : un instant, mesuré ou estimé, ne peut pas
        # contredire la séquence. Une estimation qui placerait l'ingestion après le
        # rangement serait pire que le vide qu'elle remplace.
        suite = [row["grabbed_at"], row["ingested_at"], row["scraped_at"], row["dispatched_at"]]
        connus = [v for v in suite if v is not None]
        if connus != sorted(connus):
            gaps.append(Gap(h, title, "ordre", "les instants contredisent la séquence du workflow"))

        # « Différenciable » : une série dont la ligne wanted porte une saison DOIT la
        # porter aussi, sinon deux acquisitions du même feuilleton sont indiscernables.
        if w is not None and w["season"] is not None:
            has_columns = {"season", "episode"} <= columns
            if not has_columns or row["season"] is None:
                gaps.append(Gap(h, title, "identity", "wanted.season / wanted.episode"))

    return gaps


def _open_ro(path: str) -> sqlite3.Connection:
    """Ouvre une base SQLite strictement en lecture seule."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main() -> int:
    """Exécute le contrôle sur les bases configurées.

    Returns:
        Le nombre d'anomalies (0 = complet), ou 2 si une base manque.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Dump JSON au lieu des lignes lisibles.")
    args = parser.parse_args()

    from personalscraper.conf.loader import load_config

    config = load_config()
    acquire_path, indexer_path = config.acquire.db_path, config.indexer.db_path
    if acquire_path is None or not acquire_path.exists() or indexer_path is None or not indexer_path.exists():
        print("acquire.db ou library.db introuvable", file=sys.stderr)
        return 2

    tracker: dict[str, dict[str, object]] = {}
    try:
        tracker = json.loads((config.paths.data_dir / "ingested_torrents.json").read_text())
    except (OSError, ValueError):
        pass

    acquire_conn, indexer_conn = _open_ro(str(acquire_path)), _open_ro(str(indexer_path))
    try:
        gaps = collect_gaps(acquire_conn, indexer_conn, tracker)
    finally:
        acquire_conn.close()
        indexer_conn.close()

    if args.json:
        print(json.dumps([asdict(g) for g in gaps], indent=2, ensure_ascii=False))
    else:
        for gap in gaps:
            print(gap.line())
        par_champ: dict[str, int] = {}
        for gap in gaps:
            par_champ[gap.field] = par_champ.get(gap.field, 0) + 1
        detail = ", ".join(f"{n} {champ}" for champ, n in sorted(par_champ.items())) or "aucune"
        print(f"\n{len(gaps)} manque(s) RÉPARABLE(s) — {detail}.")
        if gaps:
            print("La réparation n'est pas finie : ces étapes ont une source et sont pourtant vides.")
    return len(gaps)


if __name__ == "__main__":
    raise SystemExit(main())
