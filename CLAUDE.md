# Clinic Sline: website and weekly article workflow

Static, multilingual hair transplant site (Istanbul). Languages: en, tr, de, fr, ar, ru.
Goal: patients find the clinic through organic search, AI assistants and cited sources.
No database, no server. `python3 build.py` turns `content/` and `site.json` into `public/`.
`public/` is committed and deployed as-is (Cloudflare Pages, output directory `public`, no build command).

## Layout

- `site.json`: brand, site URL, WhatsApp number, language list, all UI texts per language
- `content/articles/<id>.md`: one file per article, all six languages in one file
- `content/pages/<id>.md`: fixed pages (treatments, process), same format as articles
- `content/home.json`: home page, menu and chart texts per language (no invented numbers)
- `assets/site.js`: reveal animation, Norwood selector (builds the WhatsApp message), results lightbox
- `assets/results/`: patient before/after photos supplied by the clinic (patients consented). The weekly task never adds or changes photos
- `content/keywords.csv`: keyword plan and status (the source of truth for what to write next)
- `assets/style.css`: the only stylesheet
- `build.py`: generator. Never edit `public/` by hand.

## Article file format

```
updated: YYYY-MM-DD
reviewed: true         (add this line ONLY after the doctor has really read the article; never add it yourself)
draft: true            (optional: hides the article from the public build)

=== en
slug: url-slug-in-ascii
title: ...
description: one or two sentences, under 160 characters
keyword: main search phrase in that language

## Key takeaways
...
## Sources
- [Real source title](https://real-url)

::: faq
Q: question
A: answer
```

Repeat the `=== xx` block for tr, de, fr, ar, ru. Slugs differ per language (ASCII only).
Every language block needs slug, title and description. Body supports `##`, `###`, `- ` lists, **bold**, [links](https://...).

## Weekly workflow (run by the scheduled task)

1. Open `content/keywords.csv`. Take the first row with status `planned`. If none is left, research and add 5 new rows.
2. Research with web search in each of the six languages: what the first results cover, which questions patients ask, what competitors miss. Search volume is not available, so say "unverified" in notes.
3. Write one new article in all six languages. Write each language natively, not as a literal translation. Match the search intent of that language.
4. Do NOT set `reviewed: true` and do not set `draft: true`: the article goes live automatically, showing only "Updated <date>" and no medical-review claim. Run `python3 build.py` and check it builds.
5. Update the row in `content/keywords.csv` to `published` with the date.
6. Commit with a clear message and push to `main`.

## Editorial rules (medical content, high stakes)

- Never invent facts, prices, statistics, studies or quotes. If a number is not from a source you can link, leave it out.
- No promises of results, no "best", "guaranteed", "painless", "no risk". Say results vary.
- Do not use doctor wording on the site (the owner decided: no "doctor-approved", "licensed doctor" or doctor mentions). Say "our team" or "specialist". Only for medication safety, point to "whoever prescribed it" and the clinic. Do not name the doctor. The "medically reviewed by a licensed physician" line appears only when the file has `reviewed: true`, which a human adds after the doctor really read it. Never add it, never claim review anywhere else.
- Do not name or criticise competitor clinics.
- Cite real, linkable sources in a Sources section (medical societies, health authorities, peer-reviewed work). Check that each link exists.
- Each article: short key takeaways first, clear headings, a three-question FAQ, one honest "what to ask a clinic" or "warning signs" section.
- Turkish regulations restrict health advertising. The clinic decided to show consented before/after photos on the home page. Do not add testimonials, discount offers or prices, and do not add or change photos in the weekly task.
- Arabic and Russian texts must be natural. Mark anything uncertain in the commit message for human review.

## Placeholders to replace before launch

- `site_url` in `site.json` (currently `https://clinicsline.example`)
- `whatsapp` in `site.json` (currently a dummy number)
- `address` in `site.json` (optional, shown in the footer when filled)
