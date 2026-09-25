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

  // Live Google-reviews (via /reviews.php). Lukt dat niet, dan blijven de vaste reviews staan.
  var blocks = document.querySelectorAll('[data-google-reviews]');
  if (blocks.length && window.fetch) {
    fetch('/reviews.php', { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.reviews || data.reviews.length < 3) return;
        blocks.forEach(function (block) { renderReviews(block, data); });
      })
      .catch(function () {});
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function renderReviews(block, data) {
    var list = block.querySelector('.reviews');
    var summary = block.querySelector('.reviews-summary');
    if (data.rating && data.count) {
      summary.textContent = '';
      summary.appendChild(el('strong', '', String(data.rating).replace('.', ',') + ' ★'));
      summary.appendChild(document.createTextNode(' op Google, gebaseerd op ' + data.count + ' reviews. '));
      if (data.url) {
        var a = el('a', 'link-arrow', 'Bekijk alle reviews');
        a.href = data.url; a.rel = 'noopener';
        summary.appendChild(a);
      }
      summary.hidden = false;
    }
    list.textContent = '';
    data.reviews.forEach(function (r) {
      var fig = el('figure', 'review');
      var stars = el('div', 'stars', '★★★★★'.slice(0, r.rating));
      stars.setAttribute('aria-label', r.rating + ' sterren');
      fig.appendChild(stars);
      fig.appendChild(el('blockquote', '', r.text));
      var cap = el('figcaption');
      if (r.author_url) {
        var link = el('a', '', r.author); link.href = r.author_url; link.rel = 'noopener nofollow';
        cap.appendChild(link);
      } else {
        cap.textContent = r.author;
      }
      cap.appendChild(el('span', 'review-meta', (r.when ? r.when + ' · ' : '') + 'Google'));
      fig.appendChild(cap);
      list.appendChild(fig);
    });
  }

  // Datum/tijd standaard op nu (huurovereenkomst)
  var dt = document.querySelector('input[type="datetime-local"][data-now]');
  if (dt && !dt.value) {
    var d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    dt.value = d.toISOString().slice(0, 16);
  }
})();
