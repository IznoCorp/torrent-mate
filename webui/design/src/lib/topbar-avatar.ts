// The door through which the signed-in picture reaches the top bar.
//
// The top bar is static markup (`index.html`): its avatar button holds an empty
// `<img>` until someone says whose picture it is. WHO is signed in is the
// account feature's subject and the bar is the frame's, and a feature may not
// reach into the frame's markup by itself — so the frame's half is this one
// verb, and the feature calls it with what the server answered.

/**
 * Shows the signed-in account in the top bar's avatar: its picture, or — for
 * an account that has none, or whose picture fails to load — its initial,
 * never another account's picture.
 *
 * A document without the top bar (a page with no frame drawn) is left as it is
 * rather than throwing.
 *
 * @param source The picture's address, or the empty string when there is none.
 * @param name The account's name, whose initial stands in for a picture.
 */
export function showAvatar(source: string, name: string): void {
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
  image.style.display = source ? "" : "none";
  if (source) image.src = source;
  else image.removeAttribute("src");
  // A PICTURE THAT DOES NOT LOAD IS NO PICTURE: the server answers an address,
  // and a Gravatar asked with `d=404` answers no image for an e-mail that has
  // none, or plex.tv is down. The initial takes its place — unless the image
  // has been given another address since, whose own load decides.
  image.onerror = source
    ? () => {
        if (image.getAttribute("src") === source) showAvatar("", name);
      }
    : null;
  if (!initial) return;
  initial.style.display = source ? "none" : "";
  initial.textContent = source ? "" : name.trim().slice(0, 1).toLocaleUpperCase();
}
