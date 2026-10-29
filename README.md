# Nutrivero – web

Statický web Nutrivero (nutriční poradenství, Bc. Tereza Ševčíková).

- **Náhled na Netlify (hlavní):** https://nutrivero-nahled.netlify.app/ (noindex, cíl `netlify-nahled`,
  nasazuje se ručně přes Netlify CLI; kontaktní formulář přes Netlify Forms)
- **Náhled na GitHub Pages:** https://ondrejkamaryt.github.io/nutrivero-nahled/ (noindex, cíl `preview`,
  nasazuje se automaticky z větve `main` přes GitHub Actions; **kontaktní formulář tu nefunguje** –
  GitHub Pages neumí zpracovat odeslaný formulář)
- **Ostrý web:** https://nutrivero.cz/ (cíl `production`, zatím nenasazeno)
- **Zdroje:** `_src/` (šablony, právní texty, `config.json`, `build.py`) – podrobný návod je v [`_src/README.md`](_src/README.md)
- **Výstup / statické soubory:** `site/`

Náhled na Netlify – sestavení a nasazení (z kořenové složky projektu):

```bash
python _src/build.py --target netlify-nahled --out _dist
netlify deploy --prod --dir _dist --site 0e049152-4ae2-4324-a1bf-d60fa1261180
```

Každé produkční nasazení (`--prod`) stojí na Netlify 15 kreditů – změny sdružujte.

Jednorázově v administraci Netlify (web `nutrivero-nahled`):

1. **Forms → Enable form detection** a pak web znovu nasaďte (formuláře se hledají při nasazení).
2. **Forms → Form notifications → Add notification → Email notification** → formulář `kontakt`,
   adresa `info@nutrivero.cz`.

Odeslané zprávy z formuláře: administrace Netlify → web → **Forms → kontakt**.

Ostatní sestavení:

```bash
python _src/build.py --target preview
python _src/build.py --target production --strict --out _dist
```
