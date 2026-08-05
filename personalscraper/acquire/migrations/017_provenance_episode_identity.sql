-- personalscraper/acquire/migrations/017_provenance_episode_identity.sql
-- Rendre un parcours DIFFÉRENCIABLE (feature `parcours-dates-distincts`, §12 / DOIT-1).
--
-- `media_ref_json` ne porte que l'identité de l'ŒUVRE (l'id de série), jamais l'épisode.
-- Quatre acquisitions de « Silo » avaient donc exactement la même identité affichable :
-- quatre cartes rigoureusement identiques, dont certaines datées et d'autres non — que
-- l'opérateur a lues, à raison, comme des doublons. Une carte qu'on ne peut pas
-- distinguer d'une autre ne dit rien.
--
-- La saison et l'épisode existent depuis toujours sur la ligne `wanted` correspondante ;
-- ils manquaient simplement au registre. ALTER purement additif : toute lecture/écriture
-- antérieure ignore les colonnes, et NULL — la valeur par défaut — est correct pour un
-- film comme pour un parcours dont l'épisode est inconnu.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance ADD COLUMN season INTEGER;
ALTER TABLE staging_provenance ADD COLUMN episode INTEGER;

INSERT OR IGNORE INTO schema_version(version) VALUES (17);
PRAGMA user_version = 17;

COMMIT;
