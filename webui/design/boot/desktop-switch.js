// THE CHOICE IS REMEMBERED. A reload used to put the operator back inside
// the phone every time he had left it; the choice is a preference now,
// kept in `localStorage` the way the appearance is, and restored HERE —
// inline, right after the control, so the box is already checked when the
// document is parsed and before any module runs. The key is the harness's:
// no module of the app reads it, and it goes when the frame goes.
//
// AND ONLY WHERE THE CONTROL IS DRAWN. Where the frame is not drawn the
// control is `display: none` and there is nothing to leave — but a checked
// box would still take `overflow: clip` off the device, which the frame
// declares outside any breakpoint. So a narrow window neither applies the
// choice nor forgets it. Whether the control is drawn is asked of the
// stylesheet, never typed a second time here: the build links it in the
// head, and a script waits for a pending stylesheet before it runs.
(function () {
  var key = "tm-desktop-switch";
  var control = document.getElementById("desktop-switch");
  try {
    if (
      localStorage.getItem(key) === "out-of-the-frame" &&
      getComputedStyle(control.parentElement).display !== "none"
    )
      control.checked = true;
  } catch (error) {}
  control.addEventListener("change", function () {
    try {
      if (control.checked) localStorage.setItem(key, "out-of-the-frame");
      else localStorage.removeItem(key);
    } catch (error) {}
  });
})();
