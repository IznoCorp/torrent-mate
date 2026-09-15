// The door through which the signed-in picture reaches the top bar.
//
// The top bar is static markup (`index.html`): its avatar button holds an empty
// `<img>` until someone says whose picture it is. WHO is signed in is the
// account feature's subject and the bar is the frame's, and a feature may not
// reach into the frame's markup by itself — so the frame's half is this one
// verb, and the feature calls it with what the server answered.

/**
 * Shows a picture in the top bar's avatar.
 *
 * A document without the top bar (a page with no frame drawn) is left as it is
 * rather than throwing.
 *
 * @param source The picture's address.
 */
export function showAvatar(source: string): void {
  const image = document.querySelector<HTMLImageElement>(".topbar .avatar img");
  if (image) image.src = source;
}
