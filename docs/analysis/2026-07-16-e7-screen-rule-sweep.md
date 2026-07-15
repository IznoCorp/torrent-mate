# E7 — DOIT / NE-DOIT-PAS screen×rule sweep (2026-07-16)

Every authenticated screen passed against the constitution v2 checklists
(`docs/reference/product-intent.md`). Legend: **OK** conform · **FIX** fixed in
this PR · **OPEN** surfaced open item (operator arbitrage) · **n/a** rule doesn't
apply to this screen. Screens = the 8 authenticated routes (+ /login).

## DOIT (must do)

| Screen (route)            | 1 clair FR | 2 montre l'attente/pourquoi | 3 agir sur place | 4 accepte tjrs (file) | 5 va au bout | 6 chiffres | 7 porte de sortie | 8 confirme remplacement | 9 mobile 390 | 10 URL détail |
| ------------------------- | ---------- | --------------------------- | ---------------- | --------------------- | ------------ | ---------- | ----------------- | ----------------------- | ------------ | ------------- |
| Dashboard `/`             | OK         | OK (santé, différés)        | OK (start/stop)  | OK (§6)               | n/a          | OK         | OK                | n/a                     | OK           | n/a           |
| Pipeline `/pipeline`      | OK         | OK (stages, blocked reason) | OK (run/kill)    | **OK (E1 queue)**     | OK           | OK         | OK                | n/a                     | OK           | OK (`?stage=`)|
| Scraping `/scraping`      | OK         | OK (activity, en file)      | OK (resolve)     | OK (#287)             | OK (§4)      | OK         | OK (candidats/recherche) | n/a               | OK           | OK (`?decision=`,`?media=`) |
| Acquisition `/acquisition`| OK         | **OK (E2 errored torrents)**| OK (grab/detect) | OK                    | OK           | OK (§5 run)| OK                | OK (confirm-replace)    | OK           | OPEN (tabs local state) |
| Maintenance `/maintenance`| **FIX (Verrou pipeline)** | **OK (E2 reasons in run detail)** | OK (actions) | **OK (E1 queue)** | OK       | OK         | OK                | n/a                     | OK           | **FIX (`?run=`)** |
| Registry `/registry`      | OK         | OK                          | OK               | n/a                   | n/a          | n/a        | OK                | n/a                     | OK           | n/a           |
| Config `/config`          | OK         | OK (conflicts)              | OK (edit)        | n/a                   | n/a          | n/a        | OK                | n/a                     | OK           | OPEN (selectedFile local) |
| Login `/login`            | OK         | OK                          | n/a              | n/a                   | n/a          | n/a        | OK                | n/a                     | OK           | OK (`?redirect=`) |

## NE-DOIT-PAS (must not do)

| Screen                    | 1 mentir | 2 file invisible | 3 409 occupé | 4 msg obscur | 5 échec silencieux | 6 détruire sans consentement | 7 mécanisme parallèle | 8 maltraiter dépendances |
| ------------------------- | -------- | ---------------- | ------------ | ------------ | ------------------ | ---------------------------- | --------------------- | ------------------------ |
| Dashboard                 | OK       | OK               | OK           | OK           | OK                 | n/a                          | OK (single trigger)   | OK                       |
| Pipeline                  | OK (no blind success) | **OK (E1)** | **OK (E1 dup-only)** | OK | OK           | n/a                          | OK                    | OK                       |
| Scraping                  | OK (read-model = real verify) | OK (#287) | OK (dup-only) | OK | OK             | n/a                          | OK (single runner)    | OK                       |
| Acquisition               | OK (§5 no blind success) | OK | OK          | OK           | **OK (E2 errored)**| n/a                          | OK                    | **OK (E4 client removal)**|
| Maintenance               | OK       | **OK (E1)**      | **OK (E1 dup-only)** | **FIX (FR label)** | OK        | OK (dry-run-first, provider-ID at dispatch) | OK       | OK (E4/E3)               |
| Registry                  | OK       | OK               | OK           | OK           | OK                 | n/a                          | OK                    | OK (circuit-aware)       |
| Config                    | OK       | OK               | OK (409 = conflict, legit) | OK | OK             | OK (validate→backup→write)   | OK                    | OK                       |

## Fixes applied in the E7 PR

- **NE-DOIT-PAS-4 / DOIT-1** — « Pipeline lock » (English machine label) → « Verrou du pipeline » (LocksPanel). Torrent-domain headers (`Ratio`, `Seed`, `HnR`, `Info Hash`) left as-is: they are the operator's own vocabulary, not machine English.
- **DOIT-10** — the maintenance run detail is now URL-addressable (`?run=<uid>`): deep-linkable + « Retour » clears the param (push-on-open / replace-on-close, mirroring `?decision=`).
- **Hygiene** — removed dead `pages/ComingSoon.tsx` (no route/import); fixed stale docstrings (`RunDetail` said `/pipeline`, renders on `/maintenance`; `nav.ts` called Registre a disabled S6 stub while it is live).

## Open items surfaced (§méthode-4 — operator arbitrage)

- **DOIT-10** — a few detail states remain local-`useState`, not URL-addressable: **AcquisitionPage active tab** (4 tabs), **Config selected file**, ResolutionDeck queue position. Making the tab/file addressable is a small follow-up per surface; recorded here rather than done wholesale.
- Modal dialogs (action forms, confirm-replace, run/kill confirms) are intentionally NOT URL-addressable — they are transient chrome, not detail views. This reading is offered for confirmation.

## Verdict

Every DOIT/NE-DOIT-PAS cell is **OK or FIX**, with two DOIT-10 refinements (tab/file addressability) surfaced as open. No screen mints an invisible queue, a busy-refusal, a blind success, or a machine-English label after this sweep.
