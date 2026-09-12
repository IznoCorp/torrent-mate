# maquette-scroll-jump — the in-flight list keeps the reader's place

Register: **B-490** (the jump), **B-491** (the double scroll), **B-492** (filed, not repaired here). Constitution:
§ 12 — a reader who loses their place is the defect the mobile clause names first. A micro-wave beside no lot; it draws
nothing new.

## 1. The report and the two mechanisms

The operator, on his Mac, verbatim:

> « Bug majeur : double scroll systématique sur Acquisition › En cours ; dès que le scroll arrive au niveau de Lucky on
> remonte automatiquement en haut de la page. »

Two facts, measured separately on a private bench (Chrome, a setter trap on `Element.prototype.scrollTop`, 40 px
gestures with a settle after each). They are two mechanisms.

### The jump (B-490) — the restoration's late re-apply

`app/scroll-restoration.ts` `restoreScroll()` restores a page's offset on a history RETURN, then subscribes to the `load`
of every `img` of `#port` not yet complete and, when the last one fires, writes the remembered offset again — to recover
an offset the browser clamped while the list was short. Its only guard was the navigation token. The posters below the
fold are `loading="lazy"`: the last `load` fires when the READER scrolls down to it, and wrote the arrival offset over
the reader's own. Path: `/acquisition` → « Résoudre → » on Lucky → Back → scroll.

Desktop 1440 × 900 in the frame:

```
STEP  12 port=  480
      EVENT {"kind": "img-load", "src": "a406ec1c.webp", "loading": "lazy", "offset": 1280, "portTop": 520, "card": "Wicker"}
      EVENT {"t": 9012, "kind": "scrollTop=", "target": "main#port[data-part=viewport]", "before": 520, "value": 0, "after": 0}
STEP  13 port=    0
```

Phone 390 × 844: `before 520 value 240` (the departure was at 240), same stack, `addEventListener.once`.

Lucky is not special as a card; it is where the detour starts, and the first unloaded posters sit just below it — so the
operator's reading was exact. A fresh arrival, a sheet opened and closed, or no detour: no write at all over 60 steps, the
port monotone to its end (720 phone, 722 desktop in the frame; 557 / 357 / 157 out of the frame at 900 / 1100 / 1300
high), `#port.scrollHeight` constant, `activeElement` the body. Out of the frame at 1440 × 900 every poster loads at
once, so that path cannot jump there. No list re-mount, no height collapse, no focus move: `tm-design`'s `/build.json`
equals its bundle's identity (no update-discipline reload), and `lib/pull-gesture.ts` is armed by a touch or a mouse
DRAG, never by a wheel.

### The double scroll (B-491) — the document out of the frame

Out of the frame (`#desktop-switch` checked) `.device` stops clipping — its `overflow` is the app's own cascade there,
held by R140 against the control document. The closed sheet (`#sheet`, absolute, translated 43 px below the bottom edge)
and its 88 px `sheet/drag-band` end at `innerHeight + 89`, so `document.scrollingElement` measures 989 against 900. A
wheel over `[data-part="shell/header"]` moved the document 0 → 89 with the port at 0; a wheel over the list moved the
port and left the document. In the frame, at either width, `#port` is the only container.

## 2. The repairs

- **B-490, inside the one path.** `restoreScroll()` records `landed = port.scrollTop` right after its write; the late
  re-apply runs only while `port.scrollTop === landed`. A clamped offset has not moved since the write; a reader's has.
  Nothing else moves: the retry budget, the token and R94's promise on a return are unchanged.
- **B-491, in the frame's own stylesheet.** `styles/harness.css` gives `.stage` `overflow-y: clip` beside its existing
  `overflow-x: clip` (the build merges the pair into `overflow: clip`). NOT on `.device`: a probe of that candidate read
  the device's computed `overflow` as `visible clip` out of the frame against `visible` in the control document, which is
  exactly what R140's skin hold refuses. The stage is the window's height and holds nothing below it; fixed harness
  chrome is not clipped by it.

Probe of the three candidates (none / `.stage` / `.device` out of the frame), each in the phone, the desktop in the frame
and the desktop out of it, all at `/acquisition`:

| Candidate | Out of frame: document overflow | Header wheel moves the document | Device `overflow` out of frame | Rects in all three frames |
| --- | --- | --- | --- | --- |
| none | 89 | 0 → 89 | `visible` (= control) | reference |
| `.stage` clip | 0 | stays 0 | `visible` (= control) | identical |
| `.device` clip, out of frame | 0 | stays 0 | `visible clip` (≠ control: R140 falls) | identical |

« Rects » are the device, the stage, the closed sheet and its `translateY(43)`, the drag band and the switch's label. An
opened sheet (`sheet-more`) on the repaired tree, in all three frames: it rises whole (`transform: none`, its own element
at its centre, document overflow 0), and Escape takes it back below the edge (`translateY(316.5)`).

## 3. The rule — R175, `harness/scroll_keeps_place.py`

By finger (CDP `synthesizeScrollGesture`, touch) and by wheel, at the phone width, at 1440 × 900 in the frame (fresh
arrival and return from the resolution) and out of it (fresh arrival and the header):

- **the walk** — a downward gesture repeated to the end of the list, past Lucky's card: the port never goes back up,
  not even after the last poster has loaded;
- **one container** — every gesture moves at most one scroll container, and it is `#port`;
- **the header** — a gesture over the shell's header moves no container, and the document has nothing to scroll;
- **the detour** — the return really went through the restoration with posters still to load, so the walk's holds
  cannot pass over a path that cannot jump.

It sits in the full suite, not in the contracts tier: it reads a behaviour, not a name.

| Tree | Holds | Violations | Which |
| --- | --- | --- | --- |
| unrepaired | 40 | 6 | the four return walks (phone finger 490 → 22, phone wheel 480 → 0, desktop finger 491 → 15, desktop wheel 480 → 0) and the two out-of-frame header holds (`moved ['document']`, 89 px) |
| B-490 repaired | 40 | 2 | the two header holds — B-491 alone |
| both repaired | 40 | 0 | — |
| mutation: `&& port.scrollTop === landed` removed | 40 | 4 | exactly the four return walks (498 → 23, 480 → 0, 499 → 24, 480 → 0); the header holds stay green |

R140 (`desktop_frame.py`) on the repaired tree: 24 holds, 0 violations.

## 4. The confirmatory probe

The repaired tree, a return from the resolution, the port wheeled to Lucky's card and parked there for 30 s with the
relay quiet, a setter trap armed: phone `280 → 280`, desktop in the frame `280 → 280`, no `scrollTop` write, two posters
still loading.

## 5. Filed, not repaired

**B-492** — out of the frame the overflow is the app's own cascade (the shell's absolute layers are not clipped by any
element of the app), so after switchover, when `harness.css` ships nowhere, a desktop document can regain its second
scroll. It belongs to the frame model (L13), not to this micro-wave.

## 6. The gate

Written once, on the final head.
