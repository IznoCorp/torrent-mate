# Product intent → surface map

**What this file is.** `docs/reference/product-intent.md` is the constitution: it says what the
product must BE, in fourteen DOIT clauses and nine NE-DOIT-PAS clauses. Nothing in this repository
read it against the interface until 2026-08-29 (B-142): three instruments compare the interface to
what already exists, and a capability the constitution requires that neither the maquette nor the
backend has was invisible to every gate — which is how three dictated sections went a month
unnoticed. This file is the **declared mapping** that instrument needs: one row per clause, the
surface that serves it, a verdict, and — where the verdict is « to draw » — the lot that owes it.

**A mapping is a design decision, not a grep.** It was written by L10-ter clause by clause against
the tree, never seeded from what exists: five rows say « to draw », and a row that says « served »
names the proof that says so. **The operator amends this file; an agent proposes.** The arm that
reads it is specified in `docs/features/maquette-l10-ter/MODEL.md` § 4 and built by L15.

**The vocabulary of the `Verdict` column**, and the arm refuses any other word:

| Verdict | Means |
| --- | --- |
| `served` | a surface in the tree serves the clause, and the `Proof` column names the rule or guard that reads it |
| `served, unproved` | the surface exists, no instrument reads the clause; the `Proof` column names the lot that owes the instrument |
| `partly` | one half served with its proof, the other half `to draw` — both named in the row |
| `to draw` | no surface serves it; the `Owner` column names the lot |
| `outside the interface` | the clause binds the backend or the method, not a surface; the row says what the interface's share is |

Surfaces are named by **route path** (as `routes/*` declares them) or by **feature directory**
(`features/<domain>/`), never by a component name — a component moves, an address and a domain do
not.

---

## DOIT

| Clause | Surface | Verdict | Proof / Owner |
| --- | --- | --- | --- |
| **DOIT-1** — tout montrer, en français clair | `features/arrivals` (each item's state and timeline), `features/acquisition` (per-film and per-episode states), `features/library` | `partly` | served for the drawn pages: `scripts/check-no-french.py` (no interface text outside `fr.json`), R66 (Arrivées says what really happened), R63 (a card says what the engine knows). **To draw**: the pipeline's own states, which live on `/pipeline` — **L20** |
| **DOIT-2** — montrer ce qui ne se passe pas, et pourquoi | `features/arrivals` (the stuck queue, each with its reason); `features/acquisition` (waiting, searching) | `partly` | served: R66, R57 (a decision, with its candidates). **To draw**: a torrent deferred for ratio or space — `GET /api/acquisition/stalled-grabs` and `/obligations` are called by nothing — **L16** (§18) |
| **DOIT-3** — agir là où l'on observe | `/system` (run, kill, pause, resume declared and wired) | `partly` | served: `harness/machine.py` R67. **To draw**: « relancer le watcher » — `POST /api/pipeline/watcher` is in neither contract's use — **L20**; the tracker policy set from the ratio surface — **L16** |
| **DOIT-4** — toujours accepter une action légitime, mise en file visible | `features/arrivals` (the resolve queue, « En file ») | `served, unproved` | the pattern exists (resolve → 202 → `queue` step); no rule drives the mock's « pipeline busy » scenario and reads « En file » on the surface — the instrument is **L19**'s, with the producers that draw the queue |
| **DOIT-5** — aller au bout et le montrer | `features/arrivals` (the journey sheet), `/resolution/$folder` | `partly` | served: R57, `harness/ident.py` (Arrivées → Résoudre → manual search). **To draw**: the continuation's progress to the library — `GET /api/pipeline/stages` is called by nothing — **L20** |
| **DOIT-6** — des résultats chiffrés pour un run manuel | `features/acquisition` (« Lancer la veille maintenant » in the status sheet) | `partly` | the trigger exists (engine producer, `legacy.js:32395`, moving with **L19**). **To draw**: the run's figures — `GET /api/pipeline/history/{run_uid}` is called by nothing — **L20** |
| **DOIT-7** — une porte de sortie à chaque impasse | `/resolution/$folder` (candidates; zero candidate → pre-filled manual search) | `served` | R57, `harness/ident.py` |
| **DOIT-8** — confirmation avant remplacement d'un film déjà en médiathèque | `/add` (the add screen) | `served, unproved` | the copy exists (`grep -c remplac legacy.js` → 7, in the add flow's producers); no rule walks « add a film the library owns » and reads the confirmation — **L19**, with the add flow's producers |
| **DOIT-9** — pensée pour le téléphone d'abord | every surface | `served` | `harness/states.py` (no horizontal overflow on every named state at 390 px), the oracle at 390 × 844, `a11y.py` `target-size`, R83 |
| **DOIT-10** — retrouvable : chaque détail a son URL, Retour refait le chemin | every screen and addressed panel (`lib/addresses.ts`) | `served` | R69 (`url_state.py`), R82 (`journey.py`), R59 (`back.py`), R75 (`screen_addresses.py`) |
| **DOIT-11** — être consultable : tout média ouvre sa fiche | `/media/$provider/$id`; every poster gallery | `served` | `harness/gallery.py` (tap opens the media sheet on every gallery), R75 |
| **DOIT-12** — montrer l'application de CE compte (§17) | none — one account, one role, `GET /api/auth/me` says nothing of rights | `to draw` | **L18** |
| **DOIT-13** — montrer et piloter le ratio, tracker par tracker (§18) | none — `obligations`, `stalled-grabs`, `downloads` answer and nothing calls them | `to draw` | **L16** |
| **DOIT-14** — rendre le cross-seed visible et décidable (§19) | none — no route in either contract, no event relayed to a surface | `to draw` | **L17** |

## NE-DOIT-PAS

| Clause | Surface | Verdict | Proof / Owner |
| --- | --- | --- | --- |
| **NE-DOIT-PAS-1** — mentir | the connection mark; every state label | `partly` | served: R95 (never « connected » over a dead link), R63. The interface's share of §13 (« l'interface reflète l'état réel ») is one derivation per question — R56's descriptor discipline and `lib/queue.ts`'s single derivation; the data-side proof is `scripts/check-acquisition-coherence.py`, outside the interface |
| **NE-DOIT-PAS-2** — file ou attente invisible | `features/arrivals` | `served` | R66 |
| **NE-DOIT-PAS-3** — 409 / « occupé » face à une action légitime | every mutation | `served, unproved` | the contract carries no 409 for a legitimate action (`frontend/maquette/contract/openapi.json`); no rule drives a busy scenario through the mock and reads the surface — **L19** (same instrument as DOIT-4) |
| **NE-DOIT-PAS-4** — message obscur | every surface | `served` | `scripts/check-no-french.py` (interface text only in `fr.json`, where it is reviewed as copy); R81 (every error surface announces) |
| **NE-DOIT-PAS-5** — échec silencieux | every surface's error phase | `served` | `harness/states.py` (loading and error on every surface), R90 (the error surfaces are one component), R92 (the connection says what is wrong) |
| **NE-DOIT-PAS-6** — détruire sans consentement | `features/library` (single and bulk delete dialogs) | `served` | `harness/selection.py`, R96's sibling holds on the dialog; **the dialog is not on the back ladder (B-229)** — a Back with the dialog up does not consent, it pops the page; **L15** |
| **NE-DOIT-PAS-7** — second mécanisme parallèle | — | `outside the interface` | the interface's share: ONE contract (D7) and one navigation door (R76). The rights model absorbing the read-only role is **L18**'s requirement on existing code |
| **NE-DOIT-PAS-8** — maltraiter les dépendances | — | `outside the interface` | the interface's share: no polling where an event exists — `scripts/check-live-relay.py`'s poll arm, R91 |
| **NE-DOIT-PAS-9** — afficher un média sans chemin vers sa fiche | every poster gallery, every list row naming an identified medium | `served, unproved` | `harness/gallery.py` covers the galleries; no rule walks the LIST rows (a follow row, an arrival row, a search result) — the instrument is **L19**'s, with the producers that draw them |

---

## What this map does NOT read, said so it is not mistaken for complete

- It maps CLAUSES to SURFACES. The numbered sections §1–§19 carry requirements the clauses
  summarise; where a section says more than its clause (§4's « la chaîne va jusqu'à la visibilité
  Plex », §14's junction), that is the backend's and the pipeline's, and the interface's share is
  what the clause says.
- « Served » with a rule named means the rule READS the clause's subject; it does not mean the
  rule cannot be green over something it does not read — B-085's count is 93 for that reason, and
  a row here is exactly as good as the instrument it names.
- The `frontend-backend-demands.md` § 4 list (24 operations the backend has and the interface
  does not use) now has a verdict for each operation a clause names: `stalled-grabs`,
  `obligations`, `downloads` → L16 · `watcher`, `stages`, `history/{run_uid}` → L20 ·
  `config/validate` → served differently (the settings page validates before writing through
  `PUT /api/config/files/{name}`'s own contract; the operation is not the clause). The rest of
  that list is not a clause's and stays where it is.
