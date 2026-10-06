// Signing in navigates to a document of several megabytes; until its first frame is
// painted the browser still shows the sign-in page, so the wait belongs here: the
// startup screen (extracted from the shell like the rest of the gate) takes over at
// the submit, instead of a tap that answers nothing. Served as a file, never inline:
// the page runs under a Content-Security-Policy without `'unsafe-inline'`.
document.querySelector('#loginform').addEventListener('submit', function (e) {
  if (!e.currentTarget.checkValidity()) return;
  document.querySelector('#login').hidden = true;
  document.querySelector('#splash').hidden = false;
});
