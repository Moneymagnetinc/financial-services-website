#!/usr/bin/env python3
"""
build-pages.py — Generates all new Finaxis content pages into dist/.

Pages rendered:
  dist/acceptatie/index.html
  dist/debiteurenbeheer/index.html
  dist/cdd-kyc/index.html
  dist/freelance/index.html
  dist/over-ons/index.html
  dist/kennisbank/index.html
  dist/kennisbank/<slug>/index.html  (one per article in articles.json)
  dist/gids/wwft-checklist/index.html
  dist/contact/index.html
  dist/bedankt/index.html
  dist/sitemap.xml (updated with all new URLs)

Usage:
  python3 scripts/build-pages.py [--ping]
"""

import os, re, sys, json, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT    = Path(__file__).resolve().parent.parent
SRC     = ROOT / 'src'
DIST    = ROOT / 'dist'
TODAY   = datetime.now(timezone.utc).strftime('%Y-%m-%d')
INDEXNOW_KEY = '4cf68e079095338dd77720450132bda0'

PAGE_TPL    = (SRC / 'templates' / 'page.html').read_text(encoding='utf-8')
ARTICLE_TPL = (SRC / 'templates' / 'article.html').read_text(encoding='utf-8')

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_meta_comment(fragment: str) -> dict:
    """Extract <!-- META: key=value | key=value --> from first line.
    Splits only on | followed by a known key name, so titles/descs
    that contain | are preserved intact."""
    m = re.match(r'<!--\s*META:\s*(.*?)\s*-->', fragment.strip(), re.DOTALL)
    if not m:
        return {}
    meta = {}
    # Split on pipe only when immediately followed by a word + '='
    parts = re.split(r'\s*\|\s*(?=\w+=)', m.group(1))
    for part in parts:
        part = part.strip()
        if '=' in part:
            k, _, v = part.partition('=')
            meta[k.strip()] = v.strip()
    return meta


def build_head(meta: dict, is_article: bool = False) -> str:
    title    = meta.get('title', 'Finaxis | Specialist in financiële operaties')
    desc     = meta.get('desc', '')[:160]   # Google truncates at 160
    canonical = meta.get('canonical', 'https://finaxis.nl/')
    og_title = meta.get('og_title', title)
    og_desc  = meta.get('og_desc', desc)
    return f'''<title>{title}</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:url"         content="{canonical}" />
  <meta property="og:title"       content="{og_title}" />
  <meta property="og:description" content="{og_desc}" />
  <meta name="twitter:title"       content="{og_title}" />
  <meta name="twitter:description" content="{og_desc}" />'''


def build_service_jsonld(meta: dict, service_name: str, service_type: str,
                          service_desc: str, page_url: str) -> str:
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Service",
                "@id": page_url + "#service",
                "name": service_name,
                "provider": {"@id": "https://finaxis.nl/#org"},
                "areaServed": {"@type": "Country", "name": "Netherlands"},
                "serviceType": service_type,
                "description": service_desc,
                "url": page_url
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://finaxis.nl/"},
                    {"@type": "ListItem", "position": 2, "name": service_name, "item": page_url}
                ]
            }
        ]
    }
    return f'<script type="application/ld+json">\n{json.dumps(graph, ensure_ascii=False, indent=2)}\n</script>'


def build_faq_jsonld(faqs: list, page_url: str) -> str:
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "@id": page_url + "#faq",
        "mainEntity": [
            {"@type": "Question", "name": faq["q"],
             "acceptedAnswer": {"@type": "Answer", "text": faq["a"]}}
            for faq in faqs
        ]
    }
    return f'<script type="application/ld+json">\n{json.dumps(faq_schema, ensure_ascii=False, indent=2)}\n</script>'


def build_article_jsonld(article: dict) -> str:
    graph = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": article["title"],
        "author": {
            "@type": "Person",
            "name": "Alexander Gevorgyan",
            "@id": "https://finaxis.nl/#alexander"
        },
        "publisher": {"@id": "https://finaxis.nl/#org"},
        "datePublished": article["published"],
        "dateModified": TODAY,
        "mainEntityOfPage": {"@type": "WebPage", "@id": "https://finaxis.nl" + article["url"]},
        "keywords": article.get("keywords", []),
        "description": article.get("meta_description", ""),
        "inLanguage": "nl-NL"
    }
    return f'<script type="application/ld+json">\n{json.dumps(graph, ensure_ascii=False, indent=2)}\n</script>'


def extract_faqs_from_fragment(html: str) -> list:
    """Parse FAQ Q&A pairs from page fragment for JSON-LD."""
    faqs = []
    # Pattern 1: <div class="faq-item" data-faq-item="N"><h3>Q</h3><p>A</p></div>
    for m in re.finditer(
        r'<div[^>]*class="faq-item"[^>]*>[\s\S]*?<h3[^>]*>([\s\S]*?)</h3>[\s\S]*?<p[^>]*>([\s\S]*?)</p>[\s\S]*?</div>',
        html, re.DOTALL
    ):
        q = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        a = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if q and a:
            faqs.append({"q": q, "a": a})
    # Pattern 2: .faq-btn > span + .faq-answer > p (interactive accordion)
    if not faqs:
        qs = re.findall(r'class="faq-btn"[^>]*>[\s\S]*?<span>([\s\S]*?)</span>', html)
        as_ = re.findall(r'class="faq-answer"[^>]*>[\s\S]*?<p[^>]*>([\s\S]*?)</p>', html)
        for q, a in zip(qs, as_):
            faqs.append({
                "q": re.sub(r'<[^>]+>', '', q).strip(),
                "a": re.sub(r'<[^>]+>', '', a).strip()
            })
    return faqs


# ── i18n chrome (for the few English subpages) ─────────────────────────────────

# Dutch → English replacements for the shared nav/footer/popup chrome in page.html.
# Order matters; all strings are exact matches present in the rendered page.
CHROME_EN = [
    ('<html lang="nl">', '<html lang="en">'),
    ('content="nl_NL"', 'content="en_GB"'),
    ('finaxis-share-nl.png', 'finaxis-share-en.png'),
    # top nav + footer service labels
    ('>Acceptatie</a>', '>Underwriting</a>'),
    ('>Debiteurenbeheer</a>', '>Accounts Receivable</a>'),
    ('>AI-automatisering</a>', '>AI Automation</a>'),
    ('>Kennisbank</a>', '>Knowledge Base</a>'),
    ('>Gesprek aanvragen</a>', '>Request a call</a>'),
    ('>CDD / KYC Compliance</a>', '>CDD / KYC Compliance</a>'),
    ('>Freelance / ZZP inhuren</a>', '>Freelance / Contract hire</a>'),
    ('>Over ons</a>', '>About us</a>'),
    ('>Uitbesteden vs. In-house</a>', '>Outsourcing vs. In-house</a>'),
    ('>WWFT Checklist (gratis)</a>', '>WWFT Checklist (free)</a>'),
    # footer headings + taglines
    ('>Diensten<', '>Services<'),
    ('>Navigatie<', '>Navigation<'),
    ('Specialist in acceptatie, debiteurenbeheer en CDD/KYC-compliance. Gevestigd in Nederland.',
     'Specialist in underwriting, accounts receivable and CDD/KYC compliance. Based in Amsterdam, the Netherlands.'),
    ('>Nederland &middot; Wereldwijd<', '>Netherlands &middot; Worldwide<'),
    ('Nederland &middot; Alle rechten voorbehouden.', 'Netherlands &middot; All rights reserved.'),
    ('>Acceptatie &middot; Debiteurenbeheer &middot; CDD/KYC<',
     '>Underwriting &middot; Accounts Receivable &middot; CDD/KYC<'),
    # exit popup + whatsapp
    ('Voordat je gaat — download de gratis WWFT Checklist 2026',
     'Before you go — download the free WWFT Checklist 2026'),
    ('17 controlepunten voor KYC, AML en CDD — direct te gebruiken in jouw organisatie.',
     '17 checkpoints for KYC, AML and CDD — ready to use in your organisation.'),
    ('Direct downloaden &rarr;', 'Download now &rarr;'),
    ('aria-label="Download gratis checklist"', 'aria-label="Download free checklist"'),
    ('<span>Direct chatten</span>', '<span>Chat now</span>'),
    # sticky CTA bar + misc labels
    ('Specialist nodig? Binnen 5 werkdagen inzetbaar —', 'Need a specialist? Operational within 5 business days —'),
    ('Plan een kennismaking &rarr;', 'Schedule an intro &rarr;'),
    ('aria-label="Sluiten"', 'aria-label="Close"'),
    # service links should point to their English equivalents (nav, footer + body)
    ('href="/ai-automatisering/"', 'href="/en/ai-automation/"'),
    ('href="/acceptatie/"', 'href="/en/underwriting/"'),
    ('href="/debiteurenbeheer/"', 'href="/en/accounts-receivable/"'),
    ('href="/cdd-kyc/"', 'href="/en/cdd-kyc/"'),
]


def to_english_chrome(html: str) -> str:
    for nl, en in CHROME_EN:
        html = html.replace(nl, en)
    return html


def inject_hreflang(html: str, alternates: dict) -> str:
    """Replace the template's static homepage hreflang links with a page-specific set."""
    html = re.sub(r'[ \t]*<link rel="alternate"[^>]*>\n', '', html)
    links = '\n'.join(
        f'  <link rel="alternate" hreflang="{lang}" href="{url}" />'
        for lang, url in alternates.items()
    )
    return html.replace(
        '<meta name="theme-color" content="#0A2456" />',
        '<meta name="theme-color" content="#0A2456" />\n' + links, 1)


def render_page(fragment_path: Path, out_path: Path,
                service_name: str = '', service_type: str = '',
                service_desc: str = '',
                lang: str = 'nl', alternates: dict = None) -> None:
    fragment = fragment_path.read_text(encoding='utf-8')
    meta     = parse_meta_comment(fragment)
    canonical = meta.get('canonical', 'https://finaxis.nl/')
    head     = build_head(meta)

    # strip the META comment
    content  = re.sub(r'<!--\s*META:.*?-->\s*', '', fragment, count=1, flags=re.DOTALL)

    # build JSON-LD — one @graph per page
    faqs = extract_faqs_from_fragment(content)
    graph_nodes = []
    if service_name:
        graph_nodes.append({
            "@type": "Service",
            "@id": canonical + "#service",
            "name": service_name,
            "provider": {"@id": "https://finaxis.nl/#org"},
            "areaServed": {"@type": "Country", "name": "Netherlands"},
            "serviceType": service_type,
            "description": service_desc,
            "url": canonical
        })
    graph_nodes.append({
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://finaxis.nl/"},
            {"@type": "ListItem", "position": 2, "name": service_name or meta.get('title',''), "item": canonical}
        ]
    })
    if faqs:
        graph_nodes.append({
            "@type": "FAQPage",
            "@id": canonical + "#faq",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in faqs
            ]
        })
    combined = {"@context": "https://schema.org", "@graph": graph_nodes}
    jsonld_block = f'<script type="application/ld+json">\n{json.dumps(combined, ensure_ascii=False, indent=2)}\n</script>'

    page = PAGE_TPL.replace('{{HEAD}}', head) \
                   .replace('{{CONTENT}}', content) \
                   .replace('{{JSONLD}}', jsonld_block)

    if alternates:
        page = inject_hreflang(page, alternates)
    if lang == 'en':
        page = to_english_chrome(page)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding='utf-8')
    print(f'  {out_path.relative_to(ROOT)}  ({len(page):,} chars)')


def render_article(article: dict, all_articles: list, out_path: Path) -> None:
    url     = 'https://finaxis.nl' + article['url']
    url_enc = urllib.parse.quote(url, safe='')
    date_obj = datetime.strptime(article['published'], '%Y-%m-%d')
    date_nl  = date_obj.strftime('%-d %B %Y').replace(
        'January','januari').replace('February','februari').replace(
        'March','maart').replace('April','april').replace(
        'May','mei').replace('June','juni').replace(
        'July','juli').replace('August','augustus').replace(
        'September','september').replace('October','oktober').replace(
        'November','november').replace('December','december')

    art_desc = article.get('meta_description', '')[:160]
    head = f'''<title>{article["title"]} | Finaxis Kennisbank</title>
  <meta name="description" content="{art_desc}" />
  <link rel="canonical" href="{url}" />
  <meta property="og:url"         content="{url}" />
  <meta property="og:title"       content="{article['title']}" />
  <meta property="og:description" content="{article.get('meta_description','')}" />
  <meta name="twitter:title"       content="{article['title']}" />
  <meta name="twitter:description" content="{article.get('meta_description','')}" />'''

    # Build related cards
    related_slugs = article.get('related', [])
    related_map   = {a['slug']: a for a in all_articles}
    related_html  = ''
    for slug in related_slugs[:2]:
        rel = related_map.get(slug)
        if rel:
            cat = rel.get('keywords', ['Kennisbank'])[0]
            related_html += f'''
      <a href="{rel['url']}" class="related-card">
        <div class="related-card-cat">{cat}</div>
        <h4>{rel['title']}</h4>
        <span class="related-card-link">Lees artikel &rarr;</span>
      </a>'''

    title_short = article['title'][:55] + ('…' if len(article['title']) > 55 else '')
    pillar_link  = article.get('pillar_link', '/cdd-kyc/')
    pillar_label = article.get('pillar_label', 'Meer over CDD / KYC')
    cat_label    = (article.get('keywords', ['Kennisbank'])[0]).upper()

    jsonld = build_article_jsonld(article)

    page = ARTICLE_TPL \
        .replace('{{HEAD}}', head) \
        .replace('{{ARTICLE_TITLE}}', article['title']) \
        .replace('{{ARTICLE_TITLE_SHORT}}', title_short) \
        .replace('{{ARTICLE_CATEGORY}}', cat_label) \
        .replace('{{ARTICLE_DATE}}', date_nl) \
        .replace('{{ARTICLE_READTIME}}', str(article.get('read_time', '5'))) \
        .replace('{{ARTICLE_BODY}}', article.get('body_html', '')) \
        .replace('{{ARTICLE_URL_ENCODED}}', url_enc) \
        .replace('{{RELATED_CARDS}}', related_html) \
        .replace('{{PILLAR_LINK}}', pillar_link) \
        .replace('{{PILLAR_LABEL}}', pillar_label) \
        .replace('{{JSONLD}}', jsonld)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding='utf-8')
    print(f'  {out_path.relative_to(ROOT)}  ({len(page):,} chars)')


def build_sitemap(article_slugs: list) -> str:
    pillar_pages = [
        ('/acceptatie/',       '0.9'),
        ('/debiteurenbeheer/', '0.9'),
        ('/cdd-kyc/',          '0.9'),
        ('/ai-automatisering/', '0.9'),
        ('/en/underwriting/',  '0.8'),
        ('/en/accounts-receivable/', '0.8'),
        ('/en/cdd-kyc/',       '0.8'),
        ('/en/ai-automation/', '0.8'),
        ('/us/cdd-kyc/',       '0.8'),
        ('/ae/cdd-kyc/',       '0.8'),
        ('/freelance/',        '0.8'),
        ('/over-ons/',         '0.6'),
        ('/kennisbank/',       '0.7'),
        ('/gids/wwft-checklist/', '0.8'),
        ('/contact/',          '0.7'),
        ('/privacy/',          '0.3'),
        ('/vergelijken/',       '0.8'),
        ('/kennisbank/kredietacceptatie-uitbesteden/', '0.7'),
        ('/kennisbank/cdd-uitbesteden/', '0.7'),
    ]
    article_urls = [(f'/kennisbank/{s}/', '0.7') for s in article_slugs]
    homepage_urls = [
        ('/', '1.0'),
        ('/en/', '0.9'),
    ]

    # Per-path hreflang, sourced from the page definitions so the sitemap and the
    # pages never disagree.
    alt_by_path = {}
    for p in PILLAR_PAGES + EN_PAGES + REGIONAL_PAGES:
        if p.get('alternates'):
            alt_by_path['/' + p['out'].replace('index.html', '')] = p['alternates']

    def url_block(path, priority):
        # The homepage NL/EN pair carries the full regional hreflang set so search
        # engines serve the English page to US/UAE visitors. NL subpages are nl-only.
        if path in ('/', '/en/'):
            alts = '''
    <xhtml:link rel="alternate" hreflang="nl"        href="https://finaxis.nl/"/>
    <xhtml:link rel="alternate" hreflang="nl-NL"     href="https://finaxis.nl/"/>
    <xhtml:link rel="alternate" hreflang="en"        href="https://finaxis.nl/en/"/>
    <xhtml:link rel="alternate" hreflang="en-US"     href="https://finaxis.nl/en/"/>
    <xhtml:link rel="alternate" hreflang="en-AE"     href="https://finaxis.nl/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://finaxis.nl/"/>'''
        elif path in alt_by_path:
            alts = ''.join(
                f'\n    <xhtml:link rel="alternate" hreflang="{lang}" href="{url}"/>'
                for lang, url in alt_by_path[path].items()
            )
        else:
            alts = f'''
    <xhtml:link rel="alternate" hreflang="nl" href="https://finaxis.nl{path}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://finaxis.nl/"/>'''
        return f'''  <url>
    <loc>https://finaxis.nl{path}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{priority}</priority>{alts}
  </url>'''

    blocks = []
    for p, pri in homepage_urls + pillar_pages + article_urls:
        blocks.append(url_block(p, pri))

    return '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
''' + '\n'.join(blocks) + '\n</urlset>'


def ping_indexnow(urls: list) -> None:
    payload = json.dumps({
        'host': 'finaxis.nl',
        'key': INDEXNOW_KEY,
        'keyLocation': f'https://finaxis.nl/{INDEXNOW_KEY}.txt',
        'urlList': urls
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.indexnow.org/indexnow',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f'  IndexNow: HTTP {resp.status} ({len(urls)} URLs)')
    except Exception as e:
        print(f'  IndexNow error: {e}')


# ── Page definitions ──────────────────────────────────────────────────────────

# CDD/KYC cluster: NL + generic EN + US-targeted EN. Shared so all three pages
# (and the sitemap) advertise the same reciprocal hreflang set.
CDD_ALTS = {
    'nl':        'https://finaxis.nl/cdd-kyc/',
    'en':        'https://finaxis.nl/en/cdd-kyc/',
    'en-US':     'https://finaxis.nl/us/cdd-kyc/',
    'en-AE':     'https://finaxis.nl/ae/cdd-kyc/',
    'x-default': 'https://finaxis.nl/cdd-kyc/',
}

PILLAR_PAGES = [
    {
        'src':          'acceptatie.html',
        'out':          'acceptatie/index.html',
        'service_name': 'Acceptatie uitbesteden',
        'service_type': 'Underwriting outsourcing',
        'service_desc': 'Volledige acceptatieverwerking — kredietanalyse, risicobeoor­deling en portfoliobeheer — binnen 5 werkdagen operationeel vanuit Nederland.',
        'alternates':   {'nl': 'https://finaxis.nl/acceptatie/', 'en': 'https://finaxis.nl/en/underwriting/', 'x-default': 'https://finaxis.nl/acceptatie/'},
    },
    {
        'src':          'debiteurenbeheer.html',
        'out':          'debiteurenbeheer/index.html',
        'service_name': 'Debiteurenbeheer uitbesteden',
        'service_type': 'Accounts receivable management',
        'service_desc': 'End-to-end debiteurenadministratie — van facturering tot incasso. Bewezen DSO-verlaging van 30–40% binnen 90 dagen bij financiële instellingen in Nederland.',
        'alternates':   {'nl': 'https://finaxis.nl/debiteurenbeheer/', 'en': 'https://finaxis.nl/en/accounts-receivable/', 'x-default': 'https://finaxis.nl/debiteurenbeheer/'},
    },
    {
        'src':          'cdd-kyc.html',
        'out':          'cdd-kyc/index.html',
        'service_name': 'CDD / KYC Compliance uitbesteden',
        'service_type': 'CDD/KYC compliance outsourcing',
        'service_desc': 'WWFT-conforme CDD en KYC — van KYC-onboarding tot EDD en PEP-screening. Auditgereed klantonderzoek conform DNB- en EU-AML-vereisten.',
        'alternates':   CDD_ALTS,
    },
    {
        'src':          'freelance.html',
        'out':          'freelance/index.html',
        'service_name': 'Freelance acceptant & KYC specialist',
        'service_type': 'Freelance financial operations specialist',
        'service_desc': 'Freelance acceptant, KYC specialist of AR-professional inhuren. Ervaren ZZP-specialisten met institutionele achtergrond, binnen 5 werkdagen inzetbaar.',
    },
    {
        'src':          'ai-automatisering.html',
        'out':          'ai-automatisering/index.html',
        'service_name': 'AI-automatisering voor financiële operaties',
        'service_type': 'AI process automation',
        'service_desc': 'AI-automatisering van acceptatie-, CDD/KYC- en debiteurenworkflows — documentextractie, screening en reconciliatie met menselijke controle en een volledig audittrail.',
        'alternates':   {
            'nl':        'https://finaxis.nl/ai-automatisering/',
            'en':        'https://finaxis.nl/en/ai-automation/',
            'x-default': 'https://finaxis.nl/ai-automatisering/',
        },
    },
]

# English subpages (English chrome + body). Each carries reciprocal hreflang.
EN_PAGES = [
    {
        'src':          'en/ai-automation.html',
        'out':          'en/ai-automation/index.html',
        'service_name': 'AI automation for financial operations',
        'service_type': 'AI process automation',
        'service_desc': 'AI automation of underwriting, CDD/KYC and receivables workflows — document extraction, screening and reconciliation with human review and a full audit trail.',
        'alternates':   {'nl': 'https://finaxis.nl/ai-automatisering/', 'en': 'https://finaxis.nl/en/ai-automation/', 'x-default': 'https://finaxis.nl/ai-automatisering/'},
    },
    {
        'src':          'en/underwriting.html',
        'out':          'en/underwriting/index.html',
        'service_name': 'Outsource underwriting',
        'service_type': 'Underwriting outsourcing',
        'service_desc': 'Full-cycle underwriting — credit analysis, risk assessment and portfolio management — operational within 5 business days from the Netherlands.',
        'alternates':   {'nl': 'https://finaxis.nl/acceptatie/', 'en': 'https://finaxis.nl/en/underwriting/', 'x-default': 'https://finaxis.nl/acceptatie/'},
    },
    {
        'src':          'en/accounts-receivable.html',
        'out':          'en/accounts-receivable/index.html',
        'service_name': 'Outsource accounts receivable',
        'service_type': 'Accounts receivable management',
        'service_desc': 'End-to-end receivables management — from invoicing to collections. Proven DSO reduction of 30–40% within 90 days at financial institutions.',
        'alternates':   {'nl': 'https://finaxis.nl/debiteurenbeheer/', 'en': 'https://finaxis.nl/en/accounts-receivable/', 'x-default': 'https://finaxis.nl/debiteurenbeheer/'},
    },
    {
        'src':          'en/cdd-kyc.html',
        'out':          'en/cdd-kyc/index.html',
        'service_name': 'Outsource CDD / KYC compliance',
        'service_type': 'CDD/KYC compliance outsourcing',
        'service_desc': 'AML-compliant CDD and KYC — from KYC onboarding to EDD and PEP screening. Audit-ready customer due diligence to EU AML standards.',
        'alternates':   CDD_ALTS,
    },
]

# Region-targeted English pages (local AML language). English chrome.
REGIONAL_PAGES = [
    {
        'src':          'us/cdd-kyc.html',
        'out':          'us/cdd-kyc/index.html',
        'service_name': 'Outsource BSA/AML and KYC compliance',
        'service_type': 'BSA/AML and KYC compliance outsourcing',
        'service_desc': 'Audit-ready BSA/AML and KYC operations — CIP, FinCEN CDD Rule beneficial ownership, OFAC screening and EDD — built to US regulatory expectations.',
        'area':         'United States',
        'alternates':   CDD_ALTS,
    },
    {
        'src':          'ae/cdd-kyc.html',
        'out':          'ae/cdd-kyc/index.html',
        'service_name': 'Outsource AML and KYC compliance (UAE)',
        'service_type': 'AML and KYC compliance outsourcing',
        'service_desc': 'Audit-ready AML and KYC operations — CDD, UBO, sanctions screening and EDD — aligned to CBUAE, DFSA and ADGM expectations and goAML reporting.',
        'area':         'United Arab Emirates',
        'alternates':   CDD_ALTS,
    },
]

SIMPLE_PAGES = [
    ('over-ons.html',  'over-ons/index.html'),
    ('kennisbank.html', 'kennisbank/index.html'),
    ('wwft-checklist.html', 'gids/wwft-checklist/index.html'),
    ('contact.html',   'contact/index.html'),
    ('bedankt.html',   'bedankt/index.html'),
    ('privacy.html',   'privacy/index.html'),
    ('vergelijken.html', 'vergelijken/index.html'),
    ('kennisbank-kredietacceptatie.html', 'kennisbank/kredietacceptatie-uitbesteden/index.html'),
    ('kennisbank-cdd-uitbesteden.html', 'kennisbank/cdd-uitbesteden/index.html'),
]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f'Building pages → {DIST}')

    # Pillar pages
    print('\nPillar pages:')
    for p in PILLAR_PAGES:
        src_path = SRC / 'pages' / p['src']
        if not src_path.exists():
            print(f'  SKIP (missing): {src_path.name}')
            continue
        render_page(
            src_path,
            DIST / p['out'],
            p['service_name'],
            p['service_type'],
            p['service_desc'],
            alternates=p.get('alternates'),
        )

    # English pages
    print('\nEnglish pages:')
    for p in EN_PAGES:
        src_path = SRC / 'pages' / p['src']
        if not src_path.exists():
            print(f'  SKIP (missing): {p["src"]}')
            continue
        render_page(
            src_path,
            DIST / p['out'],
            p['service_name'],
            p['service_type'],
            p['service_desc'],
            lang='en',
            alternates=p.get('alternates'),
        )

    # US-targeted English pages
    print('\nUS pages:')
    for p in REGIONAL_PAGES:
        src_path = SRC / 'pages' / p['src']
        if not src_path.exists():
            print(f'  SKIP (missing): {p["src"]}')
            continue
        render_page(
            src_path,
            DIST / p['out'],
            p['service_name'],
            p['service_type'],
            p['service_desc'],
            lang='en',
            alternates=p.get('alternates'),
        )

    # Simple pages
    print('\nSupporting pages:')
    for src_name, out_name in SIMPLE_PAGES:
        src_path = SRC / 'pages' / src_name
        if not src_path.exists():
            print(f'  SKIP (missing): {src_name}')
            continue
        render_page(src_path, DIST / out_name)

    # Articles
    articles_json = SRC / 'articles.json'
    article_slugs = []
    if articles_json.exists():
        print('\nArticles:')
        articles = json.loads(articles_json.read_text(encoding='utf-8'))
        for article in articles:
            slug = article['slug']
            article_slugs.append(slug)
            out_path = DIST / 'kennisbank' / slug / 'index.html'
            render_article(article, articles, out_path)
    else:
        print('\nNo articles.json found — skipping articles')

    # Sitemap
    sitemap = build_sitemap(article_slugs)
    (DIST / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    url_count = sitemap.count('<loc>')
    print(f'\nSitemap: {url_count} URLs → dist/sitemap.xml')

    # IndexNow key file
    (DIST / f'{INDEXNOW_KEY}.txt').write_text(INDEXNOW_KEY, encoding='utf-8')

    print('\nBuild complete.')

    if '--ping' in sys.argv:
        all_urls = (
            ['https://finaxis.nl/', 'https://finaxis.nl/en/'] +
            [f'https://finaxis.nl/acceptatie/',
             'https://finaxis.nl/debiteurenbeheer/',
             'https://finaxis.nl/cdd-kyc/',
             'https://finaxis.nl/ai-automatisering/',
             'https://finaxis.nl/en/underwriting/',
             'https://finaxis.nl/en/accounts-receivable/',
             'https://finaxis.nl/en/cdd-kyc/',
             'https://finaxis.nl/en/ai-automation/',
             'https://finaxis.nl/us/cdd-kyc/',
             'https://finaxis.nl/ae/cdd-kyc/',
             'https://finaxis.nl/freelance/',
             'https://finaxis.nl/over-ons/',
             'https://finaxis.nl/kennisbank/',
             'https://finaxis.nl/gids/wwft-checklist/',
             'https://finaxis.nl/contact/', 'https://finaxis.nl/privacy/', 'https://finaxis.nl/vergelijken/', 'https://finaxis.nl/kennisbank/kredietacceptatie-uitbesteden/', 'https://finaxis.nl/kennisbank/cdd-uitbesteden/'] +
            [f'https://finaxis.nl/kennisbank/{s}/' for s in article_slugs]
        )
        print(f'\nPinging IndexNow ({len(all_urls)} URLs)...')
        ping_indexnow(all_urls)


if __name__ == '__main__':
    main()
