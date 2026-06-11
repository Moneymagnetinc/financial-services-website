# CLAUDE.md — Finaxis Financial Services Website

## What this project is
B2B marketing site for Finaxis Financial Services (finaxis.nl). Single-page bilingual (NL/EN) site. NL is the primary language and default; EN is secondary at `/en/`.

**Owner:** Alexander Gevorgyan — alex.g@live.nl — +31625009505
**Live URL:** https://finaxis.nl/
**VPS:** root@204.168.203.253 (Hetzner, Ubuntu, nginx + PHP 8.1-FPM)
**Webroot:** /var/www/finaxis/

---

## Stack

| Layer | Detail |
|---|---|
| Template | `src/index.html` — single HTML file, all CSS + JS inline |
| Build | `scripts/build-i18n.py` — Python 3, stdlib only |
| Output | `dist/index.html` (NL) and `dist/en/index.html` (EN) |
| Server | nginx + Let's Encrypt on Hetzner VPS |
| Email | PHP `contact.php` → Postfix → Hostnet SMTP relay → info@finaxis.nl + alex.g@live.nl |
| Runtime | `python3` (no Node, no npm, no framework) |

---

## File map

```
src/index.html          ← SOURCE OF TRUTH — edit this, never edit dist/
scripts/build-i18n.py   ← SSR build script
dist/                   ← generated, gitignored, deployed to VPS
  index.html            ← NL page (lang="nl")
  en/index.html         ← EN page (lang="en")
  sitemap.xml           ← auto-stamped with today's date on each build
  4cf68e...bda0.txt     ← IndexNow key verification file
assets/
  og/
    finaxis-share-nl.png  ← 1200×630 NL social share image
    finaxis-share-en.png  ← 1200×630 EN social share image
  icon-192.png          ← PWA icon (generated from logo-icon.png)
  icon-512.png          ← PWA icon (generated from logo-icon.png)
logo-icon.png           ← Shield icon — navbar hero badge, favicon
logo-nav.png            ← Full wordmark — navbar
logo-footer.png         ← Full wordmark — footer (white-filtered)
logo-full.png           ← About section photo
site.webmanifest        ← PWA manifest (theme_color: #0A2456)
robots.txt              ← Allow all, points to sitemap
4cf68e...bda0.txt       ← IndexNow key (committed, not secret)
```

---

## i18n system

`src/index.html` contains an inline `<script>` with:

```javascript
var translations = {
  en: { nav_about: 'About', ... },   // ~85 keys
  nl: { nav_about: 'Over ons', ... } // ~85 keys
};
var currentLang = 'nl';

function setLang(lang) { /* applies translations to DOM */ }
function buildFaq(lang) { /* renders FAQ accordion from faqsEN/faqsNL arrays */ }

setLang('nl'); // default on page load
```

**HTML attributes used:**
- `data-i18n="KEY"` — sets textContent
- `data-i18n-html="KEY"` — sets innerHTML (used for hero_h1 which has `<br>`/`<em>`)
- `data-i18n-ph="KEY"` — sets placeholder attribute on inputs
- `data-i18n-select="KEY"` — regenerates `<option>` list from array value

**Runtime toggle** (`btnNL` / `btnEN` buttons) still works for users after SSR — the build pre-renders the correct language, then JS rebinds on load.

---

## Build workflow

```bash
# After any edit to src/index.html OR src/pages/*:
python3 scripts/build-i18n.py    # homepage NL/EN (does NOT write sitemap)
python3 scripts/build-pages.py   # subpages + sitemap.xml (run this AFTER build-i18n)

# IndexNow ping (run from VPS — macOS Python fails SSL): see Deploy section
```

> **Sitemap ownership:** `build-pages.py` is the single source of `dist/sitemap.xml`
> (it knows every page). `build-i18n.py` deliberately no longer writes the sitemap —
> doing so overwrote the full sitemap with a 2-URL one. Always run `build-pages.py` last.

What the build script does:
1. Extracts `translations.en` and `translations.nl` blocks using brace counting
2. Extracts `faqsEN` and `faqsNL` arrays from `buildFaq()`
3. Strips the old `<head>` from the template, prepends per-language `<head>`
4. Resolves all `data-i18n*` attributes to static text
5. Renders FAQ accordion as static HTML into `#faq-list`
6. Replaces JSON-LD with 5-entity `@graph` (Organization, ProfessionalService, Person, WebSite, FAQPage)
7. For EN page: changes `setLang('nl')` → `setLang('en')`
8. Writes `dist/sitemap.xml` with today's UTC date
9. With `--ping`: POSTs to api.indexnow.org (run from VPS if macOS SSL blocks it)

---

## Deploy

```bash
# From repo root — deploy all dist/ output + assets + root files:
rsync -av dist/index.html dist/sitemap.xml dist/4cf68e079095338dd77720450132bda0.txt \
  site.webmanifest robots.txt root@204.168.203.253:/var/www/finaxis/

rsync -av dist/en/index.html root@204.168.203.253:/var/www/finaxis/en/
rsync -av assets/ root@204.168.203.253:/var/www/finaxis/assets/

# IndexNow ping (run from VPS if macOS SSL fails):
ssh root@204.168.203.253 'curl -s -X POST https://api.indexnow.org/indexnow \
  -H "Content-Type: application/json" \
  -d "{\"host\":\"finaxis.nl\",\"key\":\"4cf68e079095338dd77720450132bda0\",\
\"keyLocation\":\"https://finaxis.nl/4cf68e079095338dd77720450132bda0.txt\",\
\"urlList\":[\"https://finaxis.nl/\",\"https://finaxis.nl/en/\"]}"'
```

---

## nginx config (on VPS)

File: `/etc/nginx/sites-available/finaxis.nl`

Key routes:
- `/` → `dist/index.html` (NL)
- `/en/` → `dist/en/index.html` (EN)
- `/en` → 301 redirect to `/en/`
- `*.png|ico|woff2` → `expires 1y; Cache-Control: public, immutable`
- `index.html` files → `expires 5m; Cache-Control: no-cache`

After nginx changes: `nginx -t && systemctl reload nginx`

---

## Email (contact form)

- `contact.php` on VPS sends via Postfix → Hostnet SMTP relay
- Delivered to: info@finaxis.nl AND alex.g@live.nl
- Postfix config: `smtputf8_enable = no` (required for Hostnet compatibility)
- Sender rewriting: `/etc/postfix/generic` forces `From: info@finaxis.nl`

---

## SEO state (as of 2026-05-22)

| Signal | Status |
|---|---|
| `lang="nl"` on NL, `lang="en"` on EN | ✅ |
| hreflang nl / en / x-default | ✅ both pages |
| og:image 1200×630 per language | ✅ |
| twitter:card summary_large_image | ✅ |
| og:locale nl_NL / en_GB | ✅ |
| JSON-LD @graph — 5 entities | ✅ zero errors |
| FAQPage rich result eligible | ✅ 6 Q&A per language |
| Sitemap — 2 URLs + hreflang alternates | ✅ |
| IndexNow key live | ✅ 4cf68e...bda0 |
| Bing/Yahoo/DDG pinged | ✅ HTTP 202 |

---

## Design tokens

```css
--navy:      #0A2456   /* primary dark blue */
--blue:      #1B4FD8   /* accent blue */
--sky:       #3B82F6   /* light blue */
--white:     #FFFFFF
--off-white: #F8FAFC
--muted-text:#64748B
--border:    #E2E8F0
```

Fonts: Inter (body), DM Sans (headings) — loaded via Google Fonts with `media="print"` async trick.

---

## Do not

- Edit `dist/` files directly — they are overwritten by every build
- Add a framework (Next, Vite, Astro) — keep it vanilla HTML + build script
- Remove the inline `setLang()` toggle — it's the in-page language switch for users
- Duplicate translation strings — `src/index.html` is the single source of truth
- Change logo files without updating all references (4 logos serve different contexts)
