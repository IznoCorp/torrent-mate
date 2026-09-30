# Product intent → surface map

**What this file is.** `docs/reference/product-intent.md` is the constitution: it says what the
product must BE, in fourteen DOIT clauses and nine NE-DOIT-PAS clauses. Nothing in this repository
read it against the interface until 2026-08-29 (B-142): three instruments compare the interface to
what already exists, and a capability the constitution requires that neither the maquette nor the
backend has was invisible to every gate — which is how three dictated sections went a month
unnoticed. This file is the **declared mapping** that instrument needs: one row per clause, the
surface that serves it, a verdict, and — where the verdict is « to draw » — the lot that owes it.

**A mapping is a design decision, not a grep.** It was written by L10-ter clause by clause against
the tree, never seeded from what exists: three rows say `to draw` and five more carry a « to draw »
half inside `partly`, and a row that says `served` names the proof that says so. **A review of the
first version found two `served` rows resting on a print statement and on a rule about PM2
processes** — the arm cannot see that, only a reader can, so every amendment of this file is read
against the proof it names. **The operator amends this file; an agent proposes** — and **ratified it as written on 2026-08-30** (Q7), with the §20 re-reading applied in the same pull request. The arm that
reads it is specified in `docs/reference/frame-model.md` § 4 and built by L15.

**The vocabulary of the `Verdict` column**, and the arm refuses any other word:

| Verdict | Means |
| --- | --- |
| `served` | a surface in the tree serves the clause, and the `Proof` column names the rule or guard that reads it |
| `served, unproved` | the surface exists, no instrument reads the clause; the `Proof` column names the lot that owes the instrument |
| `partly` | one half served with its proof, the other half `to draw` or unproved — both named in the row, and the owed half names its lot |
| `to draw` | no surface serves it; the `Owner` column names the lot |
| `outside the interface` | the clause binds the backend or the method, not a surface; the row says what the interface's share is |

Surfaces are named by **route path** (as `routes/*` declares them) or by **feature directory**
(`features/<domain>/`), never by a component name — a component moves, an address and a domain do
not.

---

## DOIT

| Clause | Surface | Verdict | Proof / Owner |
| --- | --- | --- | --- |
| **DOIT-1** — « tout montrer, en français clair » | `features/acquisition` (each arrival as a card: its state on the one ladder and its journey sheet; per-film and per-episode states), `features/library` | `partly` | served for the drawn pages: R207 (`harness/one_ladder.py`, one ladder read by the card and the journey sheet), R63 (a card says what the engine knows) — **R63 reads the operator's live databases** (`content.py:35`), holds on that machine only; R66 (`arrivals.py`) died with the Arrivées page (`6645c23d8`) and sit outside the contracts tier; `scripts/check-no-french.py` proves WHERE the copy lives (`fr.json`), never that it is clear — no instrument reads clarity. **To draw**: the pipeline's own states — per media, in the tunnel (§20): the journey sheet and the Arrivées' producers — **L24**. **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **DOIT-2** — « montrer ce qui ne se passe pas, et pourquoi » | `features/acquisition` (« À traiter »: what waits on the operator's hand, each with its reason; waiting, searching) | `partly` | served: R209 (`harness/todo_holds.py`, « À traiter » holds only what the hand unblocks), R208 (`harness/card_without_identity.py`, the reason in full), R57 (a decision, with its candidates). **To draw**: a torrent deferred for ratio or space — `GET /api/acquisition/stalled-grabs` and `/obligations` are called by nothing — **L16** (§18). **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **DOIT-3** — « agir là où l'on observe » | `features/system` (the pipeline's levers: pause, resume — « Lancer » / « Arrêter » died with Arrivées' bar, OPEN 6) and `/system` (the runs it produced) | `partly` | served: R240 (`harness/levers_stay_live.py`, Système's levers move with the server's events — the live rule the pilot's bar carried). Acting from the tunnel one is looking at is SERVED: « Remettre en file » and « Re-scraper » on the journey sheet — R126 (`harness/journey_verbs.py`, 16 holds, B-302) — and « Récupérer cette saison » on the seasons panel, calling `follows/{followedId}/seasons/{season}/grab` — R125 (`harness/season_grab.py`, 16 holds, B-301). **Served, L20**: the levers' own half — the automatic watcher trigger and the pipeline's pause / resume — R178, R179 (the parallelism bound stays a backend demand, unset — `docs/reference/backend-demands-architecture.md`). **To draw**: the tracker policy set from the ratio surface — **L16**. **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **DOIT-4** — « toujours accepter une action légitime, mise en file visible » | `features/system` (a pass asked for while one runs is queued and says so: Système's `levers-queued`); the resolve queue; under §20, an arrival that meets the parallelism bound | `served` | served for the pipeline pass: R178–R181 (`harness/levers.py`, the levers act and are never refused; the queued pass is `levers-queued`), and for the ACCEPTANCE half of every other mutation: **R124** (`harness/busy.py`, L19). The « En file » pastille is DRAWN: `data-part="season/queued"`, on BOTH season surfaces, held in the cache by `features/media/queued-seasons.ts` — **R138** (`harness/queued_ask_mark.py`, 7 holds unchanged), which reads the mark AFTER the message has gone, because a sentence shown for four seconds tells the operator who was looking and nobody else. Mutated: removing the mark makes two holds fall with « 0 mark(s) ». **Closed by L20 (B-371, R185)**: the pastille is now reachable BY HAND — a maintenance command started from Maintenance holds the lock, then a season is asked, and the mark is present; `harness/queued_by_hand.py` walks the whole path with no `__go` between. **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **DOIT-5** — « aller au bout et le montrer » | `features/acquisition` (the journey sheet, opened from the card), `/resolution/$folder` | `partly` | served: R57, `harness/ident.py` (the card → Résoudre → manual search). **To draw**: the continuation's progress to the library — per media, in the tunnel (§20), `GET /api/pipeline/stages` is called by nothing — **L24**; the journeys as a whole — `GET /api/acquisition/journeys` is uncalled, only the single journey is — **L24**. **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **DOIT-6** — « des résultats chiffrés pour un run manuel » | `features/acquisition` (« Lancer la veille maintenant » in the status sheet), `/system` (a passage's own screen) | `served` | the trigger exists (engine producer, `legacy.js:32395`, moved with **L19**). **Served by L20, by TWO operations, each with its own run's numbers**: `POST /api/acquisition/detect` (the veille: detected / available / grabbed — R180, `harness/watch_run.py`) and `GET /api/pipeline/history/{run_uid}` (a pipeline run: per-step counts and reasons in the history's detail, the raw lines folded and never the default view — R182 `harness/run_history.py`, R183 `harness/raw_log.py`, B-296). Drawn at `docs/features/maquette-l20/DESIGN.md@60c6d9b1d` |
| **DOIT-7** — « une porte de sortie à chaque impasse » | `/resolution/$folder` (candidates; zero candidate → pre-filled manual search) | `partly` | served: R57, `harness/ident.py`. **Unproved**: the step that CREATES a decision with its candidates — `POST /api/staging/media/{id}/enqueue`, §3's invariant and `§méthode`'s own first guard test — and `GET /api/decisions/activity` are called by nothing in the maquette; **L24**, with the arrivals producers |
| **DOIT-8** — « confirmation avant remplacement d'un film déjà en médiathèque » | `/add` (the add screen) | `served` | **R121** (`harness/replacement.py`, L19): the panel announces the replacement BEFORE the act is tapped, the act raises a DIALOG rather than a message after the fact, cancelling leaves the medium unadded, and a medium the library does NOT own is added with no dialog at all — that last half is not thoroughness: a rule reading only the owned case passes a build that asks « are you sure? » about everything. Which result is owned is read from the layer's own answer, never named in the rule |
| **DOIT-9** — « pensée pour le téléphone d'abord » | every surface | `partly` | served for geometry: `harness/states.py` (no horizontal overflow on every named state at 390 px), the oracle at 390 × 844, `a11y.py` `target-size`, R83. **Unproved**: §12's engraved card composition (title alone on line 1) is read on the follows tab only, by a print in an unnumbered script (`harness/follows.py:24`) — a numbered rule over every card, **L24**. R-L16bis-d (`harness/trackers_card.py`) reads a torrent card's name WHOLE at 390 px, never cut. |
| **DOIT-10** — « retrouvable : chaque détail a son URL, Retour refait le chemin » | every screen and addressed panel (`lib/addresses.ts`) | `served` | R69 (`url_state.py`), R82 (`journey.py`), R-navigation-a and R-navigation-b (`journey.py`), R59 (`back.py`), R75 (`screen_addresses.py`) |
| **DOIT-11** — « être consultable : tout média ouvre sa fiche » | `/media/$provider/$id`; the poster galleries | `partly` | served for the PATH, on the five galleries `harness/gallery.py` names (`lib-grid`, `lib-incomplete`, `lib-recent`, `acq-follows-grid`, `discover-posters`), and R75 for the address. **Unproved**: the sheet's CONTENT — nothing reads title, year, synopsis, director, trailer. **To draw**: « complétude par saison » — `GET /api/acquisition/followed/{id}/completeness` is called by nothing, and §9 makes that read-model THE definition of « acquis » — **L24** |
| **DOIT-12** — « montrer l'application de CE compte (§17) » | none — one account, one role, `GET /api/auth/me` says nothing of rights | `to draw` | **L18** — §17's roles, options, requester and SSO were dictated on 2026-08-30; the lot is unblocked |
| **DOIT-13** — « montrer et piloter le ratio, tracker par tracker (§18) » | none — `obligations`, `stalled-grabs`, `downloads` answer and nothing calls them | `to draw` | **L16** |
| **DOIT-14** — « rendre le cross-seed visible et décidable (§19) » | none — no route in either contract, no event relayed to a surface | `to draw` | **L17** |

## NE-DOIT-PAS

| Clause | Surface | Verdict | Proof / Owner |
| --- | --- | --- | --- |
| **NE-DOIT-PAS-1** — « mentir » | the connection mark; every state label | `partly` | served: R95 (never « connected » over a dead link), R63 (live-database bound). The interface's share of §13 (« l'interface reflète l'état réel ») is one derivation per question — R56's descriptor discipline and `lib/queue.ts`'s single derivation, which is LOCAL: the executable completeness the backend answers (`completeness`) is uncalled, see DOIT-11 — **L24**; the data-side proof is `scripts/check-acquisition-coherence.py`, outside the interface. **§13, one more instance, L20**: the levers' own bound, lock and trigger print NO value while their read is in flight rather than a fabricated one — `harness/levers.py` (**R181**) — `served, unproved`: no mutation of R181's own is on record for this hold (`REPORT.md` §2, `@60c6d9b1d`); the fall is a reader's own (r1-C.md C04), not the wave's |
| **NE-DOIT-PAS-2** — « file ou attente invisible » | `features/acquisition` (« En cours », queue included; « À traiter ») and `features/system` (the locks block) | `served` | R184 (`harness/locks.py`, what holds the pipeline is drawn, with its age), R185 (`harness/queued_by_hand.py`); R66 (`arrivals.py`, live-database bound) died with the Arrivées page; `GET /api/maintenance/locks`, the operation that says WHO holds the lock behind « En file — pipeline en cours », is uncalled — **L19**. **2026-09-15**: the surface moves to Acquisition at L22 (auditor's lot-order delegation); verdict unchanged until it lands |
| **NE-DOIT-PAS-3** — « 409 / « occupé » face à une action légitime » | every mutation | `served` | R178–R181 for the pipeline pass (`harness/levers.py`, the levers are never refused), and **R124** (`harness/busy.py`, L19) for the others: with the pipeline put to work over a state that has media waiting, a medium is TAKEN and a follow is PAUSED, each read on the STATE and never on a message; nothing is answered 409 — read on the NETWORK, because that is where the refusal would arrive and a rule reading only the screen would pass a build that swallowed one; and nothing anywhere says the machine is busy |
| **NE-DOIT-PAS-4** — « message obscur » | every surface | `served, unproved` | **no instrument reads obscurity.** `scripts/check-no-french.py` proves WHERE the copy lives (`fr.json`, reviewed as copy by a human); R81 proves an error surface ANNOUNCES. The clause is held by review of `fr.json`, and this row says so rather than naming a location guard as a clarity proof. R-L16bis-h (`harness/trackers_switch.py`) reads a tracker's refused re-activation said in the engine's words under its row, never a code alone |
| **NE-DOIT-PAS-5** — « échec silencieux » | every surface's error phase | `served` | `harness/states.py` (loading and error on every DECLARED state — a surface that declares no error state is invisible to it), R90 (the error surfaces are one component), R92 (the connection says what is wrong), R-L16bis-h (`harness/trackers_switch.py`: a refused re-activation is a state under the row, never a toast that leaves) |
| **NE-DOIT-PAS-6** — « détruire sans consentement » | `features/library` (single and bulk delete dialogs) | `partly` | served: `harness/audit2.py:239` (« deleting a medium: no confirmation » — the one hold that reads `#dlg[data-open]`); `harness/selection.py` only PRINTS the dialog's title and choices and asserts that the sheet opens — an instrument **L24** owes with the dialog's conversion. **Owed**: the dialog's back rung (B-229) and its z-order (B-237) — **L24**. The « identité par provider-ID » half is §7's, the backend's; the interface's share is DOIT-8's confirmation |
| **NE-DOIT-PAS-7** — « second mécanisme parallèle » | — | `outside the interface` | the clause's subject is the pipeline lock and the runner. The interface's share: a resolve continues through the existing runner (`POST /api/staging/media/{id}/continue`) and never through a second path — read by no rule, **L19** with the arrivals producers; and the rights model absorbing the read-only role, **L18**'s requirement on existing code |
| **NE-DOIT-PAS-8** — « maltraiter les dépendances » | — | `outside the interface` | the interface's share today: no polling where an event exists — `scripts/check-live-relay.py`'s poll arm, R91. **And a share L17 owes**: §19-4 names this clause « la limite dure », opposable to any more aggressive cross-seed automation the surface might offer — L17's design honours it |
| **NE-DOIT-PAS-9** — « afficher un média sans chemin vers sa fiche » | every poster gallery, every list row naming an identified medium | `served` | the five galleries `harness/gallery.py` names, and **R122** (`harness/paths_to_sheets.py`, L19) for the LIST rows and the galleries outside them: six surfaces — a follow row listed and grouped, an acquisition in flight, an arrival, a library row, a search result — each with a floor, because a state that draws nothing has no dead end either. **A path is three things**, since the interface spells reachability three ways (`data-mediasheet`, `data-panel` — the long press raises the panel that carries the act — and the frame's navigation); refusing the second would refuse the interface's own gesture vocabulary. A row wearing `data-nonmedia` is excluded: an arrival still a folder nobody has identified names no medium, and demanding a path to a sheet that does not exist is the same broken promise read from the other side |

---

## What this map does NOT read, said so it is not mistaken for complete

- It maps CLAUSES to SURFACES. The numbered sections §1–§19 carry requirements the clauses
  summarise; where a section says more than its clause (§4's « la chaîne va jusqu'à la visibilité
  Plex », §14's junction), that is the backend's and the pipeline's, and the interface's share is
  what the clause says.
- « Served » with a rule named means the rule READS the clause's subject; it does not mean the
  rule cannot be green over something it does not read — B-085's count is 98 for that reason, and
  a row here is exactly as good as the instrument it names. Three of the proofs (R66, R63) read the
  operator's live databases and hold on that machine only.
- The `frontend-backend-demands.md` § 4 list (24 operations the backend has and the interface
  does not use — COMPUTED by `compare-contracts.py`, so the verdicts live here and not there) has a
  verdict for each operation a clause names: `stalled-grabs`, `obligations`, `downloads` → L16 ·
  `watcher`, `history/{run_uid}` → L20, with `acquisition/detect` (DOIT-6's figures — the veille, not the
  watcher, ruled 2026-09-12) · `stages` → the TUNNEL, per media on the card (operator, 2026-09-12: « le
  pipeline se voit aussi sur la carte d'un média en cours ») — L19's family, and a backend demand for a
  per-media form · `staging/media/{id}/enqueue` and
  `decisions/activity` → DOIT-7, L19 · `followed/{id}/completeness` → DOIT-11 / §9, L19 ·
  `journeys`, `journeys/{hash}/requeue`, `journeys/{hash}/rescrape` → DOIT-3 / DOIT-5, L19 ·
  `follows/{id}/seasons/{season}/grab` → §5 (season by season), L19 · `maintenance/locks` →
  DOIT-4 / §6, L19 · `config/validate` → served differently (the settings page validates before
  writing through `PUT /api/config/files/{name}`'s own contract; the operation is not the clause).
  **The remainder** (`lookup`, `overview`, `wanted`, `config/files/{name}`, `decisions/{id}`,
  `health`, `registry/status`, `staging/media/{id}/poster`, `ranking/preview`) **is not yet read
  against the clauses** — said so rather than declared clause-less.
