#!/usr/bin/env python3
"""Static site generator for Clinic Sline.

Usage: python3 build.py
Reads site.json and content/articles/*.md, writes the finished site to public/.
No third-party packages needed.
"""
import html
import json
import pathlib
import re
import shutil
import sys
import urllib.parse
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "public"
CFG = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
LANGS = CFG["languages"]
LANG_CODES = [l["code"] for l in LANGS]
LANG_BY = {l["code"]: l for l in LANGS}
UI = CFG["ui"]
SITE = CFG["site_url"].rstrip("/")
BRAND = CFG["brand"]
WA_NUMBER = CFG["whatsapp"]
ADDRESS = CFG.get("address", "")
E = html.escape


# ---------- text helpers ----------

def inline(t):
    t = E(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def md(text):
    out, items, para = [], [], []

    def flush_items():
        nonlocal items
        if items:
            out.append("<ul>" + "".join("<li>%s</li>" % inline(i) for i in items) + "</ul>")
            items = []

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para = []

    for line in text.splitlines():
        s = line.strip()
        if not s:
            flush_items()
            flush_para()
        elif s.startswith("### "):
            flush_items()
            flush_para()
            out.append("<h3>%s</h3>" % inline(s[4:]))
        elif s.startswith("## "):
            flush_items()
            flush_para()
            out.append("<h2>%s</h2>" % inline(s[3:]))
        elif s.startswith("- "):
            flush_para()
            items.append(s[2:])
        else:
            flush_items()
            para.append(s)
    flush_items()
    flush_para()
    return "\n".join(out)


def split_meta(block):
    meta, lines, i = {}, block.strip("\n").splitlines(), 0
    while i < len(lines) and lines[i].strip():
        k, _, v = lines[i].partition(":")
        meta[k.strip()] = v.strip()
        i += 1
    return meta, "\n".join(lines[i + 1:]).strip()


def split_faq(body):
    main, _, faq = body.partition("\n::: faq\n")
    pairs, q = [], None
    for line in faq.splitlines():
        if line.startswith("Q:"):
            q = line[2:].strip()
        elif line.startswith("A:") and q:
            pairs.append((q, line[2:].strip()))
            q = None
    return main.strip(), pairs


# ---------- content ----------

def load_articles():
    arts = []
    for p in sorted((ROOT / "content" / "articles").glob("*.md")):
        parts = re.split(r"^=== (\w+)\s*$", p.read_text(encoding="utf-8"), flags=re.M)
        pre, _ = split_meta(parts[0])
        # Drafts wait for the doctor's review. `python3 build.py --drafts` previews them.
        if pre.get("draft", "").lower() == "true" and "--drafts" not in sys.argv:
            continue
        art = {"id": p.stem, "updated": pre.get("updated", str(date.today())), "langs": {}}
        for i in range(1, len(parts), 2):
            lang = parts[i]
            if lang not in LANG_BY:
                raise SystemExit("%s: unknown language block '%s'" % (p.name, lang))
            meta, body = split_meta(parts[i + 1])
            for key in ("slug", "title", "description"):
                if key not in meta:
                    raise SystemExit("%s [%s]: missing '%s'" % (p.name, lang, key))
            main, faq = split_faq(body)
            art["langs"][lang] = {
                "slug": meta["slug"], "title": meta["title"],
                "description": meta["description"], "keyword": meta.get("keyword", ""),
                "html": md(main), "faq": faq,
            }
        arts.append(art)
    arts.sort(key=lambda a: a["updated"], reverse=True)
    return arts


# ---------- page pieces ----------

def wa_link(lang, tag):
    msg = "%s [web:%s]" % (UI[lang]["wa_msg"], tag)
    return "https://wa.me/%s?text=%s" % (WA_NUMBER, urllib.parse.quote(msg))


def ld_script(data):
    return '<script type="application/ld+json">%s</script>' % json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def page(lang, title, desc, path, alts, body, ld=None, og="website"):
    l = LANG_BY[lang]
    u = UI[lang]
    canon = SITE + path
    hrefl = "".join('<link rel="alternate" hreflang="%s" href="%s%s">' % (c, SITE, p) for c, p in alts.items())
    if "en" in alts:
        hrefl += '<link rel="alternate" hreflang="x-default" href="%s%s">' % (SITE, alts["en"])
    switch = "".join(
        '<li><a href="%s" hreflang="%s" lang="%s"%s>%s</a></li>' % (
            alts.get(c, "/%s/" % c), c, c, ' aria-current="page"' if c == lang else "", E(LANG_BY[c]["name"]))
        for c in LANG_CODES)
    ld_html = "".join(ld_script(x) for x in (ld or []))
    year = date.today().year
    addr = "<p>%s</p>" % E(ADDRESS) if ADDRESS else ""
    return """<!doctype html>
<html lang="{lang}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
{hrefl}
<meta property="og:type" content="{og}">
<meta property="og:site_name" content="{brand}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canon}">
<meta property="og:locale" content="{locale}">
<link rel="stylesheet" href="/assets/style.css">
{ld}
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="/{lang}/">{brand}</a><nav aria-label="Language"><ul class="langs">{switch}</ul></nav></div></header>
<main>
{body}
</main>
<footer class="bottom"><div class="wrap"><p>{disclaimer}</p>{addr}<p>© {year} {brand} · Istanbul</p></div></footer>
<a class="wa" href="{wa}" rel="noopener">WhatsApp</a>
</body>
</html>
""".format(lang=lang, dir=l["dir"], title=E(title), desc=E(desc), canon=canon, hrefl=hrefl, og=og,
           brand=E(BRAND), locale=l["locale"], ld=ld_html, switch=switch, body=body,
           disclaimer=E(u["disclaimer"]), addr=addr, year=year, wa=E(wa_link(lang, lang + "/float")))


def home_page(lang, arts):
    u = UI[lang]
    steps = "".join("<li><b>%s</b><span>%s</span></li>" % (E(t), E(d)) for t, d in u["steps"])
    cards = "".join(
        '<a class="guide" href="/%s/%s/"><b>%s</b><span>%s</span><em>%s</em></a>' % (
            lang, a["langs"][lang]["slug"], E(a["langs"][lang]["title"]), E(a["langs"][lang]["description"]), E(u["read"]))
        for a in arts if lang in a["langs"])
    body = """<section class="hero"><div class="wrap">
<h1>{h1}</h1>
<p>{sub}</p>
<a class="btn" href="{wa}" rel="noopener">{cta}</a>
</div></section>
<section class="block"><div class="wrap"><h2>{st}</h2><ol class="steps">{steps}</ol></div></section>
<section class="block" id="guides"><div class="wrap"><h2>{latest}</h2><div class="guides">{cards}</div></div></section>""".format(
        h1=E(u["hero_title"]), sub=E(u["hero_sub"]), wa=E(wa_link(lang, lang + "/home")), cta=E(u["cta"]),
        st=E(u["steps_title"]), steps=steps, latest=E(u["latest"]), cards=cards)
    ld = [{
        "@context": "https://schema.org", "@type": "MedicalClinic", "name": BRAND, "url": SITE + "/%s/" % lang,
        "description": u["hero_sub"], "inLanguage": lang,
        "address": {"@type": "PostalAddress", "addressLocality": "Istanbul", "addressCountry": "TR"},
        "availableLanguage": [LANG_BY[c]["name"] for c in LANG_CODES],
    }]
    return page(lang, "%s | %s" % (BRAND, u["hero_title"]), u["hero_sub"], "/%s/" % lang,
                {c: "/%s/" % c for c in LANG_CODES}, body, ld)


def article_page(lang, art):
    u = UI[lang]
    a = art["langs"][lang]
    path = "/%s/%s/" % (lang, a["slug"])
    alts = {c: "/%s/%s/" % (c, art["langs"][c]["slug"]) for c in art["langs"]}
    faq_html = ""
    if a["faq"]:
        faq_html = "<h2>%s</h2>" % E(u["faq"]) + "".join("<h3>%s</h3><p>%s</p>" % (E(q), inline(an)) for q, an in a["faq"])
    body = """<div class="wrap narrow"><article>
<p class="crumb"><a href="/{lang}/">{brand}</a></p>
<h1>{h1}</h1>
<p class="meta">{reviewed}</p>
{content}
{faq}
<aside class="ctabox"><h2>{cbt}</h2><p>{cbx}</p><a class="btn" href="{wa}" rel="noopener">{cta}</a></aside>
</article></div>""".format(
        lang=lang, brand=E(BRAND), h1=E(a["title"]), reviewed=E(u["reviewed"].format(date=art["updated"])),
        content=a["html"], faq=faq_html, cbt=E(u["cta_box_title"]), cbx=E(u["cta_box_text"]),
        wa=E(wa_link(lang, "%s/%s" % (lang, a["slug"]))), cta=E(u["cta"]))
    ld = [{
        "@context": "https://schema.org", "@type": "MedicalWebPage", "name": a["title"], "headline": a["title"],
        "description": a["description"], "inLanguage": lang, "url": SITE + path,
        "lastReviewed": art["updated"], "dateModified": art["updated"],
        "author": {"@type": "Organization", "name": BRAND},
        "publisher": {"@type": "MedicalClinic", "name": BRAND,
                      "address": {"@type": "PostalAddress", "addressLocality": "Istanbul", "addressCountry": "TR"}},
    }]
    if a["faq"]:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": lang,
                   "mainEntity": [{"@type": "Question", "name": q,
                                   "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", an)}}
                                  for q, an in a["faq"]]})
    return page(lang, "%s | %s" % (a["title"], BRAND), a["description"], path, alts, body, ld, og="article")


# ---------- files ----------

def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets")
    arts = load_articles()
    urls = []  # (path, lastmod, alternates)
    newest = max([a["updated"] for a in arts] or [str(date.today())])

    for lang in LANG_CODES:
        write("%s/index.html" % lang, home_page(lang, arts))
        urls.append(("/%s/" % lang, newest, {c: "/%s/" % c for c in LANG_CODES}))
    for art in arts:
        alts = {c: "/%s/%s/" % (c, art["langs"][c]["slug"]) for c in art["langs"]}
        for lang in art["langs"]:
            slug = art["langs"][lang]["slug"]
            write("%s/%s/index.html" % (lang, slug), article_page(lang, art))
            urls.append(("/%s/%s/" % (lang, slug), art["updated"], alts))

    # sitemap with hreflang alternates
    rows = []
    for path, mod, alts in urls:
        links = "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s%s"/>' % (c, SITE, p) for c, p in alts.items())
        rows.append("<url><loc>%s%s</loc><lastmod>%s</lastmod>%s</url>" % (SITE, path, mod, links))
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n%s\n</urlset>\n' % "\n".join(rows))

    # robots.txt: everyone, including AI search crawlers, is welcome
    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot", "Google-Extended", "Applebot-Extended"]
    robots = "User-agent: *\nAllow: /\n\n" + "".join("User-agent: %s\nAllow: /\n\n" % b for b in bots)
    write("robots.txt", robots + "Sitemap: %s/sitemap.xml\n" % SITE)

    # llms.txt: short guide for AI assistants
    lines = ["# %s" % BRAND, "",
             "> Hair transplant clinic in Istanbul, Turkey. Patients from Turkey, Europe and Arabic-speaking countries. "
             "Languages: " + ", ".join(LANG_BY[c]["name"] for c in LANG_CODES) + ".", "",
             "Every treatment plan is confirmed by a licensed doctor. Articles are medically reviewed. "
             "Prices are fixed and given in writing after a doctor reviews the patient's photos.", ""]
    for lang in LANG_CODES:
        lines.append("## %s" % LANG_BY[lang]["name"])
        lines.append("- [%s](%s/%s/)" % (BRAND, SITE, lang))
        for art in arts:
            if lang in art["langs"]:
                a = art["langs"][lang]
                lines.append("- [%s](%s/%s/%s/): %s" % (a["title"], SITE, lang, a["slug"], a["description"]))
        lines.append("")
    write("llms.txt", "\n".join(lines))

    # root: redirect to English, with a language-aware fallback page
    write("_redirects", "/  /en/  302\n")
    opts = json.dumps(LANG_CODES)
    write("index.html", """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>%s</title>
<meta name="robots" content="noindex"><link rel="canonical" href="%s/en/">
<link rel="alternate" hreflang="x-default" href="%s/en/">
<meta http-equiv="refresh" content="1;url=/en/">
<script>var L=%s,n=(navigator.language||"en").slice(0,2);location.replace("/"+(L.indexOf(n)>-1?n:"en")+"/")</script>
</head><body><p><a href="/en/">English</a></p></body></html>
""" % (E(BRAND), SITE, SITE, opts))
    write("404.html", '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>404 | %s</title>'
          '<meta name="robots" content="noindex"><link rel="stylesheet" href="/assets/style.css"></head>'
          '<body><div class="wrap narrow"><h1>404</h1><p><a href="/en/">%s</a></p></div></body></html>\n' % (E(BRAND), E(BRAND)))

    n_pages = sum(1 for _ in OUT.rglob("index.html"))
    print("Built %d articles, %d pages in public/" % (len(arts), n_pages))


if __name__ == "__main__":
    main()
