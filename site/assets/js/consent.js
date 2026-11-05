/*!
 * Nutrivero – správa souhlasu s cookies, externím obsahem a měřením (consent.js)
 *
 * Bez závislostí, bezpečné pro <script defer>, žádný inline kód ani vkládané <style>.
 * Vzhled: /assets/css/consent.css (třídy s prefixem "nvc-").
 *
 * Úložiště:  localStorage "nv-consent" = {"v":2,"ts":"<ISO>","categories":{"externi":true|false, …}}
 *            Platnost 6 měsíců; chybějící, poškozený, prošlý nebo jinak verzovaný záznam = bez souhlasu.
 *            Záznam musí obsahovat všechny zobrazené volitelné kategorie – po přidání kategorie
 *            (např. doplněním GA_ID) se lišta zobrazí znovu.
 * API:       window.nvConsent = { has(cat), grant(cat), revoke(cat), set(obj), get(), openSettings(), refresh() }
 * Událost:   document → CustomEvent "nv:consent", detail = kategorie (např. {externi: true, marketing: false})
 * Háčky:     [data-consent-open]                      – otevře nastavení
 *            [data-consent-embed="kat"][data-src][data-title][data-height]
 *                                                      – obsah se vloží jako <iframe> až po souhlasu
 *            [data-consent-accept="kat"]               – udělí souhlas jen s danou kategorií
 *
 * Měření (načítá se jen odsud a jen po souhlasu; ID dodává build do <html>):
 *   <html data-ga-id="G-…">              – Google Analytics 4, kategorie "analytika" (prázdné = vypnuto,
 *                                          kategorie se nezobrazí a nic se nenačte)
 *   <html data-meta-pixel-id="123…">     – Meta pixel, kategorie "marketing" (prázdné = vypnuto)
 *   Konverze: document → CustomEvent "nv:lead" (odeslaný kontaktní formulář) a "nv:booking" (klik vedoucí
 *   k rezervaci; posílá site.js). Předají se jen nástrojům se souhlasem a bez jakýchkoli údajů z formuláře
 *   (detail události se ignoruje): GA generate_lead / booking_open, Meta Lead / BookingOpen.
 *   Odvolání souhlasu: smaže cookies nástroje (_ga, _ga_*, _gid / _fbp, _fbc) na této doméně i nadřazené
 *   a stránku jednou znovu načte, aby skripty zmizely. Změna z jiné záložky je jen vypne (bez reloadu).
 */
(function () {
  'use strict';

  if (window.nvConsent && window.nvConsent.__nvc) return; // skript už běží

  /* ------------------------------------------------------------------ */
  /* Konfigurace                                                         */
  /* ------------------------------------------------------------------ */

  var root = document.documentElement;

  // ID nástrojů měření z <html> (build: %%GA_ID%%, %%META_PIXEL_ID%%). Neplatné nebo prázdné = vypnuto.
  function readId(attr, re) {
    var v = (root.getAttribute(attr) || '').trim();
    return re.test(v) ? v : '';
  }
  var GA_ID = readId('data-ga-id', /^G-[A-Z0-9]+$/);
  var META_PIXEL_ID = readId('data-meta-pixel-id', /^[0-9]+$/);

  // Kategorie souhlasu. Novou volitelnou kategorii stačí přidat sem: uložené souhlasy, které ji
  // ještě neobsahují, se považují za neplatné a lišta se zobrazí znovu.
  // meta = krátký řádek s poskytovatelem a cookies pod popisem v nastavení.
  var CATEGORIES = [
    {
      id: 'nezbytne',
      required: true,
      title: 'Nezbytné',
      description: 'Uchovávají jen vaši volbu z této lišty (položka „nv-consent“ v úložišti prohlížeče, 6 měsíců). ' +
        'Bez nich by si web vaši volbu nezapamatoval, proto je nelze vypnout. Neslouží ke sledování a nic neodesílají.'
    },
    {
      id: 'externi',
      required: false,
      title: 'Externí obsah',
      description: 'Načte rezervační Kalendář Google přímo na stránce, abyste si mohli vybrat termín nezávazného hovoru. ' +
        'Obsah poskytuje Google Ireland Limited (Irsko) a Google LLC (USA). Při načtení Google získá vaši IP adresu ' +
        'a může ukládat vlastní cookies podle svých zásad. Bez souhlasu se kalendář nenačte; rezervaci můžete ' +
        'i tak otevřít v novém okně přímo na webu Google.',
      meta: 'Google Ireland Limited · cookies Googlu, např. NID, AEC, SOCS'
    }
  ];
  if (GA_ID) {
    CATEGORIES.push({
      id: 'analytika',
      required: false,
      title: 'Analytické',
      description: 'Google Analytics – souhrnné statistiky návštěvnosti: kolik lidí web navštívilo, ' +
        'odkud přišli a které stránky je zajímají. Konkrétního člověka podle nich poznat nelze a reklamy se ' +
        'podle nich necílí (Google signály a personalizace reklam jsou vypnuté). Google Analytics pro ' +
        'provozovatelku webu provozuje Google jako zpracovatel. Bez souhlasu se Google Analytics nenačte.',
      meta: 'Google Ireland Limited · cookies _ga, _ga_* (2 roky)'
    });
  }
  if (META_PIXEL_ID) {
    CATEGORIES.push({
      id: 'marketing',
      required: false,
      title: 'Marketingové',
      description: 'Meta pixel – měření, kolik lidí přišlo z reklam na Facebooku a Instagramu a kolik z nich pak ' +
        'otevřelo rezervaci hovoru nebo napsalo zprávu. Meta se tím dozví, že jste navštívili web výživové ' +
        'poradkyně, z čehož lze nepřímo usuzovat na váš zájem o výživu, hmotnost nebo zdraví, a může tyto údaje ' +
        'spojit s vaším účtem na Facebooku nebo Instagramu a cílit podle nich reklamy. Povolením této kategorie ' +
        '(i tlačítkem „Přijmout vše“) s tím výslovně souhlasíte. Za získání a předání těchto údajů odpovídá ' +
        'provozovatelka webu společně se společností Meta Platforms Ireland Limited (společní správci). Jméno, ' +
        'e-mail, telefon ani obsah formuláře se Metě neposílají. Bez souhlasu se Meta pixel nenačte.',
      meta: 'Meta Platforms Ireland Limited · cookies _fbp, _fbc (3 měsíce)'
    });
  }

  var STORAGE_KEY = 'nv-consent';
  var VERSION = 2;
  var MAX_AGE_MONTHS = 6;
  var EVENT_NAME = 'nv:consent';
  // Web může běžet v podsložce (náhled na GitHub Pages: /nutrivero-nahled). Build ji zapíše
  // do <html data-base="…">; v kořeni domény je prázdná. Chybí-li atribut, odvodí se z adresy
  // tohoto skriptu (…/assets/js/consent.js → o dvě úrovně výš).
  var BASE_PATH = (function () {
    var attr = document.documentElement.getAttribute('data-base');
    if (attr !== null) return attr.replace(/\/+$/, '');
    var src = document.currentScript && document.currentScript.src;
    if (!src) return '';
    try { return new URL('../../', src).pathname.replace(/\/+$/, ''); } catch (e) { return ''; }
  })();
  var COOKIES_URL = BASE_PATH + '/cookies/';
  var PRIVACY_URL = BASE_PATH + '/ochrana-osobnich-udaju/#cookies';
  var DEFAULT_EMBED_HEIGHT = 620;
  var GA_SCRIPT = 'https://www.googletagmanager.com/gtag/js?id=';
  var META_SCRIPT = 'https://connect.facebook.net/en_US/fbevents.js';

  /* ------------------------------------------------------------------ */
  /* Stav                                                                */
  /* ------------------------------------------------------------------ */

  var storageOk = true;   // false, jakmile localStorage vyhodí výjimku
  var memory = null;      // záloha v paměti (platí jen pro aktuální stránku)
  var current = null;     // platný záznam souhlasu, nebo null
  var ready = false;
  var banner = null;
  var dialog = null;
  var statusEl = null;
  var switches = {};
  var stateLabels = {};
  var opener = null;
  var resizeObs = null;
  var downOnBackdrop = false;
  var placeholders = new WeakMap();

  /* ------------------------------------------------------------------ */
  /* Pomocné funkce                                                      */
  /* ------------------------------------------------------------------ */

  // Česká typografie: nezlomitelná mezera po jednopísmenných předložkách/spojkách,
  // mezi číslem a slovem a před pomlčkou.
  function typo(s) {
    var prev;
    s = String(s);
    do {
      prev = s;
      s = s.replace(/(^|[\s („])([AIKOSUVZaikosuvz]) /g, '$1$2 ');
    } while (s !== prev);
    return s.replace(/(\d) (?=[^\s\d])/g, '$1 ').replace(/ – /g, ' – ');
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      for (var key in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, key)) continue;
        var val = attrs[key];
        if (val === null || val === undefined || val === false) continue;
        if (key === 'class') node.className = val;
        else node.setAttribute(key, val === true ? '' : String(val));
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    if (children === null || children === undefined) return;
    if (!Array.isArray(children)) children = [children];
    for (var i = 0; i < children.length; i++) {
      var c = children[i];
      if (c === null || c === undefined || c === false) continue;
      node.appendChild(typeof c === 'string' ? document.createTextNode(typo(c)) : c);
    }
  }

  function button(label, variant, action, extra) {
    var attrs = { type: 'button', 'class': 'nvc-btn nvc-btn--' + variant, 'data-nvc-action': action };
    if (extra) for (var k in extra) attrs[k] = extra[k];
    return el('button', attrs, label);
  }

  function closeIcon() {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    var attrs = { viewBox: '0 0 24 24', width: '20', height: '20', fill: 'none', stroke: 'currentColor',
      'stroke-width': '2.5', 'stroke-linecap': 'round', 'aria-hidden': 'true', focusable: 'false' };
    for (var k in attrs) svg.setAttribute(k, attrs[k]);
    var path = document.createElementNS(ns, 'path');
    path.setAttribute('d', 'M18 6 6 18M6 6l12 12');
    svg.appendChild(path);
    return svg;
  }

  function findCat(id) {
    for (var i = 0; i < CATEGORIES.length; i++) if (CATEGORIES[i].id === id) return CATEGORIES[i];
    return null;
  }

  function optionalCats() {
    return CATEGORIES.filter(function (c) { return !c.required; });
  }

  function copy(obj) {
    var out = {};
    for (var k in obj) if (Object.prototype.hasOwnProperty.call(obj, k)) out[k] = obj[k];
    return out;
  }

  function addMonths(ms, n) {
    var d = new Date(ms);
    d.setMonth(d.getMonth() + n);
    return d.getTime();
  }

  function formatDate(ms) {
    var d = new Date(ms);
    return d.getDate() + '. ' + (d.getMonth() + 1) + '. ' + d.getFullYear();
  }

  function isVisible(node) {
    return !!(node && (node.offsetWidth || node.offsetHeight || node.getClientRects().length));
  }

  function focusQuietly(node) {
    if (!node || typeof node.focus !== 'function') return;
    try { node.focus({ preventScroll: true }); } catch (e) { node.focus(); }
  }

  // Prvek s fokusem zmizel spolu s lištou → fokus na začátek hlavního obsahu, aby nespadl
  // na <body> a další Tab nezačínal znovu od začátku stránky (WCAG 2.4.3).
  function focusMainFallback() {
    var main = document.getElementById('obsah') || document.querySelector('main');
    if (!main) return;
    if (!main.hasAttribute('tabindex')) {
      main.setAttribute('tabindex', '-1');
      main.setAttribute('data-nv-target', ''); // stejně jako site.js: bez obrysu při fokusu
    }
    focusQuietly(main);
  }

  /* ------------------------------------------------------------------ */
  /* Úložiště (každý přístup v try/catch, záloha v paměti)               */
  /* ------------------------------------------------------------------ */

  function storageRead() {
    if (storageOk) {
      try { return window.localStorage.getItem(STORAGE_KEY); } catch (e) { storageOk = false; }
    }
    return memory;
  }

  function storageWrite(value) {
    memory = value;
    if (!storageOk) return;
    try {
      if (value === null) window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, value);
    } catch (e) {
      storageOk = false;
    }
  }

  function parseRecord(raw) {
    if (!raw) return null;
    var data;
    try { data = JSON.parse(raw); } catch (e) { return null; }
    if (!data || typeof data !== 'object' || data.v !== VERSION || typeof data.ts !== 'string') return null;
    var ts = Date.parse(data.ts);
    var now = Date.now();
    if (isNaN(ts) || ts > now + 864e5 || now >= addMonths(ts, MAX_AGE_MONTHS)) return null;
    var src = data.categories;
    if (!src || typeof src !== 'object') return null;
    var cats = {};
    var opt = optionalCats();
    for (var i = 0; i < opt.length; i++) {
      if (typeof src[opt[i].id] !== 'boolean') return null; // nová kategorie → zeptat se znovu
      cats[opt[i].id] = src[opt[i].id];
    }
    return { v: VERSION, ts: data.ts, categories: cats };
  }

  function loadStored() {
    var raw = storageRead();
    var rec = parseRecord(raw);
    if (raw && !rec) storageWrite(null); // neplatný nebo prošlý záznam smažeme
    return rec;
  }

  /* ------------------------------------------------------------------ */
  /* Stav souhlasu                                                       */
  /* ------------------------------------------------------------------ */

  function has(id) {
    var c = findCat(id);
    if (!c) return false;
    if (c.required) return true;
    return !!(current && current.categories[id] === true);
  }

  function effective() {
    var out = {};
    optionalCats().forEach(function (c) { out[c.id] = has(c.id); });
    return out;
  }

  function commit(cats) {
    var norm = {};
    optionalCats().forEach(function (c) { norm[c.id] = cats[c.id] === true; });
    current = { v: VERSION, ts: new Date().toISOString(), categories: norm };
    storageWrite(JSON.stringify(current));
    applyState(true, false);
    return copy(norm);
  }

  function setAll(value) {
    var cats = {};
    optionalCats().forEach(function (c) { cats[c.id] = value; });
    return commit(cats);
  }

  // external = změna přišla odjinud (jiná záložka, návrat z bfcache) – měření se jen vypne, bez reloadu.
  function applyState(notify, external) {
    var reload = syncTrackers(!external);
    syncEmbeds();
    syncDialog();
    if (current) hideBanner();
    else if (ready) showBanner();
    if (notify) dispatch();
    if (reload) scheduleReload();
  }

  function dispatch() {
    var detail = effective();
    var ev;
    try {
      ev = new CustomEvent(EVENT_NAME, { detail: detail });
    } catch (e) {
      ev = document.createEvent('CustomEvent');
      ev.initCustomEvent(EVENT_NAME, false, false, detail);
    }
    document.dispatchEvent(ev);
  }

  /* ------------------------------------------------------------------ */
  /* Měření: Google Analytics 4 a Meta pixel (jen po souhlasu)           */
  /* ------------------------------------------------------------------ */

  function injectScript(src) {
    var s = document.createElement('script');
    s.async = true;
    s.src = src;
    (document.head || root).appendChild(s);
  }

  // gtag() podle oficiálního fragmentu – do dataLayer musí jít objekt arguments, ne pole.
  function gtag() {
    window.dataLayer.push(arguments);
  }

  var TRACKERS = {
    analytika: {
      enabled: !!GA_ID,
      loaded: false,   // skript je na této stránce vložený
      paused: false,   // souhlas odvolán v jiné záložce – vypnuto do příštího načtení stránky
      cookies: [/^_ga$/, /^_ga_/, /^_gid$/],
      load: function () {
        window.dataLayer = window.dataLayer || [];
        window['ga-disable-' + GA_ID] = false;
        if (typeof window.gtag !== 'function') window.gtag = gtag;
        // Souhlas se týká jen statistik: reklamní úložiště a signály zůstávají zakázané.
        gtag('consent', 'default', {
          analytics_storage: 'granted',
          ad_storage: 'denied',
          ad_user_data: 'denied',
          ad_personalization: 'denied'
        });
        gtag('js', new Date());
        // config odešle page_view (send_page_view je ve výchozím stavu zapnuté).
        gtag('config', GA_ID, {
          allow_google_signals: false,
          allow_ad_personalization_signals: false
        });
        injectScript(GA_SCRIPT + encodeURIComponent(GA_ID));
      },
      // ga-disable gtag čte hlavně při startu, proto navíc aktualizace souhlasu (platí i pro běžící gtag).
      pause: function () {
        window['ga-disable-' + GA_ID] = true;
        gtag('consent', 'update', { analytics_storage: 'denied' });
      },
      resume: function () {
        window['ga-disable-' + GA_ID] = false;
        gtag('consent', 'update', { analytics_storage: 'granted' });
      },
      lead: function () { gtag('event', 'generate_lead'); },
      booking: function () { gtag('event', 'booking_open'); }
    },
    marketing: {
      enabled: !!META_PIXEL_ID,
      loaded: false,
      paused: false,
      cookies: [/^_fbp$/, /^_fbc$/],
      load: function () {
        // Standardní zavaděč fbq (bez inline <script> a bez <noscript> obrázku).
        var n = window.fbq;
        if (typeof n !== 'function') {
          n = window.fbq = function () {
            if (n.callMethod) n.callMethod.apply(n, arguments);
            else n.queue.push(arguments);
          };
          if (!window._fbq) window._fbq = n;
          n.push = n;
          n.loaded = true;
          n.version = '2.0';
          n.queue = [];
          // Žádné další PageView při změně kotvy (#cena, #kontakt…) přes history.replaceState v site.js.
          n.disablePushState = true;
          injectScript(META_SCRIPT);
        }
        // Před init: vypnout automatickou konfiguraci (sledování kliknutí, metadat stránky a polí formulářů).
        n('set', 'autoConfig', false, META_PIXEL_ID);
        n('init', META_PIXEL_ID); // bez údajů o uživateli (žádné advanced matching)
        n('track', 'PageView');
      },
      pause: function () { if (typeof window.fbq === 'function') window.fbq('consent', 'revoke'); },
      resume: function () { if (typeof window.fbq === 'function') window.fbq('consent', 'grant'); },
      lead: function () { window.fbq('track', 'Lead'); },
      booking: function () { window.fbq('trackCustom', 'BookingOpen'); }
    }
  };

  // Domény, pro které mohl nástroj nastavit cookie: aktuální hostitel a všechny nadřazené (kromě TLD).
  function cookieDomains() {
    var host = window.location.hostname;
    var out = [''];
    if (!host || /^[0-9.]+$/.test(host) || host.indexOf(':') !== -1) return out; // IP adresa
    var parts = host.split('.');
    for (var i = 0; i < parts.length - 1; i++) out.push(parts.slice(i).join('.'));
    return out;
  }

  function deleteCookies(patterns) {
    var raw;
    try { raw = document.cookie || ''; } catch (e) { return; }
    var names = raw.split(';').map(function (c) {
      return c.split('=')[0].replace(/^\s+|\s+$/g, '');
    }).filter(function (name) {
      return name && patterns.some(function (re) { return re.test(name); });
    });
    if (!names.length) return;
    var domains = cookieDomains();
    names.forEach(function (name) {
      domains.forEach(function (d) {
        try {
          // GA i Meta ukládají cookies s path=/
          document.cookie = name + '=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/' +
            (d ? '; domain=' + d : '');
        } catch (e) { /* ignore */ }
      });
    });
  }

  // Načte, vypne nebo znovu zapne nástroje podle souhlasu. Vrací true, pokud je po odvolání
  // souhlasu potřeba stránku znovu načíst (jen při změně na této stránce: allowReload).
  function syncTrackers(allowReload) {
    var reload = false;
    for (var id in TRACKERS) {
      if (!Object.prototype.hasOwnProperty.call(TRACKERS, id)) continue;
      var t = TRACKERS[id];
      if (!t.enabled) continue;
      if (has(id)) {
        if (!t.loaded) {
          t.loaded = true;
          try { t.load(); } catch (e) { /* nástroj nesmí rozbít web */ }
        } else if (t.paused) {
          t.paused = false;
          try { t.resume(); } catch (e) { /* ignore */ }
        }
      } else {
        if (t.loaded && !t.paused) {
          t.paused = true;
          try { t.pause(); } catch (e) { /* ignore */ }
          if (allowReload) reload = true;
        }
        deleteCookies(t.cookies); // i staré cookies z dřívějšího (prošlého) souhlasu
      }
    }
    return reload;
  }

  var reloading = false;
  function scheduleReload() {
    if (reloading) return;
    reloading = true;
    window.setTimeout(function () { window.location.reload(); }, 0);
  }

  // Konverze ze site.js: nv:lead po odeslání formuláře, nv:booking jen po kliknutí na tlačítko vedoucí
  // na rezervaci, na „Souhlasím, načíst kalendář“ nebo na odkaz rezervace v novém okně (samotné načtení
  // kalendáře se nepočítá).
  // Detail události se záměrně nečte – žádná data z formuláře ani jiné údaje se nikam neposílají.
  function onConversion(kind) {
    for (var id in TRACKERS) {
      if (!Object.prototype.hasOwnProperty.call(TRACKERS, id)) continue;
      var t = TRACKERS[id];
      if (!t.enabled || !t.loaded || t.paused || !has(id)) continue;
      try { t[kind](); } catch (e) { /* ignore */ }
    }
  }

  /* ------------------------------------------------------------------ */
  /* Vkládaný obsah [data-consent-embed]                                 */
  /* ------------------------------------------------------------------ */

  function safeSrc(raw) {
    if (!raw) return null;
    try {
      var u = new URL(raw, window.location.href);
      return u.protocol === 'https:' ? u.href : null;
    } catch (e) {
      return null;
    }
  }

  function syncEmbeds() {
    var nodes = document.querySelectorAll('[data-consent-embed]');
    for (var i = 0; i < nodes.length; i++) {
      if (has(nodes[i].getAttribute('data-consent-embed'))) loadEmbed(nodes[i]);
      else unloadEmbed(nodes[i]);
    }
  }

  function loadEmbed(box) {
    if (box.getAttribute('data-consent-state') === 'loaded') return;
    var src = safeSrc(box.getAttribute('data-src'));
    if (!src) {
      box.setAttribute('data-consent-state', 'error');
      return;
    }
    var saved = [];
    while (box.firstChild) saved.push(box.removeChild(box.firstChild));
    placeholders.set(box, saved);

    var height = parseInt(box.getAttribute('data-height'), 10);
    if (!(height > 0)) height = DEFAULT_EMBED_HEIGHT;
    var frame = document.createElement('iframe');
    frame.className = 'nvc-embed-frame';
    frame.setAttribute('loading', 'lazy');
    frame.setAttribute('title', box.getAttribute('data-title') || 'Externí obsah');
    frame.style.cssText = 'display:block;width:100%;height:' + height + 'px;border:0';
    frame.setAttribute('src', src);
    box.appendChild(frame);
    box.setAttribute('data-consent-state', 'loaded');
  }

  function unloadEmbed(box) {
    if (box.getAttribute('data-consent-state') !== 'loaded') {
      if (!box.hasAttribute('data-consent-state')) box.setAttribute('data-consent-state', 'blocked');
      return;
    }
    while (box.firstChild) box.removeChild(box.firstChild);
    var saved = placeholders.get(box) || [];
    for (var i = 0; i < saved.length; i++) box.appendChild(saved[i]);
    placeholders['delete'](box);
    box.setAttribute('data-consent-state', 'blocked');
  }

  /* ------------------------------------------------------------------ */
  /* Lišta (nemodální, dole)                                             */
  /* ------------------------------------------------------------------ */

  // „a, b a c“
  function joinCs(items) {
    if (items.length < 2) return items.join('');
    return items.slice(0, -1).join(', ') + ' a ' + items[items.length - 1];
  }

  // Text lišty jmenuje jen nástroje, které jsou na webu opravdu zapnuté. Je záměrně krátký;
  // podrobnosti (poskytovatelé, cookies, společná odpovědnost s Metou) jsou v dialogu Nastavení.
  // Věta o výslovném souhlasu u Meta pixelu musí zůstat (čl. 9 GDPR: návštěva webu výživové poradkyně).
  function bannerText() {
    var tools = ['rezervační Kalendář Google'];
    if (TRACKERS.analytika.enabled) tools.push('Google Analytics k měření návštěvnosti');
    if (TRACKERS.marketing.enabled) tools.push('Meta pixel k měření reklam');
    var text = 'Se souhlasem web načte ' + joinCs(tools) + '. ';
    if (tools.length === 1) text += 'Kalendář ukládá vlastní cookies a zpracovává vaši IP adresu. ';
    if (TRACKERS.marketing.enabled) {
      text += 'Meta se tak dozví, že jste navštívili web výživové poradkyně, a může to spojit s vaším účtem – ' +
        'tlačítkem „Přijmout vše“ s tím výslovně souhlasíte. ';
    }
    return text + 'Volbu změníte kdykoli v Nastavení cookies v patičce. Více v ';
  }

  function buildBanner() {
    var measuring = TRACKERS.analytika.enabled || TRACKERS.marketing.enabled;
    var title = el('p', { 'class': 'nvc-banner__title' },
      measuring ? 'Cookies, externí obsah a měření' : 'Cookies a externí obsah');
    var text = el('p', { 'class': 'nvc-banner__text' }, [
      bannerText(),
      el('a', { href: COOKIES_URL }, 'zásadách cookies'),
      ' a ',
      el('a', { href: PRIVACY_URL }, 'zpracování osobních údajů'),
      '.'
    ]);
    var actions = el('div', { 'class': 'nvc-banner__actions' }, [
      button('Přijmout vše', 'primary', 'accept-all'),
      button('Odmítnout vše', 'primary', 'reject-all'),
      button('Nastavení', 'secondary', 'settings', { 'aria-haspopup': 'dialog' })
    ]);
    banner = el('div', { 'class': 'nvc-banner', role: 'region', 'aria-label': 'Souhlas s cookies', hidden: true },
      el('div', { 'class': 'nvc-banner__inner' }, [
        el('div', { 'class': 'nvc-banner__body' }, [title, text]),
        actions
      ]));
    banner.addEventListener('click', onAction);
    // Na začátek <body> (hned za odkaz „Přeskočit na obsah“, pokud tam je): klávesnice i čtečky
    // lištu najdou hned, vizuálně je dole.
    var ref = document.body.firstElementChild;
    while (ref && ref.classList.contains('skip-link')) ref = ref.nextElementSibling;
    document.body.insertBefore(banner, ref);
  }

  function measureBanner() {
    if (!banner || banner.hidden) return;
    root.style.setProperty('--nvc-banner-h', Math.ceil(banner.getBoundingClientRect().height) + 'px');
  }

  function showBanner() {
    if (!document.body) return;
    if (!banner) buildBanner();
    if (!banner.hidden) return;
    banner.hidden = false;
    root.classList.add('nvc-has-banner');
    measureBanner();
    if (typeof ResizeObserver === 'function') {
      if (!resizeObs) resizeObs = new ResizeObserver(measureBanner);
      resizeObs.observe(banner);
    } else {
      window.addEventListener('resize', measureBanner);
    }
  }

  function hideBanner() {
    if (!banner || banner.hidden) return;
    banner.hidden = true;
    root.classList.remove('nvc-has-banner');
    root.style.removeProperty('--nvc-banner-h');
    if (resizeObs) resizeObs.disconnect();
    else window.removeEventListener('resize', measureBanner);
  }

  /* ------------------------------------------------------------------ */
  /* Dialog s nastavením                                                 */
  /* ------------------------------------------------------------------ */

  function buildCategory(c) {
    var id = 'nvc-cat-' + c.id;
    var input = el('input', {
      type: 'checkbox', role: 'switch', id: id, 'class': 'nvc-switch',
      'aria-describedby': id + '-desc' + (c.meta ? ' ' + id + '-meta' : ''), 'data-nvc-cat': c.id
    });
    if (c.required) {
      input.checked = true;
      input.disabled = true;
    }
    switches[c.id] = input;
    var state = el('span', {
      'class': 'nvc-cat__state' + (c.required ? ' nvc-cat__state--always' : ''),
      'aria-hidden': c.required ? null : 'true'
    }, c.required ? 'Vždy aktivní' : 'Vypnuto');
    stateLabels[c.id] = state;
    return el('div', { 'class': 'nvc-cat' + (c.required ? ' nvc-cat--required' : '') }, [
      el('div', { 'class': 'nvc-cat__head' }, [
        el('label', { 'class': 'nvc-cat__label', 'for': id }, c.title),
        state,
        input
      ]),
      el('p', { 'class': 'nvc-cat__desc', id: id + '-desc' }, c.description),
      c.meta ? el('p', { 'class': 'nvc-cat__meta', id: id + '-meta' }, c.meta) : null
    ]);
  }

  function buildDialog() {
    dialog = el('dialog', {
      'class': 'nvc-dialog', id: 'nvc-settings',
      'aria-labelledby': 'nvc-dialog-title', 'aria-describedby': 'nvc-dialog-intro'
    });
    var header = el('div', { 'class': 'nvc-dialog__header' }, [
      el('h2', { 'class': 'nvc-dialog__title', id: 'nvc-dialog-title' }, 'Nastavení cookies'),
      el('button', { type: 'button', 'class': 'nvc-dialog__close', 'data-nvc-action': 'close', 'aria-label': 'Zavřít bez uložení' }, closeIcon())
    ]);
    var intro = el('p', { 'class': 'nvc-dialog__intro', id: 'nvc-dialog-intro' },
      'Vyberte, co smí web kromě nezbytného úložiště načíst. Souhlas můžete kdykoli změnit nebo odvolat ' +
      'stejně snadno, jako jste ho udělili. Odvolání se nedotkne ničeho, co proběhlo před ním.');
    var list = el('div', { 'class': 'nvc-cats' }, CATEGORIES.map(buildCategory));
    statusEl = el('p', { 'class': 'nvc-dialog__status' });
    var more = el('p', { 'class': 'nvc-dialog__more' }, [
      'Podrobnosti najdete v ',
      el('a', { href: COOKIES_URL }, 'zásadách používání cookies'),
      ' a ',
      el('a', { href: PRIVACY_URL }, 'zásadách zpracování osobních údajů'),
      '.'
    ]);
    var body = el('div', { 'class': 'nvc-dialog__body' }, [header, intro, list, statusEl, more]);
    var footer = el('div', { 'class': 'nvc-dialog__footer' }, [
      button('Uložit výběr', 'secondary', 'save'),
      button('Přijmout vše', 'primary', 'accept-all'),
      button('Odmítnout vše', 'primary', 'reject-all')
    ]);
    append(dialog, [body, footer]);

    dialog.addEventListener('mousedown', function (e) {
      downOnBackdrop = e.target === dialog && outsideDialog(e);
    });
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog && downOnBackdrop && outsideDialog(e)) {
        downOnBackdrop = false;
        closeDialog();
        return;
      }
      onAction(e);
    });
    dialog.addEventListener('change', updateStateLabels);
    dialog.addEventListener('close', onDialogClose);
    document.body.appendChild(dialog);
  }

  function outsideDialog(e) {
    var r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  }

  function updateStateLabels() {
    optionalCats().forEach(function (c) {
      var s = switches[c.id];
      var label = stateLabels[c.id];
      if (!s || !label) return;
      label.textContent = s.checked ? 'Zapnuto' : 'Vypnuto';
      label.classList.toggle('nvc-cat__state--on', s.checked);
    });
  }

  function syncDialog() {
    if (!dialog) return;
    optionalCats().forEach(function (c) {
      if (switches[c.id]) switches[c.id].checked = has(c.id);
    });
    updateStateLabels();
    if (current) {
      var ts = Date.parse(current.ts);
      statusEl.textContent = typo('Vaše volba je uložená od ' + formatDate(ts) + ' a platí do ' +
        formatDate(addMonths(ts, MAX_AGE_MONTHS)) + '. Potom se vás web zeptá znovu.');
    } else {
      statusEl.textContent = typo('Zatím nemáte uloženou žádnou volbu. Dokud ji neuložíte, web nenačte nic ' +
        'z volitelných kategorií.');
    }
  }

  function readSwitches() {
    var out = {};
    optionalCats().forEach(function (c) { out[c.id] = !!(switches[c.id] && switches[c.id].checked); });
    return out;
  }

  function isDialogOpen() {
    return !!dialog && dialog.hasAttribute('open');
  }

  function openSettings(from) {
    if (!document.body) return;
    if (!dialog) buildDialog();
    syncDialog();
    if (isDialogOpen()) return;
    opener = from && from.nodeType === 1 ? from : document.activeElement;
    if (typeof dialog.showModal === 'function') {
      try {
        dialog.showModal();
      } catch (e) {
        dialog.setAttribute('open', '');
      }
    } else {
      dialog.classList.add('nvc-dialog--fallback');
      dialog.setAttribute('open', '');
    }
    var first = null;
    for (var i = 0; i < CATEGORIES.length && !first; i++) {
      var s = switches[CATEGORIES[i].id];
      if (s && !s.disabled) first = s;
    }
    focusQuietly(first);
  }

  function closeDialog() {
    if (!isDialogOpen()) return;
    if (typeof dialog.close === 'function' && !dialog.classList.contains('nvc-dialog--fallback')) {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
      onDialogClose();
    }
  }

  function onDialogClose() {
    var target = opener;
    opener = null;
    if (target && document.contains(target) && isVisible(target)) focusQuietly(target);
    else focusMainFallback(); // dialog otevřený z lišty, která se mezitím skryla
  }

  /* ------------------------------------------------------------------ */
  /* Události                                                            */
  /* ------------------------------------------------------------------ */

  function onAction(e) {
    var t = e.target;
    var b = t && typeof t.closest === 'function' ? t.closest('[data-nvc-action]') : null;
    if (!b) return;
    var focusInBanner = !!banner && banner.contains(document.activeElement);
    switch (b.getAttribute('data-nvc-action')) {
      case 'accept-all': setAll(true); closeDialog(); break;
      case 'reject-all': setAll(false); closeDialog(); break;
      case 'save': commit(readSwitches()); closeDialog(); break;
      case 'settings': openSettings(b); break;
      case 'close': closeDialog(); break;
    }
    if (focusInBanner && banner.hidden && !isDialogOpen()) focusMainFallback();
  }

  function onDocumentClick(e) {
    var t = e.target;
    if (!t || typeof t.closest !== 'function') return;
    var openBtn = t.closest('[data-consent-open]');
    if (openBtn) {
      e.preventDefault();
      openSettings(openBtn);
      return;
    }
    var acceptBtn = t.closest('[data-consent-accept]');
    if (acceptBtn) {
      var id = acceptBtn.getAttribute('data-consent-accept');
      if (!findCat(id)) return;
      e.preventDefault();
      var box = acceptBtn.closest('[data-consent-embed]');
      api.grant(id);
      var frame = box && box.querySelector('iframe');
      if (frame) focusQuietly(frame); // tlačítko zmizelo – fokus přesuneme na načtený obsah
    }
  }

  function onKeydown(e) {
    // Jen pro prohlížeče bez nativního <dialog> (nativní dialog zavírá Escape sám).
    if ((e.key === 'Escape' || e.key === 'Esc') && dialog && dialog.classList.contains('nvc-dialog--fallback') && isDialogOpen()) {
      closeDialog();
    }
  }

  function onStorage(e) {
    if (e.key !== null && e.key !== STORAGE_KEY) return;
    current = loadStored();
    applyState(true, true);
  }

  function onPageShow(e) {
    if (!e.persisted) return;
    var rec = loadStored();
    if (JSON.stringify(rec) !== JSON.stringify(current)) {
      current = rec;
      applyState(true, true);
    }
  }

  function onLead() { onConversion('lead'); }
  function onBooking() { onConversion('booking'); }

  /* ------------------------------------------------------------------ */
  /* Veřejné API                                                         */
  /* ------------------------------------------------------------------ */

  var api = {
    __nvc: true,
    version: VERSION,
    categories: CATEGORIES.map(function (c) { return { id: c.id, required: c.required, title: c.title }; }),
    has: has,
    get: function () {
      return current ? { v: current.v, ts: current.ts, categories: copy(current.categories) } : null;
    },
    grant: function (id) {
      var c = findCat(id);
      if (!c) return false;
      if (!c.required) {
        var cats = effective();
        cats[id] = true;
        commit(cats);
      }
      return true;
    },
    revoke: function (id) {
      var c = findCat(id);
      if (!c || c.required) return false;
      var cats = effective();
      cats[id] = false;
      commit(cats);
      return true;
    },
    set: function (obj) {
      var src = obj && typeof obj === 'object' ? obj : {};
      if (src.categories && typeof src.categories === 'object') src = src.categories;
      var cats = effective();
      optionalCats().forEach(function (c) {
        if (typeof src[c.id] === 'boolean') cats[c.id] = src[c.id];
      });
      return commit(cats);
    },
    openSettings: function (from) { openSettings(from); },
    refresh: function () { syncEmbeds(); }
  };

  /* ------------------------------------------------------------------ */
  /* Start                                                               */
  /* ------------------------------------------------------------------ */

  function init() {
    if (ready) return;
    ready = true;
    document.addEventListener('click', onDocumentClick);
    document.addEventListener('keydown', onKeydown);
    window.addEventListener('storage', onStorage);
    window.addEventListener('pageshow', onPageShow);
    syncTrackers(false); // měření jen s uloženým souhlasem; bez něj jen úklid starých cookies
    syncEmbeds();
    if (current) dispatch();
    else showBanner();
  }

  current = loadStored();
  window.nvConsent = api;
  document.addEventListener('nv:lead', onLead);
  document.addEventListener('nv:booking', onBooking);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
