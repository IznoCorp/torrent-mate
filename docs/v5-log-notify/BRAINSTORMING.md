# V5 — LOG + NOTIFY : Brainstorming

> Logging structuré + notifications Telegram

## Contexte

Chaque version (V1→V4) produit des opérations qui doivent être tracées et notifiées.
V5 fournit le système transversal de logging et notification.

## Décisions prises

### Logging

- **Fichier de log** structuré avec horodatage
- Utilisé par toutes les versions (V1→V4)
- Module Python importable par chaque composant du pipeline

### Notifications Telegram

- Bot Telegram pour les notifications
- API simple : `POST https://api.telegram.org/bot{token}/sendMessage`
- Config dans `.env` : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Questions ouvertes

- [ ] Format log : texte lisible humainement ou JSON structuré (parseable) ?
- [ ] Emplacement : dans le projet (`logs/`) ou dossier dédié ?
- [ ] Rétention : combien de jours/Mo de logs garder ? Rotation automatique ?
- [ ] Bot Telegram : déjà existant ou à créer ?
- [ ] Notifications : résumé final uniquement ou par étape ?
- [ ] Format message Telegram : texte simple, markdown, emojis ?

## Contraintes techniques

1. Le logging doit être intégré dès V0 (module disponible pour toutes les versions)
2. Le module doit supporter `--verbose` et `--quiet` de manière cohérente
3. Les notifications ne doivent pas bloquer le pipeline en cas d'échec Telegram
4. Le log doit être exploitable pour diagnostiquer les erreurs sans relancer le pipeline

## Notes de brainstorming

_À compléter lors de la session de brainstorming dédiée_
