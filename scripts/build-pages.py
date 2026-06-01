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


def render_page(fragment_path: Path, out_path: Path,
                service_name: str = '', service_type: str = '',
                service_desc: str = '') -> None:
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

    def url_block(path, priority):
        return f'''  <url>
    <loc>https://finaxis.nl{path}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{priority}</priority>
    <xhtml:link rel="alternate" hreflang="nl" href="https://finaxis.nl{path}"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://finaxis.nl/"/>
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

PILLAR_PAGES = [
    {
        'src':          'acceptatie.html',
        'out':          'acceptatie/index.html',
        'service_name': 'Acceptatie uitbesteden',
        'service_type': 'Underwriting outsourcing',
        'service_desc': 'Volledige acceptatieverwerking — kredietanalyse, risicobeoor­deling en portfoliobeheer — binnen 5 werkdagen operationeel vanuit Nederland.',
    },
    {
        'src':          'debiteurenbeheer.html',
        'out':          'debiteurenbeheer/index.html',
        'service_name': 'Debiteurenbeheer uitbesteden',
        'service_type': 'Accounts receivable management',
        'service_desc': 'End-to-end debiteurenadministratie — van facturering tot incasso. Bewezen DSO-verlaging van 30–40% binnen 90 dagen bij financiële instellingen in Nederland.',
    },
    {
        'src':          'cdd-kyc.html',
        'out':          'cdd-kyc/index.html',
        'service_name': 'CDD / KYC Compliance uitbesteden',
        'service_type': 'CDD/KYC compliance outsourcing',
        'service_desc': 'WWFT-conforme CDD en KYC — van KYC-onboarding tot EDD en PEP-screening. Auditgereed klantonderzoek conform DNB- en EU-AML-vereisten.',
    },
    {
        'src':          'freelance.html',
        'out':          'freelance/index.html',
        'service_name': 'Freelance acceptant & KYC specialist',
        'service_type': 'Freelance financial operations specialist',
        'service_desc': 'Freelance acceptant, KYC specialist of AR-professional inhuren. Ervaren ZZP-specialisten met institutionele achtergrond, binnen 5 werkdagen inzetbaar.',
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
