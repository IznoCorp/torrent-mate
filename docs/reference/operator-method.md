# La méthode de l'opérateur — TorrentMate, refonte de l'interface

Dictée le 2026-09-12 au soir, question par question, à la session d'audit. Ce fichier est à
l'opérateur seul d'amender ; l'auditeur le lit, l'orchestrateur l'applique. Version de travail : à
placer dans le dépôt (`docs/reference/operator-method.md`) ou à garder hors dépôt, sur son mot.

## 1. Le critère de fin de la maquette

L'app doit fonctionner sur Mac. C'est une PWA ; presque tous les bugs rencontrés sur Android existaient
aussi sur Mac. L'objectif : la maquette complète, l'app prête graphiquement sur toute sa surface, avec
une ergonomie qui permet de faire tout ce qui est attendu de l'app — pour que le test soit complet.
Quand la surface est suffisante (« 90 % peut-être »), la refonte du backend commence ; le reste
s'accroche au front à ce moment-là.

## 2. Ce qu'est un bug qui compte

Principalement s'il bloque dans un parcours et/ou gêne visuellement même sans bloquer. « Je veux
pouvoir faire fonctionner la maquette comme je ferai fonctionner l'app. » Un défaut d'instrument se
file, il n'arrête pas le travail.

## 3. Comment il teste

Sur son Android (PWA sur tm-design) principalement — la version smartphone est prioritaire — et
parfois sur le Mac. Il teste quand il veut ; les retours sont pris comme ils viennent. Il accepte
d'être invité à tester une nouveauté, avec une capture d'écran quand c'est nécessaire, jamais
systématiquement.

## 4. Sa place dans les décisions

« Quand c'est possible, décide sans moi. Surtout s'il s'agit seulement de faire avancer les merges ou
les lots. On continue. » Une décision fonctionnelle (domaine) lui est posée, mais on avance sur tout
ce qui n'en dépend pas. Il balaie régulièrement les questions en attente avec `/orchestrator:decide`.

## 5. Le grain de ce qui atterrit

Gros lots, qui avancent ; des petits changements après coup, ce n'est pas grave. C'est moins vrai
pour les grosses décisions d'architecture, où l'on prend le temps avant.

## 6. Gaspillage et rigueur

« Un refactor nécessaire pour rendre l'app vraiment fiable et propre architecturalement, c'est
légitime. La rigueur doit être légitime ; si elle est contre-productive, elle est illégitime. »

## 7. Les documents

Il lit la session qui le guide, les questions qu'on lui pose et ce qu'il voit sur l'appareil. Le
reste (registre, plan, état, office, corps de PR) est pour les agents.

## 8. La liaison au backend

Pas encore défini ; à définir dans la mesure du possible. Une fois la surface suffisante, on reprend
ce qui existe : adapter, réarchitecturer, transformer — refaire seulement s'il le faut.

## 9. L'audit

Un auditeur est lancé par commande depuis l'orchestrateur (`Audit : <sujet>`, même modèle, Remote
Control), sans succession ; il indique à l'orchestrateur ce qu'il doit changer, peut resserrer ou
desserrer la méthodologie, et vérifie que les changements portent, sont appliqués et applicables.
`audit-end` met fin à l'audit ; l'orchestrateur ferme la session de l'auditeur.

## Les sept mesures en vigueur depuis le 2026-09-12 (réversibles sur son mot)

1. Geler l'appareil : aucune garde, aucun bras, aucune vague tooling sans un défaut qui l'a atteint.
2. Un tour de lecture par lot, zéro par micro-vague ; les mineurs d'instruments sont filés.
3. Le geste post-fusion est un script exécuté par l'orchestrateur, sans agent.
4. Une PR docs de l'office par lot, en fin de lot.
5. Un train de correctifs par jour, pas une micro-vague par bug.
6. Deux agents en parallèle au plus.
7. L13 (la mort du moteur) en priorité après les vagues en vol.

« On remettra la rigueur en place si elle s'avère nécessaire. »
