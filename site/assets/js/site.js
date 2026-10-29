/* Nutrivero – chování stránky (menu, plynulá navigace, FAQ, reference, kontaktní formulář, květinový slider).
   Bez závislostí; bezpečné pro defer i pro podstránky, kde některé prvky chybí. */
(function () {
  'use strict';

  var doc = document;
  var WIDE_MQ = '(min-width: 1100px)';

  // JavaScript běží: zobrazit prvky .js-only (bez JS je skrývá site.css).
  if (doc.documentElement.classList) doc.documentElement.classList.add('js');

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function onMqChange(mq, fn) {
    if (!mq) return;
    if (mq.addEventListener) mq.addEventListener('change', fn);
    else if (mq.addListener) mq.addListener(fn);
  }

  /* ───────── Mobilní menu ───────── */
  var toggle = doc.querySelector('[data-menu-toggle]');
  var panel = doc.getElementById('mobilni-menu');
  var backdrop = doc.querySelector('[data-menu-backdrop]');

  function menuIsOpen() {
    return !!toggle && toggle.getAttribute('aria-expanded') === 'true';
  }
  function setMenu(open, returnFocus) {
    if (!toggle || !panel) return;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.setAttribute('aria-label', open ? 'Zavřít menu' : 'Otevřít menu');
    panel.hidden = !open;
    if (backdrop) backdrop.hidden = !open;
    if (doc.documentElement.classList) doc.documentElement.classList.toggle('nv-menu-open', open);
    if (!open && returnFocus) toggle.focus();
  }

  if (toggle && panel) {
    toggle.addEventListener('click', function () {
      setMenu(!menuIsOpen(), false);
    });
    if (backdrop) {
      backdrop.addEventListener('click', function () { setMenu(false, false); });
    }
    doc.addEventListener('keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && menuIsOpen()) {
        setMenu(false, true);
      }
    });
    panel.addEventListener('click', function (e) {
      var link = e.target && e.target.closest ? e.target.closest('a') : null;
      if (link) setMenu(false, false);
    });
    // Klávesnice: když fokus odejde z otevřeného menu jinam než na přepínač, menu zavřít.
    panel.addEventListener('focusout', function (e) {
      var to = e.relatedTarget;
      if (menuIsOpen() && to && !panel.contains(to) && to !== toggle) setMenu(false, false);
    });
    if (window.matchMedia) {
      var wideMq = window.matchMedia(WIDE_MQ);
      onMqChange(wideMq, function () { if (wideMq.matches) setMenu(false, false); });
    }
  }

  /* ───────── Plynulá navigace na stránce ─────────
     Stejná matematika jako v prototypu:
     – #rezervace (goBook): horní hrana sekce − 72 px,
     – ostatní kotvy (onNav): horní hrana + padding-top − výška hlavičky − 32 px. */
  function scrollTargetTop(el) {
    var top = el.getBoundingClientRect().top + window.pageYOffset;
    if (el.id === 'rezervace') return top - 72;
    var head = doc.querySelector('header');
    var pt = parseFloat(window.getComputedStyle(el).paddingTop) || 0;
    return top + pt - (head ? head.offsetHeight : 72) - 32;
  }

  doc.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var link = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (!link) return;
    var href = link.getAttribute('href');
    if (!href || href.length < 2) return;
    var id;
    try { id = decodeURIComponent(href.slice(1)); } catch (err) { id = href.slice(1); }
    var el = doc.getElementById(id);
    if (!el) return;
    e.preventDefault();
    if (menuIsOpen()) setMenu(false, false);
    window.scrollTo({ top: Math.max(0, scrollTargetTop(el)), behavior: reducedMotion() ? 'auto' : 'smooth' });
    if (window.history && window.history.replaceState) {
      try { window.history.replaceState(null, '', '#' + id); } catch (err) { /* ignore */ }
    }
    // Klávesnice: přesunout fokus do cílové sekce bez dalšího posunu.
    if (!el.hasAttribute('tabindex')) {
      el.setAttribute('tabindex', '-1');
      el.setAttribute('data-nv-target', '');
    }
    try { el.focus({ preventScroll: true }); } catch (err) { /* starší prohlížeče */ }
  });

  /* ───────── FAQ ───────── */
  var faqButtons = doc.querySelectorAll('.faq-btn[aria-controls]');
  Array.prototype.forEach.call(faqButtons, function (btn) {
    btn.addEventListener('click', function () {
      var answer = doc.getElementById(btn.getAttribute('aria-controls'));
      var open = btn.getAttribute('aria-expanded') !== 'true';
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (answer) answer.hidden = !open;
    });
  });

  var faqMore = doc.querySelector('[data-faq-more]');
  if (faqMore) {
    faqMore.addEventListener('click', function () {
      var extra = doc.querySelectorAll('[data-faq-extra]');
      Array.prototype.forEach.call(extra, function (item) { item.hidden = false; });
      var first = extra.length ? extra[0].querySelector('.faq-btn') : null;
      if (faqMore.parentNode) faqMore.parentNode.removeChild(faqMore);
      if (first) first.focus();
    });
  }

  /* ───────── Reference (karusel) ───────── */
  var refTrack = doc.querySelector('[data-ref-track]');
  function refMove(dir) {
    if (!refTrack) return;
    var f = refTrack.querySelector('figure');
    var step = f ? f.offsetWidth + parseFloat(window.getComputedStyle(refTrack).columnGap || 16) : refTrack.clientWidth * 0.8;
    if (refTrack.scrollBy) refTrack.scrollBy({ left: dir * step, behavior: reducedMotion() ? 'auto' : 'smooth' });
    else refTrack.scrollLeft += dir * step;
  }
  var refPrev = doc.querySelector('[data-ref-prev]');
  var refNext = doc.querySelector('[data-ref-next]');
  if (refTrack && refPrev) refPrev.addEventListener('click', function () { refMove(-1); });
  if (refTrack && refNext) refNext.addEventListener('click', function () { refMove(1); });

  /* ───────── Kontaktní formulář (FormSubmit) ─────────
     Bez JavaScriptu se formulář odešle klasicky (action na formsubmit.co). S JavaScriptem se odešle
     jako JSON na data-ajax-endpoint a výsledek se ukáže na stránce. Vyplněné skryté pole _honey
     (spamovací robot) se tváří jako úspěch, ale nic se neodešle. */
  var kForm = doc.querySelector('[data-kontakt-form]');

  // Tlačítko „Rezervovat konzultaci“ v ceníku: předvybere zájem a případně předvyplní zprávu.
  // Posun na #kontakt obstará společná obsluha kotev výše (posluchač na dokumentu běží až po tomto).
  Array.prototype.forEach.call(doc.querySelectorAll('[data-kontakt-zajem]'), function (link) {
    link.addEventListener('click', function () {
      if (!kForm) return;
      var select = kForm.elements['Zájem'];
      var message = kForm.elements['Zpráva'];
      var value = link.getAttribute('data-kontakt-zajem');
      if (select && select.options && value) {
        for (var i = 0; i < select.options.length; i++) {
          if (select.options[i].value === value) { select.selectedIndex = i; break; }
        }
      }
      var text = link.getAttribute('data-kontakt-zprava');
      if (message && text && !message.value.trim()) message.value = text;
    });
  });

  if (kForm && window.fetch && window.JSON) {
    var kButton = kForm.querySelector('[data-kontakt-submit]');
    var kButtonLabel = kButton ? kButton.textContent : '';
    var kDone = doc.querySelector('[data-kontakt-hotovo]');
    var kError = doc.querySelector('[data-kontakt-chyba]');
    var kSending = false;

    var kValue = function (name) {
      var f = kForm.elements[name];
      return f && typeof f.value === 'string' ? f.value.trim() : '';
    };
    var kSetSending = function (on) {
      kSending = on;
      kForm.setAttribute('aria-busy', on ? 'true' : 'false');
      if (!kButton) return;
      kButton.textContent = on ? 'Odesílám…' : kButtonLabel;
      // aria-disabled místo disabled: tlačítko si během odesílání ponechá fokus.
      if (on) kButton.setAttribute('aria-disabled', 'true');
      else kButton.removeAttribute('aria-disabled');
    };
    var kShowDone = function () {
      if (kError) kError.hidden = true;
      kForm.hidden = true;
      if (kDone) {
        kDone.hidden = false;
        try { kDone.focus(); } catch (err) { /* starší prohlížeče */ }
      }
    };

    kForm.addEventListener('submit', function (e) {
      // Událost submit přichází až po úspěšné nativní kontrole polí (required, type=email).
      var endpoint = kForm.getAttribute('data-ajax-endpoint');
      if (!endpoint) return; // bez adresy pro AJAX klasické odeslání
      e.preventDefault();
      if (kSending) return;
      if (kError) kError.hidden = true;

      var honey = kValue('_honey');
      if (honey) { kForm.reset(); kShowDone(); return; }

      var zajem = kValue('Zájem');
      var payload = {
        _subject: 'Web Nutrivero: ' + zajem,
        _template: 'table',
        _captcha: 'false',
        _honey: honey,
        'Jméno': kValue('Jméno'),
        email: kValue('email'),
        'Telefon': kValue('Telefon'),
        'Zájem': zajem,
        'Zpráva': kValue('Zpráva')
      };

      kSetSending(true);
      var ctrl = window.AbortController ? new window.AbortController() : null;
      var timer = ctrl ? window.setTimeout(function () { ctrl.abort(); }, 20000) : null;
      var opts = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(payload)
      };
      if (ctrl) opts.signal = ctrl.signal;

      window.fetch(endpoint, opts)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d && (d.success === true || d.success === 'true')) {
            kForm.reset();
            kShowDone();
          } else if (kError) {
            kError.hidden = false;
          }
        })
        .catch(function () { if (kError) kError.hidden = false; })
        .then(function () {
          if (timer) window.clearTimeout(timer);
          kSetSending(false);
        });
    });
  }

  /* ───────── Tabulky v právních textech: posuvný obal na mobilu ───────── */
  Array.prototype.forEach.call(doc.querySelectorAll('.legal table'), function (table) {
    var parent = table.parentNode;
    if (!parent) return;
    var wrap = parent;
    if (!(parent.classList && parent.classList.contains('table-wrap'))) {
      wrap = doc.createElement('div');
      wrap.className = 'table-wrap';
      parent.insertBefore(wrap, table);
      wrap.appendChild(table);
    }
    // Posuvná oblast musí být dosažitelná klávesnicí a pojmenovaná.
    if (!wrap.hasAttribute('tabindex')) wrap.setAttribute('tabindex', '0');
    if (!wrap.hasAttribute('role')) wrap.setAttribute('role', 'region');
    if (!wrap.hasAttribute('aria-label') && !wrap.hasAttribute('aria-labelledby')) {
      var cap = table.querySelector('caption');
      wrap.setAttribute('aria-label', cap && cap.textContent ? cap.textContent.trim() : 'Tabulka');
    }
  });

  /* ───────── Květinový slider (jen ≥ 1100 px) ───────── */
  var track = doc.querySelector('[data-kvetiny-track]');
  var flowersBox = track ? track.querySelector('[data-kvetiny]') : null;
  var slideBtn = track ? track.querySelector('[data-kvetiny-btn]') : null;

  function el(styles, attrs) {
    var d = doc.createElement('div');
    var k;
    if (attrs) for (k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) d.setAttribute(k, attrs[k]);
    for (k in styles) if (Object.prototype.hasOwnProperty.call(styles, k)) d.style[k] = styles[k];
    return d;
  }

  function buildFlowers() {
    var N = 16;
    var frag = doc.createDocumentFragment();
    for (var i = 0; i < N; i++) {
      var f = (i + 0.3) / N;
      var hgt = 40 + ((i * 37) % 5) * 13;
      var type = i % 3;
      var stem = el({
        position: 'relative', width: '2px', height: hgt + 'px', backgroundColor: 'var(--color-accent)',
        borderRadius: '2px', transformOrigin: '50% 100%', transform: 'scaleY(0)'
      }, { 'data-nv-stem': '' });
      stem.appendChild(el({ position: 'absolute', right: '2px', bottom: (hgt * 0.32) + 'px', width: '14px', height: '14px', borderRadius: '100% 0 100% 0', backgroundColor: '#A5BA8F' }));
      stem.appendChild(el({ position: 'absolute', left: '2px', bottom: (hgt * 0.55) + 'px', width: '12px', height: '12px', borderRadius: '0 100% 0 100%', backgroundColor: '#A5BA8F' }));
      var bloomBase = { transform: 'scale(0)', transition: 'transform .35s cubic-bezier(.3,1.6,.5,1)', position: 'absolute' };
      var bloom;
      if (type === 0) {
        bloom = el(Object.assign({}, bloomBase, { top: '-13px', left: '-12px', width: '26px', height: '26px' }), { 'data-nv-bloom': '' });
        for (var k = 0; k < 6; k++) {
          bloom.appendChild(el({ position: 'absolute', left: '8px', top: '6px', width: '10px', height: '14px', borderRadius: '50%', backgroundColor: '#FDFBF7', transform: 'rotate(' + (k * 60) + 'deg) translateY(-8px)' }));
        }
        bloom.appendChild(el({ position: 'absolute', left: '7px', top: '7px', width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#E1C243' }));
      } else if (type === 1) {
        bloom = el(Object.assign({}, bloomBase, { top: '-8px', left: '-6px', width: '14px', height: '16px', borderRadius: '50% 50% 45% 45%', backgroundColor: '#E1C243' }), { 'data-nv-bloom': '' });
      } else {
        bloom = el(Object.assign({}, bloomBase, { top: '-6px', left: '-1px', width: '16px', height: '16px', borderRadius: '0 100% 0 100%', backgroundColor: 'var(--color-accent)' }), { 'data-nv-bloom': '' });
      }
      stem.appendChild(bloom);
      var flower = el({
        position: 'absolute', bottom: '0px', left: (f * 100) + '%', transformOrigin: '50% 100%',
        animation: 'nv-sway 4s ease-in-out ' + (-i * 0.5) + 's infinite'
      }, { 'data-nv-flower': String(f), 'data-nv-anim': '' });
      flower.appendChild(stem);
      frag.appendChild(flower);
    }
    flowersBox.appendChild(frag);
  }

  if (track && flowersBox && slideBtn) {
    buildFlowers();
    var flowers = flowersBox.querySelectorAll('[data-nv-flower]');
    var wideQuery = window.matchMedia ? window.matchMedia(WIDE_MQ) : null;
    var raf = null;
    var slide = function () {
      raf = null;
      // Pod 1100 px je slider skrytý (CSS) – nic nepočítat, ať se zbytečně nevynucuje layout.
      if (wideQuery && !wideQuery.matches) return;
      var r = track.getBoundingClientRect();
      var vh = window.innerHeight;
      var p = reducedMotion() ? 1 : (vh - r.top) / (vh * 0.7);
      p = Math.max(0, Math.min(1, p));
      var range = Math.max(0, r.width - slideBtn.offsetWidth);
      var mobile = window.innerWidth < 760;
      var x = p * range;
      slideBtn.style.transform = 'translateX(' + (mobile ? range : x) + 'px)';
      for (var i = 0; i < flowers.length; i++) {
        var fl = flowers[i];
        var fx = parseFloat(fl.getAttribute('data-nv-flower')) * r.width;
        var g = Math.max(0, Math.min(1, (x - fx + 4) / 70));
        var st = fl.querySelector('[data-nv-stem]');
        var bl = fl.querySelector('[data-nv-bloom]');
        if (st) st.style.transform = 'scaleY(' + g + ')';
        if (bl) bl.style.transform = 'scale(' + (g > 0.85 ? 1 : 0) + ')';
      }
    };
    var onSlideScroll = function () { if (!raf) raf = window.requestAnimationFrame(slide); };
    window.addEventListener('scroll', onSlideScroll, { passive: true });
    window.addEventListener('resize', onSlideScroll);
    if (window.matchMedia) {
      onMqChange(window.matchMedia('(prefers-reduced-motion: reduce)'), onSlideScroll);
      onMqChange(wideQuery, onSlideScroll);
    }
    window.setTimeout(onSlideScroll, 50);
  }
})();
