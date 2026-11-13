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
PHONE = CFG.get("phone", "")
HOURS = CFG.get("hours", "")
MAPS = CFG.get("maps_url", "")
REVIEWS = CFG.get("reviews_url", "")
E = html.escape
H = json.loads((ROOT / "content" / "home.json").read_text(encoding="utf-8"))
TL_UNIT = {"en": "months", "tr": "ay", "de": "Monate", "fr": "mois", "ar": "أشهر", "ru": "мес."}
GUIDES_SLUG = {"en": "guides", "tr": "rehberler", "de": "ratgeber", "fr": "guides", "ar": "adilla", "ru": "stati"}
PAGE_SLUGS = {}  # page id -> {lang: slug}


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

def load_articles(sub="articles"):
    arts = []
    for p in sorted((ROOT / "content" / sub).glob("*.md")):
        parts = re.split(r"^=== (\w+)\s*$", p.read_text(encoding="utf-8"), flags=re.M)
        pre, _ = split_meta(parts[0])
        # Drafts wait for the doctor's review. `python3 build.py --drafts` previews them.
        if pre.get("draft", "").lower() == "true" and "--drafts" not in sys.argv:
            continue
        art = {"id": p.stem, "updated": pre.get("updated", str(date.today())), "langs": {},
               "reviewed": pre.get("reviewed", "").lower() == "true", "is_page": sub != "articles"}
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

FLAG = {"en": "🇬🇧", "tr": "🇹🇷", "de": "🇩🇪", "fr": "🇫🇷", "ar": "🇦🇪", "ru": "🇷🇺"}


def form_html(lang):
    f = H[lang]["form"]
    opt = lambda xs: "".join("<option>%s</option>" % E(x) for x in xs)
    data = {"wa": "https://wa.me/%s?text=" % WA_NUMBER, "hello": UI[lang]["wa_msg"], "msg": f["msg"], "tag": "[web:%s/form]" % lang}
    return ('<form class="lead-form" id="lead-form" novalidate><h2>%s</h2><p>%s</p>'
            '<label>%s<select name="c">%s</select></label>'
            '<label>%s<select name="g">%s</select></label>'
            '<label>%s<input name="n" autocomplete="name" required></label>'
            '<label>%s<span class="ph"><select name="cc" aria-label="+">%s</select><input name="p" type="tel" inputmode="tel" autocomplete="tel-national" required></span></label>'
            '<label>%s<select name="l">%s</select></label>'
            '<button class="btn" type="submit">%s</button><p class="gnote">%s</p>'
            '<script type="application/json" id="lead-data">%s</script></form>') % (
        E(f["title"]), E(f["sub"]), E(f["country"]), opt(f["countries"]), E(f["gender"]), opt(f["g"]), E(f["name"]), E(f["phone"]),
        opt(["+90", "+49", "+44", "+33", "+31", "+966", "+971", "+7", "+1", "+43", "+41", "+32"]), E(f["lang"]), opt(f["langs"]),
        E(f["submit"]), E(f["note"]), json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


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
            alts.get(c, "/%s/" % c), c, c, ' aria-current="page"' if c == lang else "", FLAG[c] + " " + E(LANG_BY[c]["name"]))
        for c in LANG_CODES)
    ld_html = "".join(ld_script(x) for x in (ld or []))
    year = date.today().year
    addr = ("<p>%s</p>" % E(ADDRESS) if ADDRESS else "") + contact_html()
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
<meta property="og:image" content="{site}/assets/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/assets/favicon-256.png" sizes="256x256" type="image/png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta name="theme-color" content="#102a3a">
<link rel="stylesheet" href="/assets/style.css">
<script>document.documentElement.classList.add("js")</script>
{ld}
</head>
<body>
<div class="progress" aria-hidden="true"></div>
<header class="top"><div class="wrap"><a class="brand" href="/{lang}/" aria-label="{brand}"><img src="/assets/logo-header.png" alt="{brand}" width="130" height="40"></a>{menu}<nav aria-label="Language"><details class="langsel"><summary>{curflag} {curcode}</summary><ul class="langs">{switch}</ul></details></nav></div></header>
<main>
{body}
</main>
<footer class="bottom"><div class="wrap"><p>{disclaimer}</p>{addr}<p>© {year} {brand} · Istanbul</p></div></footer>
<a class="wa" href="{wa}" rel="noopener">WhatsApp</a>
<script src="/assets/site.js" defer></script>
</body>
</html>
""".format(lang=lang, dir=l["dir"], title=E(title), desc=E(desc), canon=canon, hrefl=hrefl, og=og,
           brand=E(BRAND), curflag=FLAG[lang], curcode=lang.upper(), site=SITE, locale=l["locale"], ld=ld_html, switch=switch, menu=nav_html(lang), body=body,
           disclaimer=E(u["disclaimer"]), addr=addr, year=year, wa=E(wa_link(lang, lang + "/float")))



GALLERY = {
    "en": ("Patient results", "Patients of Clinic S Line, shown with their consent. Results vary from person to person and are not a guarantee. Suitability is decided at a medical consultation.", "Patient before and after hair transplant"),
    "tr": ("Hasta sonuçları", "Clinic S Line hastaları, rızalarıyla paylaşılmıştır. Sonuçlar kişiden kişiye değişir, garanti değildir. Uygunluk muayenede belirlenir.", "Hastanın saç ekimi öncesi ve sonrası"),
    "de": ("Patientenergebnisse", "Patienten von Clinic S Line, veröffentlicht mit ihrer Einwilligung. Ergebnisse sind individuell verschieden und keine Garantie. Die Eignung wird in der individuellen Beratung geklärt.", "Patient vor und nach der Haartransplantation"),
    "fr": ("Résultats de patients", "Patients de Clinic S Line, publiés avec leur accord. Les résultats varient d'une personne à l'autre et ne sont pas garantis. L'indication est établie lors de la consultation médicale.", "Patient avant et après la greffe de cheveux"),
    "ar": ("نتائج المرضى", "مرضى Clinic S Line، تُعرض صورهم بموافقتهم. تختلف النتائج من شخص لآخر ولا تُعدّ ضمانًا. تُحدَّد الملاءمة في الاستشارة الطبية.", "مريض قبل زراعة الشعر وبعدها"),
    "ru": ("Результаты пациентов", "Пациенты Clinic S Line, фото публикуются с их согласия. Результаты индивидуальны и не гарантируются. Показания определяются на индивидуальной консультации.", "Пациент до и после пересадки волос"),
}
CLINIC = {
    "en": ("Our clinic", "Clinic interior"), "tr": ("Kliniğimiz", "Klinik içi"), "de": ("Unsere Klinik", "Klinik von innen"),
    "fr": ("Notre clinique", "Intérieur de la clinique"), "ar": ("عيادتنا", "داخل العيادة"), "ru": ("Наша клиника", "Интерьер клиники"),
}
N_CLINIC = len(list((ROOT / "assets" / "clinic").glob("clinic-*.jpg")))
N_RESULTS = len(list((ROOT / "assets" / "results").glob("result-*.jpg")))


def nav_html(lang):
    n = H[lang]["nav"]
    items = []
    for pid, key in (("treatments", "treatments"), ("process", "process")):
        if lang in PAGE_SLUGS.get(pid, {}):
            items.append(("/%s/%s/" % (lang, PAGE_SLUGS[pid][lang]), n[key]))
    items.append(("/%s/#results" % lang, n["results"]))
    items.append(("/%s/%s/" % (lang, GUIDES_SLUG[lang]), n["guides"]))
    items.append((wa_link(lang, lang + "/nav"), n["contact"]))
    return '<nav class="menu" aria-label="Menu"><ul>%s</ul></nav>' % "".join(
        '<li><a href="%s">%s</a></li>' % (E(h), E(t)) for h, t in items)


def breadcrumb_ld(lang, crumbs):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + path}
        for i, (name, path) in enumerate(crumbs)]}


def related_html(lang, arts, current):
    """Internal links at the end of every article/page: other pages first, then other guides."""
    n = H[lang]["nav"]
    links = []
    for pid, key in (("treatments", "treatments"), ("process", "process")):
        if lang in PAGE_SLUGS.get(pid, {}) and PAGE_SLUGS[pid][lang] != current:
            links.append(("/%s/%s/" % (lang, PAGE_SLUGS[pid][lang]), n[key]))
    for a in arts:
        if lang in a["langs"] and a["langs"][lang]["slug"] != current:
            links.append(("/%s/%s/" % (lang, a["langs"][lang]["slug"]), a["langs"][lang]["title"]))
    links = links[:5]
    if not links:
        return ""
    return '<nav class="related" aria-label="%s"><h2>%s</h2><ul>%s</ul></nav>' % (
        E(n["guides"]), E(n["guides"]), "".join('<li><a href="%s">%s</a></li>' % (E(h), E(t)) for h, t in links))


NOR = {
    1: [],
    2: [(24, 36, 9, 12), (96, 36, 9, 12)],
    3: [(22, 36, 16, 20), (98, 36, 16, 20)],
    4: [(20, 38, 18, 24), (100, 38, 18, 24), (60, 22, 20, 22), (60, 102, 9, 9)],
    5: [(20, 40, 20, 30), (100, 40, 20, 30), (60, 28, 28, 30), (60, 102, 15, 16)],
    6: [(60, 68, 31, 44)],
    7: [(60, 66, 36, 54)],
}


def norwood_svg(n):
    els = '<ellipse cx="60" cy="14" rx="32" ry="14" class="sk"/>' + "".join(
        '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" class="sk"/>' % e for e in NOR[n])
    return ('<svg viewBox="0 0 120 140" aria-hidden="true" focusable="false"><defs><clipPath id="hc%d">'
            '<ellipse cx="60" cy="72" rx="44" ry="54"/></clipPath></defs>'
            '<ellipse cx="14" cy="78" rx="5" ry="11" class="sk"/><ellipse cx="106" cy="78" rx="5" ry="11" class="sk"/>'
            '<ellipse cx="60" cy="72" rx="44" ry="54" class="hr"/><g clip-path="url(#hc%d)">%s</g>'
            '<path d="M54 20 L60 8 L66 20Z" class="sk"/></svg>') % (n, n, els)


def timeline_svg(lang):
    h = H[lang]
    pts = [(0, .18), (.5, .14), (1.5, .06), (3, .10), (4.5, .36), (6, .52), (9, .78), (12, .95)]
    P = [(60 + m * 44, 230 - d * 190) for m, d in pts]
    path = "M%.1f %.1f" % P[0]
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path += " C%.1f %.1f %.1f %.1f %.1f %.1f" % (c1 + c2 + p2)
    ticks = "".join('<line x1="%d" y1="232" x2="%d" y2="238" class="ax"/><text x="%d" y="256" text-anchor="middle" class="lb">%d</text>' % (
        60 + m * 44, 60 + m * 44, 60 + m * 44, m) for m in (0, 3, 6, 9, 12))
    marks = "".join('<g class="mk" style="--d:%.1fs"><circle cx="%.1f" cy="%.1f" r="15"/><text x="%.1f" y="%.1f" text-anchor="middle">%d</text></g>' % (
        .5 + k * .35, P[i][0], P[i][1], P[i][0], P[i][1] + 6, k + 1) for k, i in enumerate((1, 2, 4, 6, 7)))
    return ('<svg viewBox="0 0 640 275" class="chart" role="img" aria-label="%s"><line x1="60" y1="40" x2="60" y2="232" class="ax"/>'
            '<line x1="60" y1="232" x2="600" y2="232" class="ax"/><text x="66" y="30" class="lb">%s</text>'
            '<text x="600" y="274" text-anchor="end" class="lb">%s</text>%s'
            '<path d="%s" class="curve" pathLength="1"/>%s</svg>') % (
        E(h["tl_title"] + ". " + h["tl_note"]), E(h["tl_axis"]), E(TL_UNIT[lang]), ticks, path, marks)


def clinic_html(lang):
    if not N_CLINIC:
        return ""
    t, alt = CLINIC[lang]
    figs = "".join('<picture class="reveal" style="--d:%.2fs"><source srcset="/assets/clinic/clinic-%d.webp" type="image/webp"><img src="/assets/clinic/clinic-%d.jpg" alt="%s" loading="lazy" width="642" height="480"></picture>' % (
        (i % 3) * .08, i, i, E(alt)) for i in range(1, N_CLINIC + 1))
    return '<section class="block alt" id="clinic"><div class="wrap"><h2>%s</h2><div class="gallery">%s</div></div></section>' % (E(t), figs)


def gallery_html(lang):
    if not N_RESULTS:
        return ""
    t, note, alt = GALLERY[lang]
    figs = "".join('<picture class="reveal" style="--d:%.2fs"><source srcset="/assets/results/result-%d.webp" type="image/webp"><img src="/assets/results/result-%d.jpg" alt="%s" loading="lazy" width="900" height="900"></picture>' % (
        (i % 4) * .08, i, i, E(alt)) for i in range(1, N_RESULTS + 1))
    return ('<section class="block" id="results"><div class="wrap"><h2>%s</h2><div class="gallery">%s</div>'
            '<p class="gnote">%s</p></div></section>') % (E(t), figs, E(note))


TRUST_ICONS = [
    '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M6 30C14 12 34 12 42 30" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/><path d="M14 34h20" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/></svg>',
    '<svg viewBox="0 0 48 48" aria-hidden="true"><g fill="currentColor"><circle cx="14" cy="14" r="4"/><circle cx="24" cy="14" r="4"/><circle cx="34" cy="14" r="4"/><circle cx="14" cy="26" r="4"/><circle cx="24" cy="26" r="4"/><circle cx="34" cy="26" r="4"/><circle cx="24" cy="38" r="4"/></g></svg>',
    '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 10h20l12 12-14 14L8 24z" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linejoin="round"/><circle cx="17" cy="19" r="3" fill="currentColor"/></svg>',
    '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 6l15 6v11c0 10-7 17-15 19C16 40 9 33 9 23V12z" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linejoin="round"/><path d="M17 24l5 5 9-10" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
]


def trust_html(lang):
    t = H[lang]["trust"]
    cards = "".join('<div class="tr-card reveal" style="--d:%.2fs"><span class="tr-ic">%s</span><b>%s</b><span>%s</span></div>' % (
        i * .1, TRUST_ICONS[i], E(x), E(y)) for i, (x, y) in enumerate(t["items"]))
    return ('<section class="block trust" id="trust"><div class="wrap"><h2>%s</h2><p class="lead">%s</p><div class="tr-grid">%s</div>'
            '<p class="gnote">%s</p></div></section>') % (E(t["title"]), E(t["sub"]), cards, E(t["note"]))


def stats_html(lang):
    cells = "".join('<div class="stat"><b data-count="%d" data-lang="%s">%s+</b><span>%s</span></div>' % (
        s["n"], lang, format(s["n"], ",").replace(",", "."), E(s["label"])) for s in H[lang]["stats"])
    return '<section class="stats" aria-label="%s"><div class="wrap">%s</div></section>' % (E(BRAND), cells)


def contact_html():
    rows = []
    if PHONE:
        rows.append('<a href="tel:%s">%s</a>' % (E(re.sub(r"[^+\d]", "", PHONE)), E(PHONE)))
    if HOURS:
        rows.append("<span>%s</span>" % E(HOURS))
    if MAPS:
        rows.append('<a href="%s" rel="noopener">Maps</a>' % E(MAPS))
    if REVIEWS:
        rows.append('<a href="%s" rel="noopener">Google</a>' % E(REVIEWS))
    return '<p class="fcontact">%s</p>' % " · ".join(rows) if rows else ""


def home_page(lang, arts):
    u = UI[lang]
    h = H[lang]
    lp = lambda pid: "/%s/%s/" % (lang, PAGE_SLUGS[pid][lang]) if lang in PAGE_SLUGS.get(pid, {}) else "/%s/" % lang
    wa_home = wa_link(lang, lang + "/home")
    chips = "".join('<li>%s</li>' % E(c) for c in h["chips"])
    strands = "".join('<path d="M-20 %d C 200 %d, 380 %d, 640 %d S 980 %d, 1240 %d" style="--d:%ds"/>' % (
        60 + i * 38, 10 + i * 40, 150 + i * 30, 70 + i * 36, 20 + i * 40, 90 + i * 30, 14 + i * 3) for i in range(7))
    hero = ('<section class="hero"><svg class="strands" viewBox="0 0 1200 360" preserveAspectRatio="none" aria-hidden="true">%s</svg>'
            '<div class="wrap herogrid"><div><p class="eyebrow">%s</p><h1><span class="grad">%s</span></h1><p>%s</p>'
            '<p class="actions"><a class="btn" href="%s" rel="noopener">%s</a> <a class="btn ghost" href="%s">%s</a></p>'
            '<ul class="chips">%s</ul></div>%s</div></section>') % (
        strands, E(h["eyebrow"]), E(u["hero_title"]), E(u["hero_sub"]), E(wa_home), E(u["cta"]),
        E(lp("process")), E(h["cta2"]), chips, form_html(lang))

    words = [t for t, _ in h["treat"]] + list(h["chips"])
    track = "".join("<span>%s</span>" % E(w) for w in words)
    marquee = '<div class="marquee" aria-hidden="true"><div class="mtrack">%s%s</div></div>' % (track, track)
    treat = "".join('<div class="tcard reveal" style="--d:%.2fs"><b>%s</b><span>%s</span></div>' % (i * .1, E(t), E(d))
                    for i, (t, d) in enumerate(h["treat"]))
    treat_sec = ('<section class="block"><div class="wrap"><h2>%s</h2><div class="tgrid">%s</div>'
                 '<p><a class="more" href="%s">%s →</a></p></div></section>') % (
        E(h["treat_title"]), treat, E(lp("treatments")), E(h["treat_more"]))

    steps = "".join('<li class="reveal" style="--d:%.2fs"><b>%s</b><span>%s</span></li>' % (i * .12, E(t), E(d))
                    for i, (t, d) in enumerate(u["steps"]))
    steps_sec = '<section class="block alt"><div class="wrap"><h2>%s</h2><ol class="steps">%s</ol></div></section>' % (E(u["steps_title"]), steps)

    nor_btns = "".join('<button type="button" class="stage" data-n="%d" aria-pressed="false">%s<span>%s</span></button>' % (
        n, norwood_svg(n), E(h["nor_stage"].format(n=n))) for n in range(1, 8))
    interests = "".join('<label><input type="radio" name="int" value="%s"%s><span>%s</span></label>' % (
        E(x), " checked" if i == 0 else "", E(x)) for i, x in enumerate(h["interests"]))
    data = {"desc": h["nor_desc"], "stage": h["nor_stage"], "cta": h["nor_cta"], "tpl": h["wa_finder"],
            "wa": "https://wa.me/%s?text=" % WA_NUMBER, "tag": "[web:%s/finder]" % lang, "intro": h["nor_intro"]}
    nor_sec = ('<section class="block"><div class="wrap"><h2>%s</h2><p class="lead">%s</p><div class="stages" role="group" aria-label="%s">%s</div>'
               '<div class="norpanel" aria-live="polite"><p id="nor-desc">%s</p><fieldset class="ints"><legend>%s</legend>%s</fieldset>'
               '<a class="btn" id="nor-cta" href="%s" rel="noopener">%s</a><p class="gnote">%s</p></div>'
               '<script type="application/json" id="nor-data">%s</script></div></section>') % (
        E(h["nor_title"]), E(h["nor_intro"]), E(h["nor_title"]), nor_btns, E(h["nor_intro"]), E(h["nor_interest"]), interests,
        E(wa_home), E(u["cta"]), E(h["nor_note"]), json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    phases = "".join('<li class="reveal" style="--d:%.2fs"><b>%s</b><span>%s</span></li>' % (i * .1, E(w), E(t))
                     for i, (w, t) in enumerate(h["tl_phases"]))
    tl_sec = ('<section class="block alt"><div class="wrap"><h2>%s</h2><p class="lead">%s</p><div class="chartbox reveal">%s</div>'
              '<ol class="phases">%s</ol><p class="gnote">%s</p><p><a class="more" href="/%s/%s/">%s →</a></p></div></section>') % (
        E(h["tl_title"]), E(h["tl_intro"]), timeline_svg(lang), phases, E(h["tl_note"]), lang,
        next((a["langs"][lang]["slug"] for a in arts if a["id"] == "results-timeline" and lang in a["langs"]), ""),
        E(a_title(arts, "results-timeline", lang)))

    local_sec = ('<section class="block"><div class="wrap"><div class="localbox reveal"><h2>%s</h2><p>%s</p>'
                 '<a class="btn" href="%s" rel="noopener">%s</a></div></div></section>') % (
        E(h["local_title"]), E(h["local_text"]), E(wa_link(lang, lang + "/local")), E(h["local_cta"]))

    cards = "".join(
        '<a class="guide reveal" style="--d:%.2fs" href="/%s/%s/"><b>%s</b><span>%s</span><em>%s</em></a>' % (
            i * .1, lang, a["langs"][lang]["slug"], E(a["langs"][lang]["title"]), E(a["langs"][lang]["description"]), E(u["read"]))
        for i, a in enumerate([x for x in arts if lang in x["langs"]][:6]))
    guides_sec = ('<section class="block alt" id="guides"><div class="wrap"><h2>%s</h2><div class="guides">%s</div>'
                  '<p><a class="more" href="/%s/%s/">%s →</a></p></div></section>') % (
        E(u["latest"]), cards, lang, GUIDES_SLUG[lang], E(H[lang]["nav"]["guides"]))

    faq_sec = ('<section class="block"><div class="wrap narrow"><h2>%s</h2>%s</div></section>') % (
        E(u["faq"]), "".join('<details class="reveal"><summary>%s</summary><p>%s</p></details>' % (E(q), E(a)) for q, a in h["faq"]))

    cta_sec = ('<section class="block"><div class="wrap"><aside class="ctabox reveal"><h2>%s</h2><p>%s</p>'
               '<a class="btn" href="%s" rel="noopener">%s</a></aside></div></section>') % (
        E(u["cta_box_title"]), E(u["cta_box_text"]), E(wa_link(lang, lang + "/bottom")), E(u["cta"]))

    body = hero + marquee + stats_html(lang) + trust_html(lang) + treat_sec + steps_sec + nor_sec + tl_sec + gallery_html(lang) + clinic_html(lang) + local_sec + guides_sec + faq_sec + cta_sec
    alts = {c: "/%s/" % c for c in LANG_CODES}
    ld = [{
        "@context": "https://schema.org", "@type": "MedicalClinic", "name": BRAND, "logo": SITE + "/assets/logo-dark.png", "image": SITE + "/assets/og.png", "url": SITE + "/%s/" % lang,
        "description": u["hero_sub"], "inLanguage": lang, "medicalSpecialty": "Dermatology",
        "address": {"@type": "PostalAddress", "addressLocality": "Istanbul", "addressCountry": "TR"},
        "availableLanguage": [LANG_BY[c]["name"] for c in LANG_CODES],
    }, {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": SITE + "/%s/" % lang, "inLanguage": lang},
        {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": lang,
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in h["faq"]]}]
    return page(lang, "%s | %s" % (BRAND, u["hero_title"]), u["hero_sub"], "/%s/" % lang, alts, body, ld)


def a_title(arts, aid, lang):
    for a in arts:
        if a["id"] == aid and lang in a["langs"]:
            return a["langs"][lang]["title"]
    return ""


def guides_index(lang, arts):
    u, h = UI[lang], H[lang]
    cards = "".join(
        '<a class="guide" href="/%s/%s/"><b>%s</b><span>%s</span><em>%s</em></a>' % (
            lang, a["langs"][lang]["slug"], E(a["langs"][lang]["title"]), E(a["langs"][lang]["description"]), E(u["read"]))
        for a in arts if lang in a["langs"])
    body = ('<div class="wrap"><p class="crumb"><a href="/%s/">%s</a></p><h1>%s</h1><p class="lead">%s</p><div class="guides">%s</div>'
            '<aside class="ctabox"><h2>%s</h2><p>%s</p><a class="btn" href="%s" rel="noopener">%s</a></aside></div>') % (
        lang, E(BRAND), E(h["guides_title"]), E(h["guides_intro"]), cards, E(u["cta_box_title"]), E(u["cta_box_text"]),
        E(wa_link(lang, lang + "/guides")), E(u["cta"]))
    path = "/%s/%s/" % (lang, GUIDES_SLUG[lang])
    ld = [breadcrumb_ld(lang, [(BRAND, "/%s/" % lang), (h["guides_title"], path)]),
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": h["guides_title"], "inLanguage": lang, "url": SITE + path}]
    return page(lang, "%s | %s" % (h["guides_title"], BRAND), h["guides_intro"], path,
                {c: "/%s/%s/" % (c, GUIDES_SLUG[c]) for c in LANG_CODES}, body, ld)


def article_page(lang, art, arts):
    u = UI[lang]
    a = art["langs"][lang]
    path = "/%s/%s/" % (lang, a["slug"])
    if art["is_page"]:
        alts = {c: "/%s/%s/" % (c, art["langs"][c]["slug"]) for c in art["langs"]}
    else:
        alts = {c: "/%s/%s/" % (c, art["langs"][c]["slug"]) for c in art["langs"]}
    faq_html = ""
    if a["faq"]:
        faq_html = "<h2>%s</h2>" % E(u["faq"]) + "".join("<h3>%s</h3><p>%s</p>" % (E(q), inline(an)) for q, an in a["faq"])
    show_reviewed = art["reviewed"] and not art["is_page"]
    meta_line = u["reviewed" if show_reviewed else "updated_only"].format(date=art["updated"])
    crumb = '<a href="/%s/">%s</a>' % (lang, E(BRAND))
    if not art["is_page"]:
        crumb += ' › <a href="/%s/%s/">%s</a>' % (lang, GUIDES_SLUG[lang], E(H[lang]["nav"]["guides"]))
    body = """<div class="wrap narrow"><article>
<p class="crumb">{crumb}</p>
<h1>{h1}</h1>
<p class="meta">{reviewed}</p>
{content}
{faq}
<aside class="ctabox"><h2>{cbt}</h2><p>{cbx}</p><a class="btn" href="{wa}" rel="noopener">{cta}</a></aside>
{related}
</article></div>""".format(
        crumb=crumb, h1=E(a["title"]), reviewed=E(meta_line), content=a["html"], faq=faq_html, cbt=E(u["cta_box_title"]),
        cbx=E(u["cta_box_text"]), wa=E(wa_link(lang, "%s/%s" % (lang, a["slug"]))), cta=E(u["cta"]),
        related=related_html(lang, arts, a["slug"]))
    crumbs = [(BRAND, "/%s/" % lang)]
    if not art["is_page"]:
        crumbs.append((H[lang]["nav"]["guides"], "/%s/%s/" % (lang, GUIDES_SLUG[lang])))
    crumbs.append((a["title"], path))
    ld = [{
        "@context": "https://schema.org", "@type": "WebPage" if art["is_page"] else "MedicalWebPage", "name": a["title"], "headline": a["title"],
        "description": a["description"], "inLanguage": lang, "url": SITE + path,
        **({"lastReviewed": art["updated"]} if show_reviewed else {}), "dateModified": art["updated"],
        "author": {"@type": "Organization", "name": BRAND},
        "publisher": {"@type": "MedicalClinic", "name": BRAND,
                      "address": {"@type": "PostalAddress", "addressLocality": "Istanbul", "addressCountry": "TR"}},
    }, breadcrumb_ld(lang, crumbs)]
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
    pages = load_articles("pages")
    for pg in pages:
        PAGE_SLUGS[pg["id"]] = {c: v["slug"] for c, v in pg["langs"].items()}
    urls = []  # (path, lastmod, alternates)
    newest = max([a["updated"] for a in arts + pages] or [str(date.today())])

    for lang in LANG_CODES:
        write("%s/index.html" % lang, home_page(lang, arts))
        urls.append(("/%s/" % lang, newest, {c: "/%s/" % c for c in LANG_CODES}))
    for lang in LANG_CODES:
        write("%s/%s/index.html" % (lang, GUIDES_SLUG[lang]), guides_index(lang, arts))
        urls.append(("/%s/%s/" % (lang, GUIDES_SLUG[lang]), newest, {c: "/%s/%s/" % (c, GUIDES_SLUG[c]) for c in LANG_CODES}))
    for art in pages + arts:
        alts = {c: "/%s/%s/" % (c, art["langs"][c]["slug"]) for c in art["langs"]}
        for lang in art["langs"]:
            slug = art["langs"][lang]["slug"]
            write("%s/%s/index.html" % (lang, slug), article_page(lang, art, arts))
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
             "Every treatment plan is confirmed individually. Prices are fixed and given in writing after our team reviews the patient's photos.", ""]
    for lang in LANG_CODES:
        lines.append("## %s" % LANG_BY[lang]["name"])
        lines.append("- [%s](%s/%s/)" % (BRAND, SITE, lang))
        for pg in pages:
            if lang in pg["langs"]:
                p_ = pg["langs"][lang]
                lines.append("- [%s](%s/%s/%s/): %s" % (p_["title"], SITE, lang, p_["slug"], p_["description"]))
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
