# Nutrivero – web (poznámky pro správu)

Statický web bez frameworku. Všechny texty se upravují v `_src/` a hotové stránky vygeneruje skript
`_src/build.py`. Web má tři cíle nasazení:

> **Stav od 30. 10. 2026:** ostrý web běží na https://nutrivero.cz/ (cíl `production`, v `config.json`
> nastavený jako výchozí `TARGET`; Netlify, web `nutrivero-nahled` s připojenou doménou). Aktuální stav
> nasazení, DNS, e-mailu a Search Console popisuje `README.md` v kořeni projektu – má přednost před
> staršími poznámkami o náhledech níže.

| Cíl | Kde běží | Adresa | Indexace | Kontaktní formulář |
|---|---|---|---|---|
| `netlify-nahled` | Netlify, web `nutrivero-nahled` (ID `0e049152-4ae2-4324-a1bf-d60fa1261180`), v kořeni | https://nutrivero-nahled.netlify.app/ | **ne** – `noindex,nofollow` | ano (Netlify Forms) |
| `preview` | GitHub Pages, veřejný repozitář `OndrejKamaryt/nutrivero-nahled` | https://ondrejkamaryt.github.io/nutrivero-nahled/ (podsložka `/nutrivero-nahled`) | **ne** – `noindex,nofollow` | **ne** – odeslání skončí chybou s odkazem na e-mail |
| `production` (výchozí) | Netlify, web `nutrivero-nahled` s vlastní doménou, v kořeni (ostrý od 30. 10. 2026) | https://nutrivero.cz/ | ano – `index,follow` | ano (Netlify Forms) |

Přepnutí mezi náhledem a ostrým webem je jen otázka buildu s jiným `--target` – zdrojové soubory
se nemění. Náhled na GitHub Pages zatím zůstává (nasazuje ho GitHub Actions), ale kontaktní formulář
na něm nefunguje – GitHub Pages neumí přijímat odeslané formuláře.

## Struktura složek

```
_src/                    zdroje – TADY se edituje
  config.json            hodnoty tokenů: společné + "targets" (netlify-nahled / preview / production)
  build.py               sestaví HTML, robots.txt a sitemap.xml (sitemap jen u ostrého webu)
  index.html             hlavní stránka (včetně kontaktního formuláře)
  page-template.html     společná šablona podstránek (hlavička, patička, <head>)
  404.html               stránka „nenalezeno“
  legal/*.html           obsah podstránek: právní texty (GDPR, cookies, obchodní podmínky, odstoupení)
                         a dekujeme.html (poděkování po odeslání formuláře bez JavaScriptu, noindex)
  robots.txt             robots.txt ostrého webu (povoleno + odkaz na sitemap)
  robots-preview.txt     robots.txt náhledu (Disallow: /)
  sitemap.xml            šablona sitemap s tokeny (jen ostrý web; náhled sitemap nemá)
site/                    statické soubory + výchozí výstup buildu (HTML v site/ needitujte, build ho přepíše)
  .nojekyll              GitHub Pages: nezpracovávat web Jekyllem (kopíruje se jen do cíle preview)
  _headers               HTTP hlavičky pro Netlify (CSP, HSTS, cache …) – jen cíle s NETLIFY true
  _redirects             301 přesměrování starých/krátkých adres (/gdpr, /vop …) – jen cíle s NETLIFY true
  site.webmanifest, favicon.ico, apple-touch-icon.png
  assets/css/            fonts.css (DM Sans, hostováno lokálně), site.css, consent.css
  assets/js/             site.js, consent.js (cookie lišta a nastavení)
  assets/fonts/          DM Sans (woff2) + licence OFL
  assets/img/            fotky (webp/jpg), ikony, icons/, og-image-3.jpg (náhled pro sociální sítě,
                         1200×630; starší og-image-2.jpg a og-image.jpg smažte, až na ně nebude nic odkazovat)
nutrivero-web-hotov/     původní návrh (prototyp) – jen pro referenci, nenasazuje se
```

## Úprava textů

- Hlavní stránka a podstránky: upravte příslušný soubor v `_src/` (nikoli v `site/`).
- Právní texty a další podstránky: `_src/legal/<adresa>.html`. První řádek je komentář `<!--meta {...} -->`
  s titulkem, popisem pro vyhledávače, nadpisem H1 a úvodní větou – při změně zachovejte platný JSON.
  Volitelně:
  - `"robots": "noindex,nofollow"` – vlastní robots stránky (jinak platí `%%ROBOTS%%` cíle). Uplatní se jen
    u ostrého webu; náhledy mají vždy `noindex,nofollow`.
  - `"sitemap": false` – stránka nemá být v sitemap ostrého webu (např. `dekujeme.html`).

  Seznam adres v `_src/sitemap.xml` je psaný ručně. Build ho u ostrého webu porovná se stránkami:
  stránka se `"sitemap": false` nebo s `noindex` v sitemap = **chyba**, indexovatelná stránka, která
  v sitemap chybí, = upozornění. Novou indexovatelnou podstránku proto doplňte i do `_src/sitemap.xml`.
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
  a jednotkou (3 900&nbsp;Kč, 30&nbsp;minut) používejte nezlomitelnou mezeru `&nbsp;`.
- Po každé změně spusťte build (viz níže) a zkontrolujte výsledek.

## Tokeny a config.json

V textech se píšou tokeny `%%NAZEV%%`, build je nahradí hodnotami z `_src/config.json`.
Kořen `config.json` obsahuje **společné** hodnoty, `targets.netlify-nahled`, `targets.preview`
a `targets.production` hodnoty **cíle**, které společné doplní nebo přepíšou. `TARGET` určuje výchozí
cíl (`"production"`). Klíče začínající `_` jsou komentáře.

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
| `%%BASE_PATH%%` | cíl | podsložka, ve které web běží: `/nutrivero-nahled` u náhledu na GitHub Pages, `""` na Netlify (náhled i ostrý web) |
| `PREVIEW` | cíl | `true` = náhled (noindex, `robots.txt` s `Disallow: /`, bez sitemap), `false` = ostrý web; není to token, řídí `%%ROBOTS%%` |
| `NETLIFY` | cíl | `true` = web běží na Netlify: build do výstupu zkopíruje `_headers` a `_redirects` (u náhledu do `_headers` připíše `X-Robots-Tag: noindex, nofollow`) a funguje kontaktní formulář; `false` = GitHub Pages (kopíruje se `.nojekyll`). Není to token |
| `%%HOSTING_NAME%%` | cíl | provozovatel hostingu (`Netlify, Inc.` / `GitHub, Inc.`) |
| `%%HOSTING_SERVICE%%` | cíl | název služby (`Netlify` / `GitHub Pages`) |
| `%%HOSTING_ADDRESS%%` | cíl | adresa provozovatele hostingu |
| `%%HOSTING_PRIVACY_URL%%` | cíl | odkaz na jeho zásady ochrany osobních údajů |
| `%%ROBOTS%%` | build | `noindex,nofollow` (náhled) / `index,follow` (ostrý web); u podstránky ho může přepsat `"robots"` v meta |
| `%%ROBOTS_404%%` | build | robots stránky 404: `noindex,nofollow` (náhled) / `noindex,follow` (ostrý web) |
| `%%UPDATED_ISO%%` | build | `UPDATED` ve tvaru `RRRR-MM-DD` (`lastmod` právních stránek v sitemap) |
| `%%BUILD_DATE%%` | build | datum buildu (`RRRR-MM-DD`); do sitemap se nepoužívá |

Cesta v `SITE_URL` musí odpovídat `BASE_PATH`, jinak build skončí chybou.

Build s `--strict` odmítne zástupné hodnoty začínající `[` (např. `[e-mail]`); používejte ho před ostrým spuštěním.

### Kontaktní formulář (Netlify Forms)

- Formulář v sekci `#kontakt` (`_src/index.html`) zpracovává **Netlify Forms**: Netlify ho při každém
  nasazení najde v hotovém HTML (atributy `data-netlify="true"` a `name="kontakt"`), zprávy ukládá
  a posílá upozornění e-mailem. Žádná další služba ani klíč v `config.json` není potřeba.
- S JavaScriptem odešle `site/assets/js/site.js` formulář AJAXem (`POST /`, `application/x-www-form-urlencoded`)
  a poděkování se ukáže přímo na stránce; při chybě nebo po 20 s bez odpovědi se zobrazí výzva napsat
  na e-mail. Bez JavaScriptu se formulář odešle klasicky na `/dekujeme/` (stránka `_src/legal/dekujeme.html`,
  `noindex`, není v sitemap).
- Názvy polí jsou klíče v Netlify – **neměňte je**: `jmeno` (titulek zprávy v Netlify, musí být první
  textové pole), `email` (nastaví Reply-To upozornění, takže stačí odpovědět), `telefon`, `zajem`,
  `zprava` (text zprávy). Skrytá pole: `form-name` (název formuláře, nutné pro AJAX), `subject`
  (předmět upozornění, `%{submissionId}` doplní Netlify) a `bot-field` (past na roboty, `netlify-honeypot`).
  Tlačítka „Rezervovat konzultaci“ v ceníku předvyplní `zajem` a `zprava` (atributy `data-kontakt-zajem`,
  `data-kontakt-zprava`).
- Spam filtruje Netlify (past `bot-field` a služba Akismet). Zprávy označené jako spam jsou v administraci
  zvlášť (Forms → kontakt, přepínač spamu) – občas je zkontrolujte.
- CSP (meta ve všech šablonách i `site/_headers`) povoluje jen vlastní web: `connect-src 'self'`
  a `form-action 'self' mailto:`.
- Lokálně ani na GitHub Pages (cíl `preview`) formulář nefunguje – odeslání skončí chybovou hláškou
  s e-mailem. Vyzkoušejte ho na https://nutrivero-nahled.netlify.app/.
- Zásady GDPR popisují formulář v části `#kontaktni-formular` (`_src/legal/ochrana-osobnich-udaju.html`),
  krátké upozornění je i pod tlačítkem „Odeslat zprávu“ – při změně služby upravte obě místa.
- Odeslané zprávy zůstávají v Netlify, dokud je nesmažete. Mažte je podle lhůt uvedených v zásadách
  (v detailu zprávy v Forms → kontakt), případně je předtím exportujte do CSV.

**Jednorázové nastavení v Netlify** (u každého webu zvlášť – `nutrivero-nahled` i budoucí ostrý web):

1. Netlify → web → **Forms** → **Enable form detection**. Detekce probíhá při nasazení, takže po zapnutí
   web **znovu nasaďte** (viz níže); pak se v Forms objeví formulář `kontakt`.
2. Forms → **Form notifications** → **Add notification** → **Email notification** → formulář `kontakt`,
   adresa `info@nutrivero.cz`.
3. Odešlete zkušební zprávu a ověřte, že je v Netlify (Forms → kontakt) a že dorazil e-mail
   (zkontrolujte i složku se spamem ve schránce).

Odeslané zprávy najdete v administraci Netlify: web → **Forms** → **kontakt** (export do CSV tamtéž).

## Build

Spouštějte z kořenové složky projektu:

```
python _src/build.py --target netlify-nahled --out _dist # náhled na Netlify (výchozí cíl) → _dist/
python _src/build.py --target preview                    # náhled na GitHub Pages → site/
python _src/build.py --target production --strict        # ostrý web → site/; zástupné hodnoty = chyba
python _src/build.py --target preview --out ../nutrivero-nahled
                                                          # kompletní web do jiné složky
```

- `--target netlify-nahled|preview|production` – cíl (výchozí podle `TARGET` v `config.json`,
  tj. `production`).
- `--out SLOŽKA` – výstup jinam než do `site/`. Do takové složky build zkopíruje i statické soubory
  ze `site/` (`assets/`, `favicon.ico`, `apple-touch-icon.png`, `site.webmanifest`; u cílů s `NETLIFY`
  `_headers` a `_redirects`, u GitHub Pages `.nojekyll`), takže vznikne kompletní web k nahrání.
  U náhledu na Netlify build do zkopírovaného `_headers` připíše pravidlo `/*` s `X-Robots-Tag: noindex, nofollow`
  – proto náhled na Netlify vždy buildujte s `--out` (zdrojový `site/_headers` se nemění; při buildu
  do `site/` build upozorní). `_dist/` je v `.gitignore`.
- `--strict` – zástupné hodnoty v `config.json` jsou chyba (vždy před ostrým nasazením).

Build selže a nic nezapíše, pokud ve výstupu zůstane `%%…%%` nebo `{{…}}`, JSON-LD není platný JSON,
náhled nemá `noindex`, `SITE_URL` neodpovídá `BASE_PATH`, `UPDATED` / `HOME_UPDATED_ISO` nejsou
platná data, v meta podstránky je neplatné `robots` / `sitemap`, stránka se `"sitemap": false` (nebo
`noindex`) je v `_src/sitemap.xml`, nebo formulář Netlify Forms nemá `name`, `method="POST"`, skryté
pole `form-name`, pole pasti z `netlify-honeypot` či stránku, na kterou míří jeho `action`.

Pozor: `site/` je zároveň zdroj statických souborů i výchozí výstup. HTML v `site/` odpovídá
poslednímu buildu – po buildu náhledu na GitHub Pages má cesty s `/nutrivero-nahled/…`, po buildu
pro Netlify (náhled i ostrý web) cesty od kořene.

### Lokální náhled

- Náhled na Netlify / ostrý web (běží v kořeni): `python _src/build.py --target netlify-nahled --out <dočasná složka>`
  (nebo `--target production`) a pak `python -m http.server 8080 --directory <dočasná složka>`
  → http://localhost:8080/ (kontaktní formulář lokálně skončí chybou – zprávy přijímá jen Netlify).
- Náhled na GitHub Pages (běží v podsložce): `python _src/build.py --target preview --out <dočasná složka>/nutrivero-nahled`,
  pak `python -m http.server 8080 --directory <dočasná složka>` → http://localhost:8080/nutrivero-nahled/

Hlavičky z `_headers` a přesměrování z `_redirects` lokálně ani na GitHub Pages nefungují
(jen na Netlify, případně přes `netlify dev`). Základní CSP je proto zapsaná i přímo v `<head>`
každé stránky (`<meta http-equiv="Content-Security-Policy">`) spolu s `<meta name="referrer">`.

## Náhled na Netlify (cíl netlify-nahled, výchozí)

Web `nutrivero-nahled` na Netlify (https://nutrivero-nahled.netlify.app/, ID
`0e049152-4ae2-4324-a1bf-d60fa1261180`) běží v kořeni domény, je `noindex` a kontaktní formulář
na něm funguje přes Netlify Forms. Nasazuje se ručně z počítače přes Netlify CLI.

Jednorázově: `npm install -g netlify-cli` a `netlify login`. Dále v administraci Netlify zapněte
detekci formulářů a upozornění e-mailem (viz [Kontaktní formulář](#kontaktní-formulář-netlify-forms)).

Každá aktualizace náhledu (z kořenové složky projektu):

```
python _src/build.py --target netlify-nahled --out _dist
netlify deploy --prod --dir _dist --site 0e049152-4ae2-4324-a1bf-d60fa1261180
```

- `--prod` zveřejní nasazení na adrese https://nutrivero-nahled.netlify.app/. **Každé produkční nasazení
  stojí 15 kreditů** z limitu účtu Netlify – nenasazujte kvůli každé drobnosti, změny sdružte
  a předem je zkontrolujte lokálně (viz Lokální náhled).
- Nasazuje se celá složka `_dist` včetně `_headers` a `_redirects`. CLI si stav ukládá do složky
  `.netlify/` (je v `.gitignore`).
- Náhled se neindexuje: `<meta name="robots" content="noindex,nofollow">` na každé stránce, hlavička
  `X-Robots-Tag: noindex, nofollow` (build ji připíše do `_dist/_headers`) a `robots.txt` s `Disallow: /`.
  Sitemap náhled nemá.
- Po nasazení ověřte formulář zkušební zprávou (Forms → kontakt).

## Náhled na GitHub Pages (repozitář nutrivero-nahled)

Původní náhled; zatím zůstává v provozu (o vypnutí GitHub Pages se rozhodne později).
**Kontaktní formulář na něm nefunguje** – GitHub Pages neumí přijímat odeslané formuláře (Netlify Forms
běží jen na Netlify), návštěvník po odeslání uvidí chybovou hlášku s odkazem na e-mail.

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
- Do náhledu se **nekopírují** `_headers` ani `_redirects` (GitHub Pages je nepoužívá; řídí to
  `"NETLIFY": false` cíle `preview`). Pokud ve složce zůstaly z dřívějška, build upozorní – smažte je.
  Na GitHub Pages proto nefungují HSTS, `frame-ancestors`/`X-Frame-Options`, `Permissions-Policy`
  ani přesměrování `/gdpr`, `/vop` … Pro náhled to nevadí; Netlify je má z `_headers`.

### Náhled na GitHub Pages se neindexuje

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

Ostrý web zatím nasazený není (rozhodne se později). Pokud poběží jako samostatný web na Netlify:
jednorázově `npm install -g netlify-cli`, pak `netlify login` a při prvním `netlify deploy` zvolte
„Create & configure a new site“ (nebo web založte v administraci a jeho ID předávejte přes `--site`).
U nového webu znovu zapněte detekci formulářů a upozornění e-mailem
(viz [Kontaktní formulář](#kontaktní-formulář-netlify-forms)) – nastavení se mezi weby nepřenáší.
Pokud se místo toho vlastní doména připojí k webu `nutrivero-nahled`, nasazujte na něj build
`--target production` (ne `netlify-nahled`, ten je `noindex`).

```
python _src/build.py --target production --strict --out ../nutrivero-produkce
netlify deploy --dir ../nutrivero-produkce --site <ID ostrého webu>          # náhledová verze (draft URL) ke kontrole
netlify deploy --prod --dir ../nutrivero-produkce --site <ID ostrého webu>   # ostrá verze (15 kreditů)
```

(Lze buildovat i přímo do `site/` – `python _src/build.py --target production --strict` – a nasadit
`site/`.) Alternativa bez CLI: v administraci Netlify → Deploys přetáhněte celou výstupní složku.
Nasazuje se vždy celá složka – včetně souborů `_headers` a `_redirects`.

Pokud ostrý web poběží jinde než na Netlify, upravte v `config.json` → `targets.production` hodnoty
`HOSTING_*` (promítnou se do právních textů) a nastavte hlavičky z `site/_headers` u nového hostingu.

Cache: obrázky a fonty mají cache na 1 rok (`immutable`). Když obrázek měníte, **uložte ho pod novým
názvem** (např. `og-image-4.jpg`) a upravte odkazy, jinak se návštěvníkům může zobrazovat starý.
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
