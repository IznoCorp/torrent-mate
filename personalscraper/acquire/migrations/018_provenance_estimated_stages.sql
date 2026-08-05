-- personalscraper/acquire/migrations/018_provenance_estimated_stages.sql
-- Marquer les instants d'étape ESTIMÉS (feature `instants-estimes`, arbitrage opérateur).
--
-- Décision de l'opérateur, réaffirmée après que la réserve lui a été posée : les étapes
-- intermédiaires d'un parcours reconstruit doivent porter une date cohérente plutôt que
-- rien, même quand aucune source ne la connaît. Le pipeline garantit l'ordre
-- (grab → ingestion → scraping → rangement, §14.2) et les deux bornes sont exactes, donc
-- une valeur répartie entre elles est cohérente — mais elle n'est PAS mesurée.
--
-- Cette colonne est ce qui empêche l'estimation de devenir un mensonge : elle nomme les
-- étapes dont l'instant a été CALCULÉ (« ingested,scraped »), de sorte que l'interface
-- puisse afficher une date tout en disant qu'elle est approchée, et qu'un lecteur futur
-- des données ne prenne jamais une interpolation pour une mesure. NULL = tout ce que la
-- ligne porte a été observé.
--
-- ALTER purement additif : toute lecture/écriture antérieure ignore la colonne.

BEGIN TRANSACTION;

ALTER TABLE staging_provenance ADD COLUMN estimated_stages TEXT;

INSERT OR IGNORE INTO schema_version(version) VALUES (18);
PRAGMA user_version = 18;

COMMIT;
