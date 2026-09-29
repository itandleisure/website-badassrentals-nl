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

  // Formulieren: invultijd meten tegen spam-bots, knop blokkeren tijdens verzenden, foutmelding tonen.
  // De invultijd wordt op het apparaat zelf gemeten, dus een verkeerd ingestelde klok maakt niet uit.
  var params = new URLSearchParams(location.search);
  var geladen = (window.performance && performance.now) ? function () { return performance.now(); } : null;
  var start = Date.now();
  document.querySelectorAll('form.js-form').forEach(function (form) {
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
      var duur = form.querySelector('input[name="duur"]');
      if (duur) duur.value = String(Math.round(geladen ? geladen() : Date.now() - start));
      var btn = form.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = 'Bezig met versturen…'; }

      // Google Sheets + e-mail via Apps Script (URL op <body data-google-form>).
      // Lukt dat niet, dan gaat het formulier gewoon naar verzenden.php (de action), zodat er niets verloren gaat.
      var googleUrl = document.body.getAttribute('data-google-form');
      if (!googleUrl || !window.fetch || !window.AbortController) return;
      e.preventDefault();
      var type = (form.querySelector('input[name="form"]') || {}).value;
      var bedankt = '/bedankt/';
      var stop = new AbortController();
      var timer = setTimeout(function () { stop.abort(); }, 15000);
      fetch(googleUrl, { method: 'POST', body: new URLSearchParams(new FormData(form)), signal: stop.signal })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          clearTimeout(timer);
          if (res.ok) { location.href = bedankt; return; }
          if (res.fout === 'velden') {
            location.href = location.pathname + '?fout=velden#formulier';
            if (location.search) location.reload();
            return;
          }
          throw new Error(res.fout || 'mislukt');
        })
        .catch(function () {
          clearTimeout(timer);
          if (/verzenden\.php$/.test(form.getAttribute('action') || '')) {
            HTMLFormElement.prototype.submit.call(form);  // reserveroute op eigen hosting: verzenden.php
            return;
          }
          // Geen reserveroute (GitHub Pages): melding tonen, niets gaat stilletjes verloren
          if (btn) { btn.disabled = false; btn.textContent = 'Opnieuw versturen'; }
          var oud = form.querySelector('.form-msg'); if (oud) oud.remove();
          var msg = document.createElement('div');
          msg.className = 'form-msg err';
          msg.setAttribute('role', 'alert');
          msg.innerHTML = 'Het versturen is niet gelukt. Probeer het nog eens, of neem direct contact op: ' +
            '<a href="tel:+31850047700">085 004 7700</a> of <a href="mailto:info@badassrentals.nl">info@badassrentals.nl</a>.';
          form.prepend(msg);
          msg.scrollIntoView({ block: 'center' });
        });
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

})();
