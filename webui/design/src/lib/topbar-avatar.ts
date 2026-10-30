// The door through which the signed-in picture reaches the top bar.
//
// The top bar is static markup (`index.html`): its avatar button holds an empty
// `<img>` until someone says whose picture it is. WHO is signed in is the
// account feature's subject and the bar is the frame's, and a feature may not
// reach into the frame's markup by itself — so the frame's half is this one
// verb, and the feature calls it with what the server answered.

// THE ADDRESS THAT FAILED, remembered across calls: the account's cache event
// calls `showAvatar` again on every refresh with the same address, and a
// picture that did not load would otherwise be asked for again each time — a
// flicker for an account with no Gravatar. A different address clears it.
let failedSource: string | null = null;

/**
 * Shows the signed-in account in the top bar's avatar: its picture, or — for
 * an account that has none, or whose picture fails to load — its initial,
 * never another account's picture.
 *
 * An address that already failed to load is not asked for again until the
 * account answers another one.
 *
 * A document without the top bar (a page with no frame drawn) is left as it is
 * rather than throwing.
 *
 * @param source The picture's address, or the empty string when there is none.
 * @param name The account's name, whose initial stands in for a picture.
 */
export function showAvatar(source: string, name: string): void {
  if (source && source === failedSource) source = "";
  else if (source) failedSource = null;
  const button = document.querySelector<HTMLElement>(".topbar .avatar");
  const image = button?.querySelector<HTMLImageElement>("img");
  if (!button || !image) return;
  let initial = button.querySelector<HTMLElement>('[data-part="avatar/initial"]');
  // THE INITIAL IS ADDED ONLY WHEN IT IS NEEDED: the owner's bar keeps the
  // markup it was drawn with.
  if (!initial && !source) {
    initial = document.createElement("span");
    initial.dataset.part = "avatar/initial";
    initial.setAttribute("aria-hidden", "true");
    button.append(initial);
  }
  // `style.display` rather than `hidden`: the image's own `block` class would
  // outrank the attribute's user-agent rule.
  // NO REFERER TO THIRD PARTIES: plex.tv and gravatar.com serve the picture
  // and have no business learning the address of this app.
  image.referrerPolicy = "no-referrer";
  image.style.display = source ? "" : "none";
  if (source) image.src = source;
  else image.removeAttribute("src");
  // A PICTURE THAT DOES NOT LOAD IS NO PICTURE: the server answers an address,
  // and a Gravatar asked with `d=404` answers no image for an e-mail that has
  // none, or plex.tv is down. The initial takes its place, and the address is
  // remembered so the next refresh does not ask for it again. The handler is
  // replaced on every call, so only the current address's load can fire it.
  image.onerror = source
    ? () => {
        failedSource = source;
        showAvatar("", name);
      }
    : null;
  if (!initial) return;
  initial.style.display = source ? "none" : "";
  initial.textContent = source ? "" : name.trim().slice(0, 1).toLocaleUpperCase();
}
