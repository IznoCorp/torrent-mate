# V5 — LOG + NOTIFY : Brainstorming

> Logging structuré + notifications Telegram

## Contexte

Le pipeline a besoin d'un système de logging pour tracer toutes les opérations
et d'un système de notification pour informer l'utilisateur des résultats.

## Logging

### Besoins

- Journal de chaque opération avec horodatage
- Niveau de détail configurable (DEBUG, INFO, WARNING, ERROR)
- Rotation des logs (ne pas accumuler indéfiniment)
- Consultable facilement (fichier texte ou structured JSON)

### Questions

- [ ] Format : texte lisible ou JSON structuré (parseable) ?
- [ ] Emplacement : dans le projet ou dans un dossier système (`/var/log/`, `~/logs/`) ?
- [ ] Rétention : combien de jours/Mo de logs garder ?

## Notifications Telegram

### Besoins

- Notification à la fin d'un run du pipeline (succès/échec)
- Résumé : nombre de fichiers ingérés, triés, scrapés, dispatchés
- Alertes en cas d'erreur (espace disque faible, échec scraping, etc.)

### Setup nécessaire

- Bot Telegram (token à créer via @BotFather)
- Chat ID de l'utilisateur
- API simple : HTTP POST vers `https://api.telegram.org/bot<token>/sendMessage`

### Questions

- [ ] Bot déjà existant ou à créer ?
- [ ] Notification par étape ou uniquement le résumé final ?
- [ ] Format du message (texte simple, markdown, avec emojis ?)

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
