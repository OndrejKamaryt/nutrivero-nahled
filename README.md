# Nutrivero – web

Statický web Nutrivero (nutriční poradenství, Bc. Tereza Ševčíková).

- **Náhled:** https://ondrejkamaryt.github.io/nutrivero-nahled/ (noindex, nasazuje se automaticky z větve `main` přes GitHub Actions)
- **Zdroje:** `_src/` (šablony, právní texty, `config.json`, `build.py`) – podrobný návod je v [`_src/README.md`](_src/README.md)
- **Výstup / statické soubory:** `site/`

Lokální sestavení:

```bash
python _src/build.py --target preview
python _src/build.py --target production --strict --out _dist
```
