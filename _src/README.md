# Nutrivero – web (poznámky pro správu)

Statický web bez frameworku. Všechny texty se upravují v `_src/` a hotové stránky vygeneruje skript
`_src/build.py`. Web má dva cíle nasazení:

| Cíl | Kde běží | Adresa | Indexace |
|---|---|---|---|
| `preview` (výchozí) | GitHub Pages, veřejný repozitář `OndrejKamaryt/nutrivero-nahled` | https://ondrejkamaryt.github.io/nutrivero-nahled/ (podsložka `/nutrivero-nahled`) | **ne** – `noindex,nofollow` |
| `production` | vlastní doména v kořeni (Netlify nebo jiný hosting) | https://nutrivero.cz/ | ano – `index,follow` |

Přepnutí mezi náhledem a ostrým webem je jen otázka buildu s jiným `--target` – zdrojové soubory
se nemění.

## Struktura složek

```
_src/                    zdroje – TADY se edituje
  config.json            hodnoty tokenů: společné + "targets" (preview / production)
  build.py               sestaví HTML, robots.txt a sitemap.xml (sitemap jen u ostrého webu)
  index.html             hlavní stránka
  page-template.html     společná šablona podstránek (hlavička, patička, <head>)
  404.html               stránka „nenalezeno“
  legal/*.html           obsah právních stránek (GDPR, cookies, obchodní podmínky, odstoupení)
  robots.txt             robots.txt ostrého webu (povoleno + odkaz na sitemap)
  robots-preview.txt     robots.txt náhledu (Disallow: /)
  sitemap.xml            šablona sitemap s tokeny (jen ostrý web; náhled sitemap nemá)
site/                    statické soubory + výchozí výstup buildu (HTML v site/ needitujte, build ho přepíše)
  .nojekyll              GitHub Pages: nezpracovávat web Jekyllem
  _headers               HTTP hlavičky pro Netlify (CSP, HSTS, cache …) – jen ostrý web
  _redirects             301 přesměrování starých/krátkých adres (/gdpr, /vop …) – jen Netlify
  site.webmanifest, favicon.ico, apple-touch-icon.png
  assets/css/            fonts.css (DM Sans, hostováno lokálně), site.css, consent.css
  assets/js/             site.js, consent.js (cookie lišta a nastavení)
  assets/fonts/          DM Sans (woff2) + licence OFL
  assets/img/            fotky (webp/jpg), ikony, icons/, og-image-2.jpg (náhled pro sociální sítě,
                         1200×630; starší og-image.jpg smažte, až na něj nebude nic odkazovat)
nutrivero-web-hotov/     původní návrh (prototyp) – jen pro referenci, nenasazuje se
```

## Úprava textů

- Hlavní stránka a podstránky: upravte příslušný soubor v `_src/` (nikoli v `site/`).
- Právní texty: `_src/legal/<adresa>.html`. První řádek je komentář `<!--meta {...} -->` s titulkem,
  popisem pro vyhledávače, nadpisem H1 a úvodní větou – při změně zachovejte platný JSON.
- Při podstatné změně právních textů změňte v `config.json` datum `UPDATED` (formát `30. 10. 2026`).
  Při podstatné změně obsahu hlavní stránky změňte `HOME_UPDATED_ISO` (formát `2026-10-30`).
  Obě data jsou `lastmod` v sitemap – měňte je jen při skutečné změně obsahu, ne při každém buildu.
- Hosting v právních textech uvádějte **jen tokeny** `%%HOSTING_NAME%%`, `%%HOSTING_SERVICE%%`,
  `%%HOSTING_ADDRESS%%`, `%%HOSTING_PRIVACY_URL%%` – náhled tak uvede GitHub, ostrý web Netlify.
- Odkazy a obrázky pište jako kořenové cesty (`/cookies/`, `/assets/img/…`). Build před ně u náhledu
  sám doplní `/nutrivero-nahled` (atributy `href`, `src`, `srcset`, `imagesrcset`, `poster`, `action`,
  `data-src`). Inline `style="…url(/…)"` nepoužívejte – v podsložce by nefungoval (build ho odmítne).
  V CSS používejte cesty relativní k CSS souboru (`url(../fonts/…)`).
- Česká typografie: za jednopísmennými předložkami a spojkami (k, s, v, z, o, u, i, a) a mezi číslem
  a jednotkou (2 900&nbsp;Kč, 30&nbsp;minut) používejte nezlomitelnou mezeru `&nbsp;`.
- Po každé změně spusťte build (viz níže) a zkontrolujte výsledek.

## Tokeny a config.json

V textech se píšou tokeny `%%NAZEV%%`, build je nahradí hodnotami z `_src/config.json`.
Kořen `config.json` obsahuje **společné** hodnoty, `targets.preview` a `targets.production` hodnoty
**cíle**, které společné doplní nebo přepíšou. `TARGET` určuje výchozí cíl (`"preview"`).
Klíče začínající `_` jsou komentáře.

| Token | Kde | Význam |
|---|---|---|
| `%%JMENO%%` | společné | jméno provozovatelky |
| `%%ICO%%` | společné | IČO |
| `%%ADRESA%%` | společné | místo podnikání |
| `%%EMAIL%%` | společné | kontaktní e-mail (i pro odkazy `mailto:`) |
| `%%TELEFON%%` | společné | telefon pro zobrazení, např. `+420 777 123 456` |
| `%%TELEFON_HREF%%` | společné | telefon pro odkaz `tel:`, bez mezer, např. `+420777123456` |
| `%%UPDATED%%` | společné | datum účinnosti právních textů (formát `26. 10. 2026`) |
| `%%HOME_UPDATED_ISO%%` | společné | datum poslední podstatné změny hlavní stránky, `RRRR-MM-DD` (`lastmod` v sitemap) |
| `%%REZERVACE_URL%%` | společné | rezervační stránka Google Kalendáře pro vložení (s `?gv=true`) |
| `%%REZERVACE_LINK%%` | společné | stejná adresa bez `gv` – odkaz „otevřít v novém okně“ |
| `%%SITE_URL%%` | cíl | adresa webu bez koncového lomítka, včetně podsložky (kanonické URL, sitemap, OG) |
| `%%BASE_PATH%%` | cíl | podsložka, ve které web běží: `/nutrivero-nahled` u náhledu, `""` u ostrého webu |
| `PREVIEW` | cíl | `true` = náhled (noindex), `false` = ostrý web; není to token, řídí `%%ROBOTS%%` |
| `%%HOSTING_NAME%%` | cíl | provozovatel hostingu (`GitHub, Inc.` / `Netlify, Inc.`) |
| `%%HOSTING_SERVICE%%` | cíl | název služby (`GitHub Pages` / `Netlify`) |
| `%%HOSTING_ADDRESS%%` | cíl | adresa provozovatele hostingu |
| `%%HOSTING_PRIVACY_URL%%` | cíl | odkaz na jeho zásady ochrany osobních údajů |
| `%%ROBOTS%%` | build | `noindex,nofollow` (náhled) / `index,follow` (ostrý web) |
| `%%ROBOTS_404%%` | build | robots stránky 404: `noindex,nofollow` (náhled) / `noindex,follow` (ostrý web) |
| `%%UPDATED_ISO%%` | build | `UPDATED` ve tvaru `RRRR-MM-DD` (`lastmod` právních stránek v sitemap) |
| `%%BUILD_DATE%%` | build | datum buildu (`RRRR-MM-DD`); do sitemap se nepoužívá |

Cesta v `SITE_URL` musí odpovídat `BASE_PATH`, jinak build skončí chybou.

**Před ostrým spuštěním** nahraďte v `config.json` zástupné hodnoty `[e-mail]`, `[telefon]`
a `TELEFON_HREF` (`+420000000000`) skutečnými údaji – build s `--strict` je jinak odmítne.

## Build

Spouštějte z kořenové složky projektu:

```
python _src/build.py --target preview                    # náhled (výchozí cíl) → site/
python _src/build.py --target production --strict        # ostrý web → site/; zástupné hodnoty = chyba
python _src/build.py --target preview --out ../nutrivero-nahled
                                                          # kompletní web do jiné složky
```

- `--target preview|production` – cíl (výchozí podle `TARGET` v `config.json`).
- `--out SLOŽKA` – výstup jinam než do `site/`. Do takové složky build zkopíruje i statické soubory
  ze `site/` (`assets/`, `favicon.ico`, `apple-touch-icon.png`, `site.webmanifest`, `.nojekyll`;
  u ostrého webu navíc `_headers` a `_redirects`), takže vznikne kompletní web k nahrání.
- `--strict` – zástupné hodnoty v `config.json` jsou chyba (vždy před ostrým nasazením).

Build selže a nic nezapíše, pokud ve výstupu zůstane `%%…%%` nebo `{{…}}`, JSON-LD není platný JSON,
náhled nemá `noindex`, `SITE_URL` neodpovídá `BASE_PATH` nebo `UPDATED` / `HOME_UPDATED_ISO`
nejsou platná data.

Pozor: `site/` je zároveň zdroj statických souborů i výchozí výstup. HTML v `site/` odpovídá
poslednímu buildu – po buildu náhledu má cesty s `/nutrivero-nahled/…`, po buildu ostrého webu
cesty od kořene.

### Lokální náhled

- Ostrý web: `python _src/build.py --target production --out <dočasná složka>` a pak
  `python -m http.server 8080 --directory <dočasná složka>` → http://localhost:8080/
- Náhled (běží v podsložce): `python _src/build.py --target preview --out <dočasná složka>/nutrivero-nahled`,
  pak `python -m http.server 8080 --directory <dočasná složka>` → http://localhost:8080/nutrivero-nahled/

Hlavičky z `_headers` a přesměrování z `_redirects` lokálně ani na GitHub Pages nefungují
(jen na Netlify, případně přes `netlify dev`). Základní CSP je proto zapsaná i přímo v `<head>`
každé stránky (`<meta http-equiv="Content-Security-Policy">`) spolu s `<meta name="referrer">`.

## Náhled na GitHub Pages (repozitář nutrivero-nahled)

Celý projekt (`_src/`, `site/`) je ve veřejném repozitáři `OndrejKamaryt/nutrivero-nahled`.
GitHub Pages je nastavené na zdroj **GitHub Actions**: workflow `.github/workflows/pages.yml`
při každém pushi do `main` spustí `python _src/build.py --target preview --out _dist`
a složku `_dist` nasadí.

Každá aktualizace náhledu:

```
git add -A
git commit -m "Aktualizace náhledu"
git push
```

Po pár minutách je náhled na https://ondrejkamaryt.github.io/nutrivero-nahled/
(průběh: záložka Actions v repozitáři).

- Repozitář je veřejný (GitHub Pages zdarma to vyžaduje) – obsahuje zdroje i `config.json`;
  nedávejte do nich nic, co nemá být veřejné. Podklady z Claude Design (`nutrivero-web-hotov/`)
  jsou v `.gitignore`.
- `.nojekyll` vypíná zpracování Jekyllem (web se zveřejní přesně tak, jak je).
- Neznámé adresy GitHub Pages obslouží souborem `404.html` (se stavem 404); stránka 404 používá
  absolutní cesty s `/nutrivero-nahled/`, takže se zobrazí správně i v hlubší cestě.
- Do náhledu se **nekopírují** `_headers` ani `_redirects` (GitHub Pages je nepoužívá). Pokud ve
  složce zůstaly z dřívějška, build upozorní – smažte je. Na GitHub Pages proto nefungují HSTS,
  `frame-ancestors`/`X-Frame-Options`, `Permissions-Policy` ani přesměrování `/gdpr`, `/vop` …
  Pro náhled to nevadí; ostrý web je má z `_headers` na Netlify.

### Náhled se neindexuje

- Každá stránka náhledu má `<meta name="robots" content="noindex,nofollow">` (build to kontroluje).
- `robots.txt` náhledu obsahuje `Disallow: /` a neodkazuje na sitemap. Vyhledávače ale čtou
  `robots.txt` jen z kořene domény (`ondrejkamaryt.github.io/robots.txt`), u webu v podsložce proto
  indexaci spolehlivě blokuje hlavně meta značka `noindex`.
- `canonical` a `og:url` náhledu ukazují na adresu náhledu (`SITE_URL` cíle preview).
- Náhled **nemá `sitemap.xml`** (seznam adres s `noindex` by si odporoval). Starou `sitemap.xml`
  z dřívějšího buildu ostrého webu build náhledu ve výstupní složce smaže.
- Ostrý build (`--target production`) přepne vše na `index,follow`, běžný `robots.txt` se sitemap
  a adresy `https://nutrivero.cz/…`.

## Ostrý web na Netlify (cíl production)

Jednorázově: `npm install -g netlify-cli`, pak `netlify login` a `netlify link` (nebo při prvním
`netlify deploy` zvolte „Create & configure a new site“).

```
python _src/build.py --target production --strict --out ../nutrivero-produkce
netlify deploy --dir ../nutrivero-produkce          # náhledová verze (draft URL) ke kontrole
netlify deploy --prod --dir ../nutrivero-produkce   # ostrá verze
```

(Lze buildovat i přímo do `site/` – `python _src/build.py --target production --strict` – a nasadit
`site/`.) Alternativa bez CLI: v administraci Netlify → Deploys přetáhněte celou výstupní složku.
Nasazuje se vždy celá složka – včetně souborů `_headers` a `_redirects`.

Pokud ostrý web poběží jinde než na Netlify, upravte v `config.json` → `targets.production` hodnoty
`HOSTING_*` (promítnou se do právních textů) a nastavte hlavičky z `site/_headers` u nového hostingu.

Cache: obrázky a fonty mají cache na 1 rok (`immutable`). Když obrázek měníte, **uložte ho pod novým
názvem** (např. `og-image-3.jpg`) a upravte odkazy, jinak se návštěvníkům může zobrazovat starý.
CSS a JS mají cache 1 hodinu.

## Vlastní doména u Webglobe

1. Netlify → Site configuration → Domain management → **Add a domain** → zadejte `nutrivero.cz`
   (Netlify přidá i `www.nutrivero.cz`). Zvolte, která varianta je primární.
2. **Varianta A – DNS zůstává u Webglobe (doporučeno, pokud u Webglobe běží e-mail):**
   v administraci Webglobe → Domény → DNS záznamy nastavte
   - `A` záznam pro kořen domény (`@` / prázdný název) → `75.2.60.5` (load balancer Netlify),
   - `CNAME` pro `www` → `<nazev-webu>.netlify.app.` (název najdete v Netlify, např. `nutrivero.netlify.app`),
   - smažte staré `A`/`AAAA` záznamy pro `@` a `www`, které ukazují jinam (např. na parkovací stránku).
   MX a TXT záznamy (e-mail, SPF, DKIM) neměňte.
3. **Varianta B – Netlify DNS:** v Netlify zvolte „Set up Netlify DNS“, u Webglobe změňte nameservery
   na ty, které Netlify zobrazí. Předtím v Netlify DNS ručně založte všechny MX/TXT záznamy pro e-mail,
   jinak přestane chodit pošta.
4. Po propagaci DNS (minuty až hodiny) Netlify automaticky vystaví certifikát Let's Encrypt;
   v Domain management → HTTPS ověřte, že je certifikát aktivní.
5. Ověřte, že `SITE_URL` v `config.json` → `targets.production` je primární doména
   (`https://nutrivero.cz`, případně `https://www.nutrivero.cz`), spusťte build ostrého webu a znovu
   nasaďte – jinak budou kanonické adresy, sitemap a náhledy pro sítě ukazovat jinam.
6. Ověřte, že `https://<nazev-webu>.netlify.app` přesměrovává na vlastní doménu; pokud ne, přidejte na
   začátek `site/_redirects` řádek
   `https://<nazev-webu>.netlify.app/*  https://nutrivero.cz/:splat  301!`
7. Volitelně: Google Search Console → přidat doménu → odeslat `https://nutrivero.cz/sitemap.xml`.

Pozn.: hlavička HSTS v `_headers` obsahuje `includeSubDomains` – všechny subdomény `nutrivero.cz`
pak musí fungovat přes HTTPS.

## Přidání analytiky později (cookie lišta)

Web dnes žádnou analytiku ani marketingové nástroje nepoužívá, proto má lišta jen kategorie
„nezbytné“ a „externí obsah“ (Google Kalendář). Při přidání analytiky:

1. **Zvažte nástroj bez cookies** (serverová statistika Netlify Analytics nebo cookieless měření) –
   pak není potřeba nová kategorie souhlasu, stačí doplnit informace do zásad.
2. Jinak v `site/assets/js/consent.js` přidejte kategorii, např. `analyticke` (název, popis, výchozí
   hodnota `false`), aby se zobrazila v nastavení i v liště.
3. Zvyšte verzi uloženého souhlasu `v` (např. z `1` na `2`) a staré záznamy s nižší verzí považujte za
   neplatné – návštěvníci tak budou znovu požádáni o souhlas s novým účelem.
4. Skript analytiky načítejte až po souhlasu, a to ze samostatného souboru (inline skripty CSP zakazuje),
   např. `site/assets/js/analytics.js` vložený na stránky za `consent.js`:

   ```js
   (function () {
     var loaded = false;
     function load() {
       if (loaded) return; loaded = true;
       var s = document.createElement('script');
       s.src = 'https://analytika.example/script.js'; s.defer = true;
       document.head.appendChild(s);
     }
     if (window.nvConsent && window.nvConsent.has('analyticke')) load();
     document.addEventListener('nv:consent', function (e) {
       if (e.detail && e.detail.analyticke) load();
     });
   })();
   ```
   (Při odvolání souhlasu nástroj vypněte / smažte jeho cookies, nejjednodušeji reloadem stránky.)
5. Rozšiřte CSP o domény nástroje (`script-src`, `connect-src`, případně `img-src`) **na obou místech**:
   v `site/_headers` i v `<meta http-equiv="Content-Security-Policy">` v `_src/index.html`,
   `_src/page-template.html` a `_src/404.html` (platí obě, prohlížeč použije přísnější).
6. Aktualizujte `_src/legal/cookies.html` (tabulka cookies) a `_src/legal/ochrana-osobnich-udaju.html`
   (účel, příjemci, předávání mimo EU), změňte `UPDATED` v `config.json`, spusťte build a nasaďte.
