(function () {
  // Mobiel menu
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('open', !open);
    });
  }

  // Formulieren: tijdstempel tegen spam-bots, knop blokkeren tijdens verzenden, foutmelding tonen
  var params = new URLSearchParams(location.search);
  document.querySelectorAll('form.js-form').forEach(function (form) {
    var ts = form.querySelector('input[name="ts"]');
    if (ts) ts.value = String(Math.floor(Date.now() / 1000));
    var url = form.querySelector('input[name="page"]');
    if (url) url.value = location.pathname;

    if (params.get('fout')) {
      var msg = document.createElement('div');
      msg.className = 'form-msg err';
      msg.setAttribute('role', 'alert');
      msg.textContent = params.get('fout') === 'velden'
        ? 'Niet alle verplichte velden zijn (goed) ingevuld. Controleer het formulier en probeer het opnieuw.'
        : 'Het versturen is niet gelukt. Probeer het nog eens of mail ons op info@badassrentals.nl.';
      form.prepend(msg);
      form.scrollIntoView();
    }

    form.addEventListener('submit', function (e) {
      // Minstens één keuze bij verplichte checkbox-groepen
      var group = form.querySelector('[data-required-group]');
      if (group && !group.querySelector('input:checked')) {
        e.preventDefault();
        alert('Kies minimaal één optie.');
        return;
      }
      var btn = form.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = 'Bezig met versturen…'; }
    });
  });

  // Link naar een antwoord in een ingeklapte FAQ (#anker): vraag openklappen
  function openHashTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    var t = id && document.getElementById(id);
    var d = t && t.closest('details');
    if (d) d.open = true;
  }
  openHashTarget();
  window.addEventListener('hashchange', openHashTarget);

  // Datum/tijd standaard op nu (huurovereenkomst)
  var dt = document.querySelector('input[type="datetime-local"][data-now]');
  if (dt && !dt.value) {
    var d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    dt.value = d.toISOString().slice(0, 16);
  }
})();
