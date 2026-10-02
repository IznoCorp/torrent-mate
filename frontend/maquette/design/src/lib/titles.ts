// A title's own words — what a medium's name reads as once the year a library
// appended to it is set aside.
//
// PURE, AND SHARED: the cards, the media screen, the release screens and the
// verbs all compare or abbreviate a title the same way, and a feature may not
// import another (invariant 7).

/**
 * The title without the year suffix some library titles carry, sometimes
 * doubled (« Silo (2023) (2023) »). It is not a word of the title: neither the
 * initials nor a comparison between two titles should see it.
 *
 * @param title The title.
 * @returns The title, its year suffixes removed.
 */
export function baseTitle(title: string): string {
  return String(title)
    .replace(/\s*\((?:19|20)\d{2}\)\s*/g, " ")
    .trim();
}

/**
 * The follow a medium's title names, among the followed titles — THE ONE
 * READING of « is it followed » (B-676).
 *
 * A follow is recorded under a title without its year (« Silo » follows
 * « Silo (2023) »), so the two are compared by their base. The media sheet's
 * header, its « Informations » row and the library's delete dialog each had
 * their own test — the base title, the exact title, the exact title or an
 * incomplete show — and they disagreed on one screen: the dialog said « est
 * suivi » of a show nobody followed, and the sheet said « inactif ». Being
 * incomplete is not being followed: Incomplets offers its own « suivre ».
 *
 * @param followedTitles The titles of the follows.
 * @param title The medium's title.
 * @returns The follow's own title, or undefined when nothing follows it.
 */
export function followedAs(followedTitles: readonly string[], title: string): string | undefined {
  const base = baseTitle(title);
  return followedTitles.find((one) => baseTitle(one) === base);
}

/**
 * The first letters of the title's first two words, uppercased — what a poster
 * with no picture shows.
 *
 * @param title The title.
 * @returns One or two letters.
 */
export function initials(title: string): string {
  const words = baseTitle(title).split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "") + (words.length > 1 ? (words[1]?.[0] ?? "") : "")).toUpperCase();
}
