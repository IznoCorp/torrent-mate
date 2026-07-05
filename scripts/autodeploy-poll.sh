#!/usr/bin/env bash
#
# autodeploy-poll.sh — déploiement continu lié aux branches (TorrentMate).
#
# Surveille origin et redéploie un clone quand sa branche suivie avance :
#   prod    : ~/deploy/torrentmate   ⟵ main     → scripts/deploy.sh
#   staging : ~/staging/torrentmate  ⟵ staging  → scripts/deploy-staging.sh
#
# Modèle CD opérateur calqué sur KanbanMate : un push sur `main` redéploie la
# prod ; un push sur `staging` redéploie le staging. Lancé comme app PM2
# `torrentmate-autodeploy` ; boucle toutes les AUTODEPLOY_INTERVAL secondes
# (défaut 60 s). `--once` = une seule passe (utile en test / CI).
#
# Chemins des clones surchargeables via TM_PROD_CLONE / TM_STAGING_CLONE.
#
# REQUIERT des remotes SSH (silencieux / non interactif) — HTTPS+GCM ouvrirait
# une fenêtre d'identifiants à chaque passe. Toutes les opérations réseau git
# sont bornées par `timeout` (le serveur peut accepter le TCP sans répondre).
#
set -euo pipefail

PROD_CLONE="${TM_PROD_CLONE:-$HOME/deploy/torrentmate}"
STAGING_CLONE="${TM_STAGING_CLONE:-$HOME/staging/torrentmate}"

# Fenêtre maximale (secondes) pour toute opération réseau git (fetch / pull) —
# évite un blocage indéfini si le remote accepte le TCP sans jamais répondre.
GIT_NET_TIMEOUT="${TM_GIT_NET_TIMEOUT:-60}"

stamp() { date "+%Y-%m-%d %H:%M:%S"; }

# redeploy_if_advanced <clone> <branch> <strategy> <deploy_script>
#
#   strategy = "pull"  → git pull --ff-only origin <branch>
#                        (prod : `main` ne fait qu'avancer, fast-forward strict)
#            = "reset" → git reset --hard origin/<branch>
#                        (staging : le clone SUIT le remote, qui peut être
#                         rebasé / force-push par une branche de feature ;
#                         un fast-forward échouerait sur un historique divergent)
#
# Fail-soft : toute erreur (clone absent, réseau, script) journalise et rend la
# main sans propager — la boucle appelante continue.
redeploy_if_advanced() {
  local clone="$1" branch="$2" strategy="$3" deploy="$4"

  cd "$clone" 2>/dev/null || { echo "[$(stamp)] clone absent : $clone — ignoré"; return 0; }

  # Rafraîchit les refs distants (borné dans le temps).
  timeout "$GIT_NET_TIMEOUT" git fetch --prune --quiet origin "$branch" 2>/dev/null \
    || { echo "[$(stamp)] $clone : git fetch origin $branch a échoué (réseau ?) — passe ignorée"; return 0; }

  local cur rem
  cur="$(git rev-parse HEAD 2>/dev/null)" \
    || { echo "[$(stamp)] $clone : HEAD illisible — passe ignorée"; return 0; }
  rem="$(git rev-parse "origin/$branch" 2>/dev/null)" \
    || { echo "[$(stamp)] $clone : origin/$branch introuvable — passe ignorée"; return 0; }

  if [ "$cur" = "$rem" ]; then
    echo "[$(stamp)] $clone : $branch à jour (${cur:0:8})"
    return 0
  fi

  echo "[$(stamp)] $clone : $branch a avancé ${cur:0:8} -> ${rem:0:8} — déploiement"

  # Se placer sur la bonne branche (robustesse au premier lancement du clone).
  git checkout -q "$branch" 2>/dev/null || git checkout -q -B "$branch" "origin/$branch" 2>/dev/null

  case "$strategy" in
    pull)
      # main ne fait qu'avancer → fast-forward strict. Après le pull, HEAD ==
      # origin/main, donc le garde-fou de deploy.sh (main synchronisée) passe.
      if ! timeout "$GIT_NET_TIMEOUT" git pull --ff-only --quiet origin "$branch"; then
        echo "[$(stamp)] $clone : git pull --ff-only origin $branch a échoué — passe ignorée"
        return 0
      fi
      ;;
    reset)
      # staging suit strictement le remote. Les scripts de déploiement refusent
      # un arbre sale, donc un clone ne porte jamais de travail local à écraser.
      if ! git reset -q --hard "origin/$branch"; then
        echo "[$(stamp)] $clone : reset --hard origin/$branch a échoué — passe ignorée"
        return 0
      fi
      ;;
    *)
      echo "[$(stamp)] $clone : stratégie inconnue '$strategy' — passe ignorée"
      return 0
      ;;
  esac

  # Déploiement : préfixe chaque ligne d'un timestamp pour les logs PM2.
  if [ ! -f "$deploy" ]; then
    echo "[$(stamp)] $clone : script de déploiement absent ($deploy) — passe ignorée"
    return 0
  fi
  if bash "$deploy" 2>&1 | sed "s/^/[$(stamp)] /"; then
    echo "[$(stamp)] $clone : déploiement $branch terminé (${rem:0:8})"
  else
    echo "[$(stamp)] $clone : $deploy en échec — passe ignorée"
  fi
  return 0
}

one_pass() {
  redeploy_if_advanced "$PROD_CLONE"    main    pull  "$PROD_CLONE/scripts/deploy.sh"
  redeploy_if_advanced "$STAGING_CLONE" staging reset "$STAGING_CLONE/scripts/deploy-staging.sh"
}

if [ "${1:-}" = "--once" ]; then
  # `if !` désactive errexit dans one_pass → une passe fait tout son travail
  # sans qu'une erreur interne ne fasse sortir prématurément.
  if ! one_pass; then echo "[$(stamp)] passe unique : erreur non fatale"; fi
  exit 0
fi

INTERVAL="${AUTODEPLOY_INTERVAL:-60}"
echo "[$(stamp)] poller autodeploy actif (toutes les ${INTERVAL}s) : deploy<-main, staging<-staging"
while true; do
  # Fail-soft par cycle : une passe en échec ne doit JAMAIS tuer la boucle.
  # `if ! one_pass` neutralise errexit à l'intérieur de la fonction, si bien
  # qu'un cycle raté journalise et on enchaîne au cycle suivant.
  if ! one_pass; then
    echo "[$(stamp)] cycle en échec — on poursuit"
  fi
  sleep "$INTERVAL"
done
