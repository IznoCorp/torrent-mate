(function () {
  // The page's own data, read from the element that loaded this file: a file is the same for every
  // visitor, so the place to return to and the reasons v1 may give ride as attributes of its tag.
  var data = document.currentScript.dataset;
  var RETURN_TO = JSON.parse(data.returnTo);
  var REASONS = JSON.parse(data.reasons);
  var form = document.querySelector('#loginform');
  function refused(code) {
    var why = REASONS.indexOf(code) < 0 ? '' : '&why=' + code;
    return '/?refus=1' + why + '&next=' + encodeURIComponent(RETURN_TO);
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!form.checkValidity()) return;
    fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.username.value.trim(), password: form.password.value })
    }).then(function (answer) {
      if (answer.ok) {
        // The application boots from scratch after this page: the mark is how its first boot
        // knows a person has just signed in, and proposes the install (`app/install-state.ts`).
        try { sessionStorage.setItem('tm-signed-in', '1'); } catch (e) {}
        return location.replace(RETURN_TO);
      }
      return answer.json().catch(function () { return {}; })
        .then(function (problem) { location.replace(refused(problem && problem.code)); });
    }).catch(function () { location.replace(refused()); });
  });
})();
