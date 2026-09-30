# L23 OPEN questions — round 11 rulings (to carry into docs/features/maquette-l23/DESIGN.md, one dated line each, in the next docs PR)
- OPEN 1 = A (27/09 17:4x): only a torrent ACTIVE in qBittorrent, complete and seeding, from its row in « Torrents ». B (from the library) may come later.
- OPEN 2 = B (27/09 18:0x): each tracker has an « accepte les uploads » switch, distinct from the cross-seed switch, in Réglages and on the tracker's entry (one write, two doors); state tracker-upload-disabled becomes real.
- OPEN 3 = A (27/09 18:0x): the interface pre-validates nothing; the backend applies the tracker's publication rules and returns a reasoned refusal, read on the torrent's row.
- OPEN 4 = A (27/09 18:1x; operator typed « TA », confirmed A): only the torrent's row remains, « erreur de cross-seed » with the refusal's reason, counted in the badge while in error; no counter on the tracker; state 8 stays proposed.
- OPEN 5 = B (27/09 18:1x): the ratio is computed like any torrent's, on its size; the origin mark gains a THIRD value « publié par vous » beside « téléchargé ici » and « cross-seed » — L23 lays it, L16's DESIGN gets a dated line.
- ROUND 11 COMPLETE 5/5. Carry into the next docs PR: L23 DESIGN (5 dated lines), L16 DESIGN (1 dated line for OPEN 5), operator-method.md byte-identical from the main checkout.
