# V6 — LOG + NOTIFY : Brainstorming

> Logging structuré + notifications Telegram

## Contexte

Chaque version (V1→V5) produit des opérations qui doivent être tracées et notifiées.
V6 fournit le système transversal de logging et notification.

Note : le module logging doit être disponible dès V0 pour être utilisé par toutes les versions.

## Décisions prises

### Logging

- **Format** : JSON structuré (parseable, exploitable par des outils)
- **Emplacement** : `logs/` à la racine du projet (ajouté au `.gitignore`)
- **Rétention** : 30 jours, 1 fichier par jour, rotation automatique
- **Nommage** : `logs/personalscraper-YYYY-MM-DD.json`
- Chaque entrée contient : timestamp, level, module, message, metadata
- Supporte `--verbose` (DEBUG) et `--quiet` (WARNING+) via le CLI

### Notifications Telegram

- **Bot** : fourni par l'utilisateur en temps voulu
- **Config** : `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` dans `.env`
- **Si pas configuré** : pas de notification, pas d'erreur (silencieux)
- **Granularité** : résumé final du pipeline uniquement (pas par étape)
- **Format** : HTML (Telegram parse_mode), belle mise en forme, emojis pertinents
- **API** : `POST https://api.telegram.org/bot{token}/sendMessage`

### Exemple de message Telegram

```html
📊 <b>PersonalScraper — Rapport</b> ━━━━━━━━━━━━━━━━━━━━━━ 📥 <b>Ingest</b> ✅ 3
torrents ingérés (2 copiés, 1 déplacé) ⏭️ 1 torrent ignoré (déjà traité) 📂
<b>Sort</b> 🎬 2 films triés 📺 4 épisodes triés 🔍 <b>Scrape</b> ✅ 2 films
scrapés ✅ 1 série scrapée (4 épisodes) ⚠️ 1 film non matché (confiance faible)
💾 <b>Dispatch</b> ✅ 2 films → Disk3 ✅ 4 épisodes → Disk2 (merge) ⚠️ 1 film
ignoré (espace insuffisant) ⏱️ Durée totale : 4min 32s 📅 2026-04-11 03:04:32
```

## Contraintes techniques

1. Le module logging doit être intégré **dès V0** (disponible pour toutes les versions)
2. Supporte `--verbose` et `--quiet` de manière cohérente avec le CLI Click
3. Les notifications ne doivent **jamais bloquer** le pipeline (try/except, timeout court)
4. Le log JSON doit être exploitable pour diagnostiquer les erreurs sans relancer
5. Rotation automatique : supprimer les fichiers de plus de 30 jours au démarrage
6. Chaque version (V1→V5) alimente un objet "rapport" qui est finalisé en V6 pour la notification
