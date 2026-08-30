// The icon paths the FRAME draws with, and the reason they live here.
//
// They were the dying engine's — one `icons` object beside the code that drew
// the tab bar and the drawer from it. The frame has to outlive that engine, so
// what the frame draws with moves out FIRST and the engine imports it back:
// one copy of every path, read by both worlds, and the day the engine goes this
// file loses an importer rather than a subject.
//
// NOT in `ui/`, and it is invariant 10 that decides. `ui/` carries the
// component vocabulary and its domain-word ceiling is ZERO — an icon called
// `library` is one word over it. `app/` is where the frame names its pages, and
// naming them is exactly what the navigation table's seven exist for; the rest
// came with them rather than be split across two files by lifetime.
//
// The shape is the one `svgIcon(paths)` and `<Icon paths={…} />` both take: the
// CONTENTS of a 24×24 `<svg>`, no wrapper. Adding a wrapper here would break
// both readers at once.

/** Every icon the interface draws, by the name its callers use. */
export const icons = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    more: '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
    group: '<path d="M3 5h18M3 12h12M3 19h7"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    folder:
      '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    radar:
      '<path d="M19.07 4.93A10 10 0 1 1 4.93 19.07"/><path d="M12 12 8 8"/><circle cx="12" cy="12" r="4"/>',
    library: '<path d="M4 4h4v16H4zM10 4h4v16h-4z"/><path d="m17 5 3 15"/>',
    inbox:
      '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5 5h14l3 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
    wrench:
      '<path d="M14.7 6.3a4 4 0 0 0 5 5L21 21H10L8.5 12.5a4 4 0 0 1-5-5z"/>',
    left: '<path d="m15 18-6-6 6-6"/>',
    right: '<path d="m9 18 6-6-6-6"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
    sort: '<path d="M11 5h10M11 12h7M11 19h4M3 8l3-3 3 3M6 5v14"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    play: '<path d="m6 4 14 8-14 8z"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    star: '<path d="m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z"/>',
    film: '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M7 3v18M17 3v18M2 9h5M2 15h5M17 9h5M17 15h5"/>',
    tv: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="m17 2-5 5-5-5"/>',
    clap: '<path d="M3 8h18v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="m3 8 2-5 16 2-2 3"/><path d="m8 3 1.5 4M14 4l1.5 4"/>',
    cards:
      '<rect x="3" y="7" width="13" height="14" rx="2"/><path d="M8 3h10a2 2 0 0 1 2 2v10"/>',
    user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    logout:
      '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    ext: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    refresh:
      '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
} as const;
