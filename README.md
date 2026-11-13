# Clinic Sline

Multilingual hair transplant website (Istanbul). Static site, no database.

```
python3 build.py            # builds public/ (skips drafts)
python3 build.py --drafts   # includes draft articles for preview
```

## Deploy (Cloudflare Pages)

1. Cloudflare Pages: create a project from this GitHub repository.
2. Build command: empty. Build output directory: `public`.
3. Add your custom domain, then set `site_url` in `site.json` to that domain and run `python3 build.py`.
4. Submit `https://YOUR-DOMAIN/sitemap.xml` in Google Search Console and Bing Webmaster Tools.

Pages: home, treatments, process, guides index and articles in six languages. Home texts live in `content/home.json`, fixed pages in `content/pages/`.

Editorial and workflow rules are in `CLAUDE.md`.
