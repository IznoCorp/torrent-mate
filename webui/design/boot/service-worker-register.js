// Registration is best-effort here: R52 measures the worker registered
// AND controlling against the live host, which is the only place a
// worker exists. On a static server (the harness, a preview) there is
// nothing to register, and an unhandled rejection would fail rules
// about other things entirely.
if ("serviceWorker" in navigator)
  addEventListener("load", () =>
    navigator.serviceWorker.register("/sw.js").catch(() => {}),
  );
