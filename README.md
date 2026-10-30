# Nutrivero – web

Statický web Nutrivero (výživové poradenství, Tereza Ševčíková).

- **Ostrý web:** https://nutrivero.cz/ (cíl `production`, indexovatelný; hosting Netlify, web `nutrivero-nahled`,
  nasazuje se ručně přes Netlify CLI; kontaktní formulář přes Netlify Forms). `www.nutrivero.cz` a
  `nutrivero-nahled.netlify.app` přesměrovávají na `nutrivero.cz`.
- **DNS:** u Webglobe (administrace Terezy). Web: A `@` → `75.2.60.5`, CNAME `www` → `nutrivero-nahled.netlify.app.`;
  e-mail běží přes Google Workspace (MX `smtp.google.com`) – MX a ostatní záznamy neměnit.
  Původní A `@` před spuštěním: `62.109.151.80` (hosting Webglobe).
- **E-mail (30. 10. 2026):** SPF `v=spf1 include:_spf.google.com include:_spf.webglobe.cz ~all`
  (původně `v=spf1 a mx include:_spf.webglobe.cz -all`), DKIM `google._domainkey` (2048 bitů, vygenerováno
  a zapnuté v Google Admin → Gmail → Ověřit e-mail), DMARC `p=none`.
- **Google Search Console:** vlastnost typu Doména `nutrivero.cz` (účet info@nutrivero.cz), ověřená
  záznamem `google-site-verification` v DNS – ten nemazat; odeslaná sitemapa `https://nutrivero.cz/sitemap.xml`.
- **Starý náhled na GitHub Pages:** https://ondrejkamaryt.github.io/nutrivero-nahled/ jen přesměrovává na
  https://nutrivero.cz/ (workflow `.github/workflows/pages.yml` publikuje `.github/pages-redirect/`).
- **Zdroje:** `_src/` (šablony, právní texty, `config.json`, `build.py`) – podrobný návod je v [`_src/README.md`](_src/README.md)
- **Výstup / statické soubory:** `site/`

Sestavení a nasazení ostrého webu (z kořenové složky projektu):

```bash
python _src/build.py --target production --strict --out _dist
netlify deploy --prod --dir _dist --site 0e049152-4ae2-4324-a1bf-d60fa1261180
```

Každé produkční nasazení (`--prod`) stojí na Netlify 15 kreditů – změny sdružujte.

Nastavení v administraci Netlify (web `nutrivero-nahled`) – hotovo:

1. **Forms → Enable form detection** (formuláře se hledají při nasazení).
2. **Forms → Form notifications → Email notification** → formulář `kontakt`, adresa `info@nutrivero.cz`.
3. **Domain management:** hlavní doména `nutrivero.cz`, alias `www.nutrivero.cz`, certifikát Let's Encrypt.

Odeslané zprávy z formuláře: administrace Netlify → web → **Forms → kontakt** (mazat do 30 dnů od vyřízení
podle zásad zpracování osobních údajů).

Ostatní sestavení:

```bash
python _src/build.py --target netlify-nahled --out _dist   # noindex náhled na *.netlify.app (nepoužívá se)
python _src/build.py --target preview                      # GitHub Pages v podsložce (nepoužívá se)
```
