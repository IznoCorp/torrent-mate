// The top bar's avatar falls back to the initial when its picture fails to load.
//
// WHAT MAKES THIS NON-VACUOUS. The server answers an ADDRESS, never a promise
// that a picture is there: a Gravatar asked with `d=404` answers no image for an
// e-mail that has none, and plex.tv can be down. Each leg places a picture over
// a stand-in bar, makes the image fail the way the browser does — its `error`
// handler called — and reads what the bar then shows.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { showAvatar } from "./topbar-avatar";

/** One element of the stand-in bar: what `showAvatar` reads and writes. */
type FakeElement = {
  dataset: Record<string, string>;
  style: { display: string };
  textContent: string;
  attributes: Record<string, string>;
  children: FakeElement[];
  src?: string;
  onerror: (() => void) | null;
  [key: string]: unknown;
};

/**
 * An element `showAvatar` can query, fill and listen on.
 *
 * @returns The element.
 */
function element(): FakeElement {
  const made: FakeElement = {
    dataset: {},
    style: { display: "" },
    textContent: "",
    attributes: {},
    children: [],
    onerror: null,
    setAttribute: (name: string, value: string) => {
      made.attributes[name] = value;
      if (name === "src") made.src = value;
    },
    getAttribute: (name: string) => (name === "src" ? made.src ?? null : made.attributes[name] ?? null),
    removeAttribute: (name: string) => {
      if (name === "src") delete made.src;
      delete made.attributes[name];
    },
    append: (child: FakeElement) => {
      made.children.push(child);
    },
    querySelector: (selector: string) => {
      if (selector === "img") return image;
      return made.children.find((child) => selector.includes(child.dataset.part ?? "\u0000")) ?? null;
    },
  };
  return made;
}

let button: FakeElement;
let image: FakeElement;

beforeEach(() => {
  image = element();
  button = element();
  (globalThis as { document?: unknown }).document = {
    querySelector: (selector: string) => (selector === ".topbar .avatar" ? button : null),
    createElement: () => element(),
  };
});

afterEach(() => {
  delete (globalThis as { document?: unknown }).document;
});

/** The initial the bar shows, or null when it shows none. */
function shownInitial(): string | null {
  const initial = button.children.find((child) => child.dataset.part === "avatar/initial");
  if (!initial || initial.style.display === "none") return null;
  return initial.textContent;
}

describe("showAvatar", () => {
  it("shows the picture it is given", () => {
    showAvatar("https://plex.tv/users/abc/avatar", "izno");
    expect(image.src).toBe("https://plex.tv/users/abc/avatar");
    expect(image.style.display).toBe("");
    expect(shownInitial()).toBeNull();
  });

  it("falls back to the initial when the picture fails to load", () => {
    showAvatar("https://www.gravatar.com/avatar/0?d=404&s=128", "lea");
    image.onerror?.();
    expect(image.style.display).toBe("none");
    expect(image.src).toBeUndefined();
    expect(shownInitial()).toBe("L");
  });

  it("does not reload an address that already failed", () => {
    const failed = "https://www.gravatar.com/avatar/0?d=404&s=128";
    showAvatar(failed, "lea");
    image.onerror?.();
    // An account refresh answers the same address again: no new load.
    showAvatar(failed, "lea");
    expect(image.src).toBeUndefined();
    expect(image.style.display).toBe("none");
    expect(shownInitial()).toBe("L");
  });

  it("gives a new address its own chance after one failed", () => {
    showAvatar("https://www.gravatar.com/avatar/0?d=404&s=128", "lea");
    image.onerror?.();
    showAvatar("https://plex.tv/users/abc/avatar", "izno");
    expect(image.src).toBe("https://plex.tv/users/abc/avatar");
    expect(shownInitial()).toBeNull();
  });

  it("draws the initial when there is no picture", () => {
    showAvatar("", "jules");
    expect(image.style.display).toBe("none");
    expect(shownInitial()).toBe("J");
  });
});
