#!/usr/bin/env python3
"""Nutrivero – sestavení statického webu z _src/ (výchozí výstup site/).

Spuštění (z libovolné složky):
    python "_src/build.py"                               # výchozí cíl z config.json (TARGET), výstup do site/
    python "_src/build.py" --target preview              # náhled na GitHub Pages (/nutrivero-nahled, noindex)
    python "_src/build.py" --target production --strict  # ostrý web v kořeni domény; zástupné hodnoty = chyba
    python "_src/build.py" --target preview --out ../nutrivero-nahled
                                                         # kompletní web do jiné složky (HTML + statické soubory)

Cíle (config.json → "targets"):
  * společné hodnoty tokenů jsou v kořeni config.json, hodnoty cíle (targets.<cíl>) je doplní/přepíšou,
  * výchozí cíl je "TARGET" v config.json, přepínač --target ho přepíše,
  * každý cíl určuje SITE_URL, BASE_PATH (podsložka, kde web běží; "" = kořen domény), PREVIEW
    (true = noindex,nofollow) a údaje o hostingu HOSTING_NAME / _SERVICE / _ADDRESS / _PRIVACY_URL.

Co dělá:
  * načte _src/config.json, doplní vypočtené tokeny %%BUILD_DATE%% (dnešní datum, ISO),
    %%UPDATED_ISO%% (UPDATED „26. 10. 2026“ jako 2026-10-26, lastmod právních stránek),
    %%ROBOTS%% (index,follow / noindex,nofollow podle PREVIEW) a %%ROBOTS_404%% (vždy noindex),
  * _src/index.html  -> <výstup>/index.html
  * _src/legal/<slug>.html (první řádek <!--meta {...} -->) + _src/page-template.html
                     -> <výstup>/<slug>/index.html
  * _src/404.html    -> <výstup>/404.html
  * _src/robots.txt (ostrý web) nebo _src/robots-preview.txt (náhled) -> <výstup>/robots.txt
  * _src/sitemap.xml -> <výstup>/sitemap.xml jen u ostrého webu (lastmod = HOME_UPDATED_ISO
    u hlavní stránky, UPDATED_ISO u právních); náhled (noindex) sitemap nemá a starou
    sitemap.xml z dřívějšího buildu ve výstupu smaže,
  * v každém výstupu nahradí %%TOKENY%% a escapuje hodnoty podle kontextu
    (HTML text/atributy, JSON-LD, XML, prostý text),
  * v HTML doplní BASE_PATH před každou kořenovou adresu ("/…") v atributech href, src, srcset,
    imagesrcset, poster, action a data-src (nemění "//…", absolutní URL, mailto:, tel:, "#…"),
  * selže (exit 1) a vypíše soubor + token, pokud ve výstupu zůstane %%…%% nebo {{…}},
  * pokud je výstupní složka jiná než site/, zkopíruje do ní ze site/ i statické soubory
    (assets/, favicon.ico, apple-touch-icon.png, site.webmanifest, .nojekyll; u ostrého webu
    i _headers a _redirects pro Netlify), takže vznikne kompletní web k nasazení.

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

TARGET_NAMES = ("preview", "production")
DEFAULT_TARGET = "preview"

# Statické soubory ze site/, které se kopírují do jiné výstupní složky (--out).
STATIC_COMMON = ["assets", "favicon.ico", "apple-touch-icon.png", "site.webmanifest", ".nojekyll"]
STATIC_NETLIFY = ["_headers", "_redirects"]  # jen ostrý web (Netlify); GitHub Pages je ignoruje

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


class BuildError(Exception):
    pass


errors: list[str] = []
warnings: list[str] = []


def read(path: Path) -> str:
    # utf-8-sig odstraní případný BOM; textový režim sjednotí konce řádků na \n
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
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
def load_config(strict: bool, target_arg: str | None) -> tuple[dict[str, str], str, bool]:
    """Vrátí (tokeny, název cíle, PREVIEW)."""
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
        raise BuildError("config.json: chybí objekt \"targets\" s cíli \"preview\" a \"production\"")
    default_target = raw.get("TARGET", DEFAULT_TARGET)
    if not isinstance(default_target, str):
        raise BuildError("config.json: TARGET musí být řetězec (\"preview\" nebo \"production\")")
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
    preview: bool | None = None
    for key, (val, where) in merged.items():
        if key == "PREVIEW":
            if isinstance(val, bool):
                preview = val
            else:
                errors.append(f"{where}: PREVIEW musí být true nebo false (bez uvozovek)")
            continue
        if not isinstance(val, str):
            errors.append(f"{where}: {key} musí být řetězec, je {type(val).__name__}")
            continue
        cfg[key] = val.strip()

    if preview is None and not any("PREVIEW" in e for e in errors):
        errors.append(f"config.json targets.{target}: chybí PREVIEW (true = náhled s noindex, false = ostrý web)")
    preview = bool(preview)

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

    return cfg, target, preview


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


def resolve_out(out_arg: str | None) -> Path:
    out = Path(out_arg).expanduser().resolve() if out_arg else SITE
    if out == SITE:
        return out
    if out == ROOT or SRC.is_relative_to(out) or out.is_relative_to(SRC):
        raise BuildError(f"--out {out}: výstup nesmí být kořen projektu, _src/ ani jejich nadřazená složka")
    if out.is_relative_to(SITE):
        raise BuildError(f"--out {out}: výstup nesmí ležet uvnitř site/ (statické soubory se kopírují odtud)")
    return out


def copy_static(out: Path, netlify: bool) -> list[str]:
    copied = []
    for name in STATIC_COMMON + (STATIC_NETLIFY if netlify else []):
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
    if not netlify:
        stale = [n for n in STATIC_NETLIFY if (out / n).exists()]
        if stale:
            warnings.append(
                f"{out}: obsahuje {', '.join(stale)} z dřívějšího buildu ostrého webu – "
                "GitHub Pages je ignoruje, ale zveřejní; před nahráním je smažte"
            )
    return copied


def build(strict: bool, target_arg: str | None, out_arg: str | None) -> int:
    cfg, target, preview = load_config(strict, target_arg)
    if errors:
        raise BuildError("chyby v config.json")
    out = resolve_out(out_arg)
    base = cfg["BASE_PATH"]

    jobs: list[tuple[Path, str, str]] = []  # (výstup, text před dosazením tokenů, kind)

    jobs.append((out / "index.html", read(SRC / "index.html"), "html"))

    template = read(SRC / "page-template.html")
    check_template(template)
    legal_dir = SRC / "legal"
    legal_files = sorted(legal_dir.glob("*.html"))
    if not legal_files:
        errors.append(f"{rel(legal_dir)}: žádné právní fragmenty")
    for frag in legal_files:
        meta, content = parse_legal(frag)
        values = {
            "TITLE": esc_html_keep_entities(meta["title"]),
            "DESCRIPTION": esc_html_keep_entities(meta["description"]),
            "PATH": esc_html(meta["path"]),
            "H1": esc_html_keep_entities(meta["h1"]),
            "LEAD": esc_html_keep_entities(meta["lead"]),
            "ROBOTS": cfg["ROBOTS"],
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
    for out_path, text, kind in jobs:
        label = rel(out_path)
        result = substitute(text, cfg, kind, label)
        if kind == "html":
            result, n = apply_base_path(result, base)
            prefixed += n
            check_page(result, label, preview, base)
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
            copied = copy_static(out, netlify=not preview)
        except OSError as exc:
            raise BuildError(f"kopírování statických souborů do {out} selhalo ({exc})")

    mode = "náhled, noindex,nofollow" if preview else "ostrý web, index,follow"
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
    return len(rendered)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Sestaví web z _src/ (výchozí výstup site/).")
    ap.add_argument("--target", choices=TARGET_NAMES,
                    help="cíl nasazení: preview = náhled na GitHub Pages (noindex), "
                         "production = ostrý web; výchozí je TARGET v config.json")
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
