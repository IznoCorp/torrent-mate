-- Schema migration 014 — multi-episode span support on media_release.
--
-- Background:
--
-- ``path``-level parsing folds a multi-episode file (« S09E23-24 - … .mkv »)
-- into a single release linked to its FIRST episode only (release_linker V1).
-- Ownership queries join episode ← media_release ← media_file, so the second
-- episode of the span is never "owned": the acquisitions truth-table keeps it
-- « manquant », the wanted row stays pending forever, and grab keeps searching
-- for content already on disk (live incident 2026-07-15: Friends S09E23-24 and
-- S10E17-18 double finales).
--
-- ``episode_end_id`` records the LAST episode covered by the release. NULL for
-- ordinary single-episode releases (the overwhelming majority — no behaviour
-- change). When set, ownership expands the release to every episode number
-- between the start row and the end row (both rows exist; the linker creates
-- the full range).

ALTER TABLE media_release ADD COLUMN episode_end_id INTEGER REFERENCES episode(id);

-- ---------------------------------------------------------------------------
-- Version bump.
-- ---------------------------------------------------------------------------

INSERT INTO schema_version (version) VALUES (14);
PRAGMA user_version = 14;
