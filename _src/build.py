#!/usr/bin/env python3
"""Nutrivero – sestavení statického webu z _src/ (výchozí výstup site/).

Spuštění (z libovolné složky):
    python "_src/build.py"                               # výchozí cíl z config.json (TARGET), výstup do site/
    python "_src/build.py" --target netlify-nahled --out _dist
                                                         # náhled na Netlify (kořen, noindex) – výchozí cíl
    python "_src/build.py" --target preview              # náhled na GitHub Pages (/nutrivero-nahled, noindex)
    python "_src/build.py" --target production --strict  # ostrý web v kořeni domény; zástupné hodnoty = chyba
    python "_src/build.py" --target preview --out ../nutrivero-nahled
                                                         # kompletní web do jiné složky (HTML + statické soubory)

Cíle (config.json → "targets"):
  * společné hodnoty tokenů jsou v kořeni config.json, hodnoty cíle (targets.<cíl>) je doplní/přepíšou,
  * výchozí cíl je "TARGET" v config.json, přepínač --target ho přepíše,
  * každý cíl určuje SITE_URL, BASE_PATH (podsložka, kde web běží; "" = kořen domény), PREVIEW
    (true = noindex,nofollow), NETLIFY (true = web běží na Netlify: do výstupu patří _headers
    a _redirects a funguje kontaktní formulář přes Netlify Forms) a údaje o hostingu
    HOSTING_NAME / _SERVICE / _ADDRESS / _PRIVACY_URL,
  * netlify-nahled = náhled na Netlify (PREVIEW + NETLIFY), preview = náhled na GitHub Pages
    (PREVIEW, bez NETLIFY), production = ostrý web (NETLIFY, indexovatelný).

Co dělá:
  * načte _src/config.json, doplní vypočtené tokeny %%BUILD_DATE%% (dnešní datum, ISO),
    %%UPDATED_ISO%% (UPDATED „26. 10. 2026“ jako 2026-10-26, lastmod právních stránek),
    %%ROBOTS%% (index,follow / noindex,nofollow podle PREVIEW) a %%ROBOTS_404%% (vždy noindex),
  * _src/index.html  -> <výstup>/index.html
  * _src/legal/<slug>.html (první řádek <!--meta {...} -->) + _src/page-template.html
                     -> <výstup>/<slug>/index.html; volitelné klíče meta: "robots" (např. "noindex,nofollow",
                     přepíše {{ROBOTS}} stránky u ostrého webu; náhled je vždy noindex,nofollow) a "sitemap": false
                     (stránka nemá být v sitemap ostrého webu – build ověří, že v _src/sitemap.xml není),
  * _src/404.html    -> <výstup>/404.html
  * _src/robots.txt (ostrý web) nebo _src/robots-preview.txt (náhled) -> <výstup>/robots.txt
  * _src/sitemap.xml -> <výstup>/sitemap.xml jen u ostrého webu (lastmod = HOME_UPDATED_ISO
    u hlavní stránky, UPDATED_ISO u právních); seznam adres je ručně psaný – build ho porovná se
    stránkami: stránka se "sitemap": false nebo robots noindex v sitemap = chyba, indexovatelná stránka
    chybějící v sitemap nebo adresa bez stránky = upozornění; náhled (noindex) sitemap nemá a starou
    sitemap.xml z dřívějšího buildu ve výstupu smaže,
  * v každém výstupu nahradí %%TOKENY%% a escapuje hodnoty podle kontextu
    (HTML text/atributy, JSON-LD, XML, prostý text),
  * v HTML doplní BASE_PATH před každou kořenovou adresu ("/…") v atributech href, src, srcset,
    imagesrcset, poster, action a data-src (nemění "//…", absolutní URL, mailto:, tel:, "#…"),
  * selže (exit 1) a vypíše soubor + token, pokud ve výstupu zůstane %%…%% nebo {{…}},
  * zkontroluje formuláře Netlify Forms (data-netlify="true"): atribut name, skryté pole form-name
    se stejnou hodnotou a existenci stránky z action (např. /dekujeme/),
  * pokud je výstupní složka jiná než site/, zkopíruje do ní ze site/ i statické soubory
    (assets/, favicon.ico, apple-touch-icon.png, site.webmanifest; u cílů s NETLIFY true
    _headers a _redirects, u ostatních .nojekyll pro GitHub Pages), takže vznikne kompletní web
    k nasazení; u náhledu na Netlify (PREVIEW i NETLIFY) připíše do zkopírovaného _headers pravidlo
    "/*" s hlavičkou X-Robots-Tag: noindex, nofollow (zdrojový site/_headers se nemění).

Jen standardní knihovna Pythonu 3, vše v UTF-8, konce řádků LF.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
SITE = ROOT / "site"  # statické soubory (assets, ikony…) a výchozí výstup

TARGET_NAMES = ("netlify-nahled", "preview", "production")
DEFAULT_TARGET = "netlify-nahled"

# Statické soubory ze site/, které se kopírují do jiné výstupní složky (--out).
STATIC_COMMON = ["assets", "favicon.ico", "apple-touch-icon.png", "site.webmanifest"]
STATIC_NETLIFY = ["_headers", "_redirects"]  # jen cíle s NETLIFY true; GitHub Pages je ignoruje
STATIC_GITHUB = [".nojekyll"]                # jen cíle bez NETLIFY (GitHub Pages: nezpracovávat Jekyllem)

# Připíše se do zkopírovaného _headers u náhledu na Netlify (PREVIEW i NETLIFY true).
NETLIFY_PREVIEW_HEADERS = """
# --- Doplněno buildem (cíl {target}, náhled): náhled se nemá indexovat. Ve zdrojovém site/_headers není. ---
/*
  X-Robots-Tag: noindex, nofollow
"""

TOKEN_RE = re.compile(r"%%([A-Za-z0-9_]+)%%")
LEFTOVER_TOKEN_RE = re.compile(r"%%[A-Za-z0-9_]*%%")
LEFTOVER_PLACEHOLDER_RE = re.compile(r"\{\{[^{}\n]*\}\}")
META_RE = re.compile(r"\A\s*<!--\s*meta\s+(\{.*?\})\s*-->[ \t]*\r?\n?", re.S)
LDJSON_RE = re.compile(
    r"(<script\b[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>)(.*?)(</script\s*>)",
    re.S | re.I,
)
# „&“, která nezačíná existující entitou (&nbsp; &amp; &#160; &#xA0;)
BARE_AMP_RE = re.compile(r"&(?!(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});)")

# Otevírací HTML tag (hodnoty atributů v uvozovkách smí obsahovat ">") a jeho atributy.
TAG_RE = re.compile(
    r"<[A-Za-z][^\s/>]*(?:\s+[^\s\"'=/>]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?)*\s*/?>"
)
ATTR_RE = re.compile(r"(\s)([^\s\"'=/>]+)(\s*=\s*)(\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+)")
URL_ATTRS = {"href", "src", "poster", "action", "data-src"}
SRCSET_ATTRS = {"srcset", "imagesrcset"}
CSS_ROOT_URL_RE = re.compile(r"url\(\s*(?:&quot;|[\"'])?/(?!/)", re.I)
ROBOTS_META_RE = re.compile(r"<meta\s+name=\"robots\"\s+content=\"([^\"]*)\"", re.I)
# Povolené direktivy pro "robots" v meta právního fragmentu (oddělené čárkou).
ROBOTS_DIRECTIVE_RE = re.compile(
    r"all|none|index|noindex|follow|nofollow|noarchive|nosnippet|noimageindex|notranslate|indexifembedded"
    r"|max-snippet:-?\d+|max-image-preview:(?:none|standard|large)|max-video-preview:-?\d+"
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FORM_RE = re.compile(r"(<form\b[^>]*>)(.*?)</form\s*>", re.S | re.I)
INPUT_TAG_RE = re.compile(r"<input\b[^>]*>", re.I)
SITEMAP_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")

REQUIRED_TOKENS = [
    "JMENO", "ICO", "ADRESA", "EMAIL", "TELEFON", "TELEFON_HREF",
    "SITE_URL", "UPDATED", "HOME_UPDATED_ISO", "REZERVACE_URL", "REZERVACE_LINK",
    "HOSTING_NAME", "HOSTING_SERVICE", "HOSTING_ADDRESS", "HOSTING_PRIVACY_URL",
]
# Hodnoty, které končí v URL (href/src/mailto/tel) – nesmí obsahovat mezery.
URL_TOKENS = ["EMAIL", "TELEFON_HREF", "SITE_URL", "BASE_PATH", "REZERVACE_URL", "REZERVACE_LINK",
              "HOSTING_PRIVACY_URL"]
# Tokeny, které počítá build – v config.json se nezadávají.
COMPUTED_TOKENS = ["BUILD_DATE", "UPDATED_ISO", "ROBOTS", "ROBOTS_404"]
TEMPLATE_KEYS = ["TITLE", "DESCRIPTION", "PATH", "H1", "LEAD", "CONTENT", "ROBOTS"]
META_KEYS = ["title", "description", "h1", "lead", "path"]
META_OPTIONAL_KEYS = ["robots", "sitemap"]


class BuildError(Exception):
    pass


errors: list[str] = []
warnings: list[str] = []


def read(path: Path) -> str:
    # utf-8-sig odstraní případný BOM; textový režim sjednotí konce řádků na \n
    return path.read_text(encoding="utf-8-sig")


# HTML komentáře (interní poznámky typu „K POTVRZENÍ MAJITELKOU“) nepatří do veřejného zdrojového kódu:
# celé řádky s komentářem se vypustí, komentáře uprostřed řádku se odstraní bez okolních mezer.
HTML_COMMENT_LINE_RE = re.compile(r"^[ \t]*<!--(?!\[if).*?-->[ \t]*\n", re.S | re.M)
HTML_COMMENT_RE = re.compile(r"<!--(?!\[if).*?-->", re.S)


def write(path: Path, text: str) -> None:
    if path.suffix == ".html":
        text = HTML_COMMENT_RE.sub("", HTML_COMMENT_LINE_RE.sub("", text))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- escapování
def esc_html(value: str) -> str:
    """Escapuje hodnotu pro HTML text i atribut v uvozovkách."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def esc_html_keep_entities(value: str) -> str:
    """Pro hodnoty z meta komentáře: escapuje, ale ponechá už zapsané entity (&nbsp;)."""
    value = BARE_AMP_RE.sub("&amp;", value)
    return value.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def esc_json(value: str) -> str:
    """Obsah řetězce v JSON (bez uvozovek), bezpečný uvnitř <script>."""
    return json.dumps(value, ensure_ascii=False)[1:-1].replace("</", "<\\/")


def esc_xml(value: str) -> str:
    return html.escape(value, quote=True)


def esc_raw(value: str) -> str:
    return value


# ---------------------------------------------------------------- konfigurace
def load_config(strict: bool, target_arg: str | None) -> tuple[dict[str, str], str, bool, bool]:
    """Vrátí (tokeny, název cíle, PREVIEW, NETLIFY)."""
    cfg_path = SRC / "config.json"
    try:
        raw = json.loads(read(cfg_path))
    except FileNotFoundError:
        raise BuildError(f"{rel(cfg_path)}: soubor neexistuje")
    except json.JSONDecodeError as exc:
        raise BuildError(f"{rel(cfg_path)}: neplatný JSON ({exc})")
    if not isinstance(raw, dict):
        raise BuildError(f"{rel(cfg_path)}: očekáván objekt {{\"TOKEN\": \"hodnota\"}}")

    # --- výběr cíle
    targets = raw.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise BuildError("config.json: chybí objekt \"targets\" s cíli " + ", ".join(f"\"{n}\"" for n in TARGET_NAMES))
    default_target = raw.get("TARGET", DEFAULT_TARGET)
    if not isinstance(default_target, str):
        raise BuildError("config.json: TARGET musí být řetězec (" + ", ".join(f"\"{n}\"" for n in TARGET_NAMES) + ")")
    target = target_arg or default_target.strip()
    if target not in targets or not isinstance(targets[target], dict):
        available = ", ".join(k for k, v in targets.items() if isinstance(v, dict)) or "žádné"
        raise BuildError(f"config.json: cíl {target!r} není v \"targets\" (k dispozici: {available})")
    for name in TARGET_NAMES:
        if name not in targets:
            warnings.append(f"config.json: v \"targets\" chybí cíl {name!r}")

    # --- sloučení: společné hodnoty, přes ně hodnoty cíle
    merged: dict[str, tuple[object, str]] = {}
    for where, source in (("config.json", raw), (f"config.json targets.{target}", targets[target])):
        for key, val in source.items():
            if key.startswith("_") or key in ("TARGET", "targets"):  # komentáře a řídicí klíče
                continue
            merged[key] = (val, where)

    cfg: dict[str, str] = {}
    flags: dict[str, bool | None] = {"PREVIEW": None, "NETLIFY": None}  # přepínače cíle (nejsou to tokeny)
    for key, (val, where) in merged.items():
        if key in flags:
            if isinstance(val, bool):
                flags[key] = val
            else:
                errors.append(f"{where}: {key} musí být true nebo false (bez uvozovek)")
            continue
        if not isinstance(val, str):
            errors.append(f"{where}: {key} musí být řetězec, je {type(val).__name__}")
            continue
        cfg[key] = val.strip()

    flag_help = {
        "PREVIEW": "true = náhled s noindex, false = ostrý web",
        "NETLIFY": "true = web běží na Netlify (_headers, _redirects, Netlify Forms), false = GitHub Pages",
    }
    for key, help_text in flag_help.items():
        if flags[key] is None and not any(key in e for e in errors):
            errors.append(f"config.json targets.{target}: chybí {key} ({help_text})")
    preview = bool(flags["PREVIEW"])
    netlify = bool(flags["NETLIFY"])

    for key in REQUIRED_TOKENS:
        if not cfg.get(key):
            errors.append(f"config.json (cíl {target}): chybí nebo je prázdná hodnota {key}")
    if "BASE_PATH" not in cfg:
        errors.append(f"config.json targets.{target}: chybí BASE_PATH (pro web v kořeni domény zadejte \"\")")

    for key in COMPUTED_TOKENS:
        if key in cfg:
            warnings.append(f"config.json: {key} se počítá při buildu, hodnota v configu se ignoruje")
    cfg["BUILD_DATE"] = _dt.date.today().isoformat()
    cfg["ROBOTS"] = "noindex,nofollow" if preview else "index,follow"
    cfg["ROBOTS_404"] = "noindex,nofollow" if preview else "noindex,follow"

    # --- data pro <lastmod> v sitemap: mění se jen se změnou obsahu, ne s každým buildem
    today = _dt.date.today()
    updated = cfg.get("UPDATED", "")
    updated_date = None
    m = re.fullmatch(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", updated)
    if m:
        try:
            updated_date = _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    if updated_date:
        cfg["UPDATED_ISO"] = updated_date.isoformat()
    else:
        if updated and not updated.startswith("["):
            errors.append(f"config.json: UPDATED musí být datum ve tvaru \"26. 10. 2026\" ({updated!r})")
        cfg["UPDATED_ISO"] = cfg["BUILD_DATE"]
    home = cfg.get("HOME_UPDATED_ISO", "")
    if home:
        home_date = None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", home):
            try:
                home_date = _dt.date.fromisoformat(home)
            except ValueError:
                pass
        if not home_date:
            errors.append(f"config.json: HOME_UPDATED_ISO musí být datum ve tvaru RRRR-MM-DD ({home!r})")
        elif home_date > today:
            warnings.append(f"config.json: HOME_UPDATED_ISO ({home}) je v budoucnosti – lastmod v sitemap by byl neplatný")
    if updated_date and updated_date > today and not preview:
        warnings.append(f"config.json: UPDATED ({updated}) je v budoucnosti – lastmod právních stránek v sitemap by byl neplatný")

    # --- kontrola tvaru hodnot
    for key in URL_TOKENS:
        val = cfg.get(key, "")
        if re.search(r"\s", val):
            errors.append(f"config.json: {key} nesmí obsahovat mezery ani zalomení ({val!r})")

    base = cfg.get("BASE_PATH", "")
    if base.endswith("/"):
        cfg["BASE_PATH"] = base = base.rstrip("/")
        warnings.append("config.json: BASE_PATH končil lomítkem – odstraněno")
    if base and not re.fullmatch(r"(?:/[A-Za-z0-9._~-]+)+", base):
        errors.append(
            f"config.json: BASE_PATH musí být \"\" nebo cesta ve tvaru \"/nazev\" bez koncového lomítka ({base!r})"
        )

    site_url = cfg.get("SITE_URL", "")
    if site_url.endswith("/"):
        cfg["SITE_URL"] = site_url = site_url.rstrip("/")
        warnings.append("config.json: SITE_URL končil lomítkem – odstraněno")
    if site_url:
        parts = urlsplit(site_url)
        if parts.scheme != "https" or not parts.netloc:
            errors.append(f"config.json: SITE_URL musí být absolutní https:// adresa ({site_url!r})")
        if parts.query or parts.fragment:
            errors.append(f"config.json: SITE_URL nesmí obsahovat ?dotaz ani #kotvu ({site_url!r})")
        if parts.path.rstrip("/") != base:
            errors.append(
                f"config.json (cíl {target}): cesta v SITE_URL ({parts.path or '/'!r}) musí odpovídat "
                f"BASE_PATH ({base!r}) – jinak by canonical/og:url vedly jinam, než web běží"
            )
        if not preview and parts.netloc.endswith(("github.io", "netlify.app")):
            warnings.append(
                f"config.json: SITE_URL ostrého webu míří na {parts.netloc} – nastavte vlastní doménu"
            )
        if netlify and parts.netloc.endswith("github.io"):
            warnings.append(f"config.json (cíl {target}): NETLIFY je true, ale SITE_URL míří na GitHub Pages ({parts.netloc})")
        if not netlify and parts.netloc.endswith("netlify.app"):
            warnings.append(f"config.json (cíl {target}): SITE_URL míří na Netlify ({parts.netloc}), ale NETLIFY je false "
                            "– do výstupu se nezkopíruje _headers ani _redirects")
    if netlify and base:
        warnings.append(
            f"config.json (cíl {target}): NETLIFY je true a web běží v podsložce {base} – cesty v site/_headers "
            "a site/_redirects i AJAX formuláře počítají s webem v kořeni domény"
        )
    if netlify and cfg.get("HOSTING_SERVICE") and "netlify" not in cfg["HOSTING_SERVICE"].lower():
        warnings.append(f"config.json (cíl {target}): NETLIFY je true, ale HOSTING_SERVICE je {cfg['HOSTING_SERVICE']!r} "
                        "– právní texty by uváděly jiný hosting")
    if not netlify and "netlify" in cfg.get("HOSTING_SERVICE", "").lower():
        warnings.append(f"config.json (cíl {target}): HOSTING_SERVICE je Netlify, ale NETLIFY je false")

    hosting_privacy = cfg.get("HOSTING_PRIVACY_URL", "")
    if hosting_privacy and not hosting_privacy.startswith("https://"):
        errors.append(f"config.json: HOSTING_PRIVACY_URL musí začínat https:// ({hosting_privacy!r})")

    rez = cfg.get("REZERVACE_URL", "")
    if rez and not rez.startswith("https://calendar.google.com/"):
        warnings.append(
            "config.json: REZERVACE_URL nezačíná https://calendar.google.com/ – CSP frame-src "
            "(meta v šablonách i site/_headers) ho zablokuje"
        )
    if rez and "gv=true" not in rez:
        warnings.append("config.json: REZERVACE_URL neobsahuje gv=true (vložitelná verze rezervační stránky)")
    link = cfg.get("REZERVACE_LINK", "")
    if link and "gv=true" in link:
        warnings.append("config.json: REZERVACE_LINK by neměl obsahovat gv=true (odkaz do nového okna)")

    email = cfg.get("EMAIL", "")
    if email and not email.startswith("[") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", email):
        errors.append(f"config.json: EMAIL nevypadá jako e-mailová adresa ({email!r})")
    tel = cfg.get("TELEFON_HREF", "")
    if tel and not re.fullmatch(r"\+?[0-9]{6,15}", tel):
        errors.append(f"config.json: TELEFON_HREF musí být jen číslice s volitelným + na začátku ({tel!r})")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cfg["BUILD_DATE"]):
        errors.append("BUILD_DATE: neočekávaný formát")
    ico = cfg.get("ICO", "")
    if ico and not ico.startswith("[") and not re.fullmatch(r"\d{8}", ico):
        warnings.append(f"config.json: ICO nemá 8 číslic ({ico!r})")

    # --- zástupné hodnoty
    placeholders = []
    for key, val in cfg.items():
        if val.startswith("["):
            placeholders.append(f"{key}={val}")
    if re.fullmatch(r"\+?420?0+", tel or "x") or re.fullmatch(r"\+?0+", tel or "x"):
        placeholders.append(f"TELEFON_HREF={tel}")
    if placeholders:
        msg = "config.json: zástupné hodnoty – doplňte před zveřejněním: " + ", ".join(placeholders)
        (errors if strict else warnings).append(msg)

    return cfg, target, preview, netlify


# ---------------------------------------------------------------- tokeny
def substitute(text: str, cfg: dict[str, str], kind: str, label: str) -> str:
    """Nahradí %%TOKENY%%. kind: html | xml | txt."""
    unknown: set[str] = set()

    def repl_with(escaper):
        def repl(m: re.Match) -> str:
            name = m.group(1)
            if name not in cfg:
                unknown.add(name)
                return m.group(0)
            return escaper(cfg[name])
        return repl

    if kind == "html":
        out, pos = [], 0
        for m in LDJSON_RE.finditer(text):
            out.append(TOKEN_RE.sub(repl_with(esc_html), text[pos:m.start()]))
            body = TOKEN_RE.sub(repl_with(esc_json), m.group(2))
            try:
                json.loads(body)
            except json.JSONDecodeError as exc:
                errors.append(f"{label}: JSON-LD po dosazení není platný JSON ({exc})")
            out.append(m.group(1) + body + m.group(3))
            pos = m.end()
        out.append(TOKEN_RE.sub(repl_with(esc_html), text[pos:]))
        result = "".join(out)
    elif kind == "xml":
        result = TOKEN_RE.sub(repl_with(esc_xml), text)
    else:
        result = TOKEN_RE.sub(repl_with(esc_raw), text)

    for name in sorted(unknown):
        errors.append(f"{label}: neznámý token %%{name}%% (není v config.json)")
    return result


def check_leftovers(text: str, label: str) -> None:
    for regex in (LEFTOVER_TOKEN_RE, LEFTOVER_PLACEHOLDER_RE):
        for m in regex.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            errors.append(f"{label}:{line}: nenahrazeno {m.group(0)}")


# ---------------------------------------------------------------- BASE_PATH
def prefix_url(url: str, base: str) -> str:
    """"/cesta" -> base + "/cesta". Nemění "//…", absolutní URL, mailto:, tel:, "#…" ani relativní cesty."""
    lead = len(url) - len(url.lstrip(" \t\n\r\f"))
    head, body = url[:lead], url[lead:]
    if not base or not body.startswith("/") or body.startswith("//"):
        return url
    if body.startswith(base) and body[len(base):len(base) + 1] in ("", "/", "?", "#"):
        return url  # už začíná BASE_PATH (např. zapsáno jako %%BASE_PATH%%/…)
    return head + base + body


def prefix_srcset(value: str, base: str) -> str:
    out = []
    for cand in value.split(","):
        m = re.match(r"(\s*)(\S+)(.*)", cand, re.S)
        out.append(m.group(1) + prefix_url(m.group(2), base) + m.group(3) if m else cand)
    return ",".join(out)


def apply_base_path(text: str, base: str) -> tuple[str, int]:
    """Doplní BASE_PATH do kořenových adres v atributech všech HTML tagů. Vrací (text, počet změn)."""
    if not base:
        return text, 0
    count = 0

    def fix_attr(m: re.Match) -> str:
        nonlocal count
        name = m.group(2).lower()
        if name not in URL_ATTRS and name not in SRCSET_ATTRS:
            return m.group(0)
        raw = m.group(4)
        quote = raw[0] if raw[:1] in ("\"", "'") else ""
        value = raw[1:-1] if quote else raw
        new = prefix_srcset(value, base) if name in SRCSET_ATTRS else prefix_url(value, base)
        if new == value:
            return m.group(0)
        count += 1
        return m.group(1) + m.group(2) + m.group(3) + quote + new + quote

    def fix_tag(m: re.Match) -> str:
        return ATTR_RE.sub(fix_attr, m.group(0))

    return TAG_RE.sub(fix_tag, text), count


# ---------------------------------------------------------------- stránky
def parse_legal(path: Path) -> tuple[dict, str]:
    text = read(path)
    m = META_RE.match(text)
    if not m:
        raise BuildError(f"{rel(path)}: první řádek musí být <!--meta {{json}} -->")
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{rel(path)}: meta komentář není platný JSON ({exc})")
    missing = [k for k in META_KEYS if not str(meta.get(k, "")).strip()]
    if missing:
        raise BuildError(f"{rel(path)}: v meta chybí {', '.join(missing)}")
    expected = f"/{path.stem}/"
    if meta["path"] != expected:
        errors.append(f"{rel(path)}: meta.path je {meta['path']!r}, očekáváno {expected!r}")
    desc_len = len(meta["description"])
    if desc_len > 160:
        warnings.append(f"{rel(path)}: meta description má {desc_len} znaků (doporučeno do ~155)")
    if len(meta["title"]) > 70:
        warnings.append(f"{rel(path)}: title má {len(meta['title'])} znaků (doporučeno do ~65)")
    unknown = sorted(k for k in meta if k not in META_KEYS and k not in META_OPTIONAL_KEYS)
    if unknown:
        warnings.append(f"{rel(path)}: neznámé klíče v meta ({', '.join(unknown)}) – build je ignoruje")
    if "robots" in meta:
        robots = meta["robots"]
        parts = [p.strip().lower() for p in robots.split(",")] if isinstance(robots, str) else []
        bad = [p for p in parts if not ROBOTS_DIRECTIVE_RE.fullmatch(p)]
        if not parts or bad:
            errors.append(f"{rel(path)}: meta.robots musí být řetězec direktiv oddělených čárkou, "
                          f"např. \"noindex,nofollow\" ({robots!r})")
            meta.pop("robots")
        else:
            meta["robots"] = ",".join(parts)
    if "sitemap" in meta and not isinstance(meta["sitemap"], bool):
        errors.append(f"{rel(path)}: meta.sitemap musí být true nebo false (bez uvozovek), je {meta['sitemap']!r}")
        meta.pop("sitemap")
    content = text[m.end():].strip("\n")
    if re.search(r"<h1[\s>]", content, re.I):
        warnings.append(f"{rel(path)}: fragment obsahuje <h1> – H1 doplňuje šablona")
    return meta, content


TEMPLATE_KEY_RE = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")


def check_template(template: str) -> None:
    found = set(TEMPLATE_KEY_RE.findall(template))
    missing = [k for k in TEMPLATE_KEYS if k not in found]
    if missing:
        warnings.append("page-template.html: chybí zástupné místo " + ", ".join("{{" + k + "}}" for k in missing))
    extra = sorted(found - set(TEMPLATE_KEYS))
    if extra:
        errors.append("page-template.html: neznámé zástupné místo " + ", ".join("{{" + k + "}}" for k in extra))


def fill_template(template: str, values: dict[str, str]) -> str:
    # jeden průchod – obsah dosazený do {{CONTENT}} se už znovu nezpracovává
    def repl(m: re.Match) -> str:
        return values.get(m.group(1), m.group(0))
    return TEMPLATE_KEY_RE.sub(repl, template)


def check_page(result: str, label: str, preview: bool, base: str) -> None:
    """Kontroly hotové HTML stránky, které hlídají správné nastavení cíle."""
    robots = ROBOTS_META_RE.search(result)
    if not robots:
        errors.append(f"{label}: chybí <meta name=\"robots\">")
    elif preview and not robots.group(1).startswith("noindex"):
        errors.append(f"{label}: náhled musí mít robots noindex, má {robots.group(1)!r}")
    if 'http-equiv="Content-Security-Policy"' not in result:
        warnings.append(f"{label}: chybí <meta http-equiv=\"Content-Security-Policy\">")
    if base:
        m = CSS_ROOT_URL_RE.search(result)
        if m:
            line = result.count("\n", 0, m.start()) + 1
            errors.append(f"{label}:{line}: inline url(/…) nefunguje v podsložce {base} – použijte relativní cestu")


def tag_attrs(tag: str) -> dict[str, str]:
    """Atributy s hodnotou z otevíracího tagu jako {název: hodnota} (bez uvozovek, bez dekódování entit)."""
    attrs: dict[str, str] = {}
    for m in ATTR_RE.finditer(tag):
        raw = m.group(4)
        attrs.setdefault(m.group(2).lower(), raw[1:-1] if raw[:1] in ("\"", "'") else raw)
    return attrs


def check_netlify_forms(result: str, label: str, base: str, page_paths: set[str]) -> list[str]:
    """Kontrola formulářů pro Netlify Forms (data-netlify="true"). Vrací jejich názvy."""
    names = []
    for m in FORM_RE.finditer(HTML_COMMENT_RE.sub("", result)):
        form = tag_attrs(m.group(1))
        if form.get("data-netlify", "").lower() != "true":
            continue
        name = form.get("name", "")
        names.append(name or "?")
        if not name:
            errors.append(f"{label}: formulář s data-netlify=\"true\" nemá atribut name (Netlify ho nerozpozná)")
            continue
        if form.get("method", "").lower() != "post":
            errors.append(f"{label}: formulář {name!r} (Netlify Forms) musí mít method=\"POST\"")
        inputs = [tag_attrs(t) for t in INPUT_TAG_RE.findall(m.group(2))]
        if not any(a.get("type") == "hidden" and a.get("name") == "form-name" and a.get("value") == name for a in inputs):
            errors.append(f"{label}: formulář {name!r} nemá skryté pole <input type=\"hidden\" name=\"form-name\" "
                          f"value=\"{name}\"> (nutné pro odeslání AJAXem)")
        honeypot = form.get("netlify-honeypot") or form.get("data-netlify-honeypot")
        if honeypot and not any(a.get("name") == honeypot for a in inputs):
            errors.append(f"{label}: formulář {name!r}: netlify-honeypot={honeypot!r}, ale pole s tímto názvem chybí")
        action = form.get("action", "")
        if action.startswith("/") and not action.startswith("//"):
            path = action.split("#", 1)[0].split("?", 1)[0]
            if base and (path == base or path.startswith(base + "/")):
                path = path[len(base):] or "/"
            if path not in page_paths:
                errors.append(f"{label}: formulář {name!r} má action={action!r}, ale taková stránka se negeneruje")
    return names


def check_sitemap(result: str, label: str, site_url: str, pages: dict[str, bool]) -> None:
    """Porovná ručně psanou sitemap se stránkami. pages = {cesta: má být v sitemap}."""
    locs = SITEMAP_LOC_RE.findall(result)
    listed = set()
    for loc in locs:
        if not loc.startswith(site_url + "/"):
            errors.append(f"{label}: adresa {loc} nezačíná SITE_URL {site_url}/")
            continue
        path = loc[len(site_url):]
        listed.add(path)
        if path not in pages:
            warnings.append(f"{label}: adresa {loc} neodpovídá žádné generované stránce")
        elif not pages[path]:
            errors.append(f"{label}: {path} nemá být v sitemap (\"sitemap\": false nebo robots noindex) – "
                          "odeberte ji z _src/sitemap.xml")
    if len(listed) != len(locs):
        warnings.append(f"{label}: některá adresa je v sitemap vícekrát")
    for path, wanted in sorted(pages.items()):
        if wanted and path not in listed:
            warnings.append(f"{label}: chybí indexovatelná stránka {path} – doplňte ji do _src/sitemap.xml "
                            "(nebo dejte do meta fragmentu \"sitemap\": false)")


def resolve_out(out_arg: str | None) -> Path:
    out = Path(out_arg).expanduser().resolve() if out_arg else SITE
    if out == SITE:
        return out
    if out == ROOT or SRC.is_relative_to(out) or out.is_relative_to(SRC):
        raise BuildError(f"--out {out}: výstup nesmí být kořen projektu, _src/ ani jejich nadřazená složka")
    if out.is_relative_to(SITE):
        raise BuildError(f"--out {out}: výstup nesmí ležet uvnitř site/ (statické soubory se kopírují odtud)")
    return out


def copy_static(out: Path, netlify: bool, preview: bool, target: str) -> list[str]:
    copied = []
    for name in STATIC_COMMON + (STATIC_NETLIFY if netlify else STATIC_GITHUB):
        src = SITE / name
        if not src.exists():
            warnings.append(f"site/{name}: neexistuje – do výstupu nezkopírováno")
            continue
        dst = out / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        copied.append(name + ("/" if src.is_dir() else ""))
    if netlify and preview:
        headers = out / "_headers"
        if headers.is_file():
            # Soubor byl právě zkopírován ze site/ – pravidlo se připíše jen jednou i při opakovaném buildu.
            text = read(headers)
            write(headers, text.rstrip("\n") + "\n" + NETLIFY_PREVIEW_HEADERS.format(target=target))
            if "_headers" in copied:
                copied[copied.index("_headers")] = "_headers (+ X-Robots-Tag: noindex, nofollow)"
        else:  # build to kontroluje předem; sem se dostane jen při souběžné změně site/
            warnings.append(f"{rel(headers)}: chybí – náhled na Netlify nemá hlavičku X-Robots-Tag: noindex")
    if not netlify:
        stale = [n for n in STATIC_NETLIFY if (out / n).exists()]
        if stale:
            warnings.append(
                f"{out}: obsahuje {', '.join(stale)} z dřívějšího buildu pro Netlify – "
                "GitHub Pages je ignoruje, ale zveřejní; před nahráním je smažte"
            )
    return copied


def build(strict: bool, target_arg: str | None, out_arg: str | None) -> int:
    cfg, target, preview, netlify = load_config(strict, target_arg)
    if errors:
        raise BuildError("chyby v config.json")
    out = resolve_out(out_arg)
    base = cfg["BASE_PATH"]
    if netlify and preview and out != SITE and not (SITE / "_headers").is_file():
        errors.append("site/_headers: chybí – náhled na Netlify ho potřebuje (build do něj přidává X-Robots-Tag: noindex)")
    if netlify and preview and out == SITE:
        warnings.append(
            "výstup je site/: do zdrojového site/_headers se hlavička X-Robots-Tag: noindex nepřidává – "
            f"náhled na Netlify nasazujte z jiné složky (--target {target} --out _dist)"
        )

    jobs: list[tuple[Path, str, str]] = []  # (výstup, text před dosazením tokenů, kind)
    # Stránky webu: cesta od kořene -> má být v sitemap ostrého webu (kontrola _src/sitemap.xml).
    pages: dict[str, bool] = {"/": True}

    jobs.append((out / "index.html", read(SRC / "index.html"), "html"))

    template = read(SRC / "page-template.html")
    check_template(template)
    legal_dir = SRC / "legal"
    legal_files = sorted(legal_dir.glob("*.html"))
    if not legal_files:
        errors.append(f"{rel(legal_dir)}: žádné právní fragmenty")
    for frag in legal_files:
        meta, content = parse_legal(frag)
        # Volitelné "robots" v meta přepíše robots stránky jen u ostrého webu; náhled je vždy noindex,nofollow.
        page_robots = cfg["ROBOTS"] if preview else meta.get("robots", cfg["ROBOTS"])
        indexable = not re.search(r"(?:^|,)\s*(?:noindex|none)\s*(?:,|$)", meta.get("robots", ""))
        pages[meta["path"]] = indexable and meta.get("sitemap", True) is not False
        values = {
            "TITLE": esc_html_keep_entities(meta["title"]),
            "DESCRIPTION": esc_html_keep_entities(meta["description"]),
            "PATH": esc_html(meta["path"]),
            "H1": esc_html_keep_entities(meta["h1"]),
            "LEAD": esc_html_keep_entities(meta["lead"]),
            "ROBOTS": esc_html(page_robots),
            "CONTENT": content,
        }
        page = fill_template(template, values)
        jobs.append((out / frag.stem / "index.html", page, "html"))

    jobs.append((out / "404.html", read(SRC / "404.html"), "html"))
    robots_src = SRC / ("robots-preview.txt" if preview else "robots.txt")
    jobs.append((out / "robots.txt", read(robots_src), "txt"))
    if not preview:
        # Náhled je celý noindex – sitemap se seznamem neindexovatelných adres by si odporovala.
        jobs.append((out / "sitemap.xml", read(SRC / "sitemap.xml"), "xml"))

    rendered: list[tuple[Path, str]] = []
    prefixed = 0
    forms: list[str] = []
    for out_path, text, kind in jobs:
        label = rel(out_path)
        result = substitute(text, cfg, kind, label)
        if kind == "html":
            result, n = apply_base_path(result, base)
            prefixed += n
            check_page(result, label, preview, base)
            forms += check_netlify_forms(result, label, base, set(pages))
        elif out_path.name == "sitemap.xml":
            check_sitemap(result, label, cfg["SITE_URL"], pages)
        check_leftovers(result, label)
        rendered.append((out_path, result))

    if errors:
        raise BuildError("výstup obsahuje chyby – nic nebylo zapsáno")

    for out_path, result in rendered:
        write(out_path, result)

    removed: list[str] = []
    if preview:
        stale = out / "sitemap.xml"
        if stale.is_file():
            try:
                if "<urlset" in read(stale):  # jen sitemap vygenerovaná dřívějším buildem
                    stale.unlink()
                    removed.append("sitemap.xml")
                else:
                    warnings.append(f"{rel(stale)}: náhled nemá mít sitemap – soubor neznám, nesmazán")
            except (OSError, UnicodeDecodeError) as exc:
                warnings.append(f"{rel(stale)}: starou sitemap se nepodařilo smazat ({exc})")

    copied: list[str] = []
    if out != SITE:
        try:
            copied = copy_static(out, netlify, preview, target)
        except OSError as exc:
            raise BuildError(f"kopírování statických souborů do {out} selhalo ({exc})")

    mode = "náhled, noindex,nofollow" if preview else "ostrý web, index,follow"
    mode += ", Netlify" if netlify else ", bez Netlify (_headers/_redirects se nekopírují)"
    print(f"Nutrivero build {cfg['BUILD_DATE']} – cíl {target} ({mode}) → {out}")
    print(f"  SITE_URL {cfg['SITE_URL']}   BASE_PATH {base or '(kořen)'}   hosting {cfg['HOSTING_SERVICE']}")
    for out_path, result in rendered:
        name = out_path.relative_to(out).as_posix()
        print(f"  zapsáno  {name:40s} {len(result.encode('utf-8')):>8,d} B".replace(",", " "))
    for name in removed:
        print(f"  smazáno  {name} (náhled je noindex, sitemap nemá)")
    if base:
        print(f"  doplněno {base} do {prefixed} kořenových adres v HTML")
    if copied:
        print(f"  zkopírováno ze site/: {', '.join(copied)}")
    if forms:
        if netlify:
            print(f"  formuláře Netlify Forms: {', '.join(forms)} (v Netlify musí být zapnutá detekce formulářů)")
        else:
            print(f"  pozn.: formuláře Netlify Forms ({', '.join(forms)}) na tomto hostingu nefungují – "
                  "odeslání skončí chybou s odkazem na e-mail")
    return len(rendered)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Sestaví web z _src/ (výchozí výstup site/).")
    ap.add_argument("--target", choices=TARGET_NAMES,
                    help="cíl nasazení: netlify-nahled = náhled na Netlify (noindex), "
                         "preview = náhled na GitHub Pages (noindex), production = ostrý web; "
                         "výchozí je TARGET v config.json")
    ap.add_argument("--out", metavar="SLOŽKA",
                    help="výstupní složka (výchozí site/); jiná složka dostane i statické soubory ze site/")
    ap.add_argument("--strict", action="store_true",
                    help="zástupné hodnoty v config.json považovat za chybu (pro produkci)")
    args = ap.parse_args()

    try:
        count = build(args.strict, args.target, args.out)
    except BuildError as exc:
        for w in warnings:
            print(f"UPOZORNĚNÍ: {w}", file=sys.stderr)
        for e in errors:
            print(f"CHYBA: {e}", file=sys.stderr)
        print(f"BUILD SELHAL: {exc}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"UPOZORNĚNÍ: {w}")
    print(f"Hotovo: {count} souborů, {len(warnings)} upozornění.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
