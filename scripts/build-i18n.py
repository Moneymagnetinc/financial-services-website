#!/usr/bin/env python3
"""
Build script: SSR-renders src/index.html into:
  dist/index.html       — Dutch (NL), served at finaxis.nl/
  dist/en/index.html    — English (EN), served at finaxis.nl/en/
  dist/sitemap.xml      — two-URL sitemap with hreflang alternates
  dist/<KEY>.txt        — IndexNow key verification file

Run:  python3 scripts/build-i18n.py [--ping]
  --ping  POST to IndexNow API after building (use after every deploy)
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
SRC           = ROOT / 'src' / 'index.html'
DIST          = ROOT / 'dist'
TODAY         = datetime.now(timezone.utc).strftime('%Y-%m-%d')
INDEXNOW_KEY  = '4cf68e079095338dd77720450132bda0'


# ── Block extraction (brace/bracket counter) ──────────────────────────────────

def extract_block(src: str, marker: str, opener: str) -> str:
    pos = src.index(marker)
    open_pos = src.index(opener, pos)
    closer = '}' if opener == '{' else ']'
    depth = 0
    i = open_pos
    in_str = False
    str_ch = ''
    escape = False
    while i < len(src):
        c = src[i]
        if escape:
            escape = False
        elif c == '\\' and in_str:
            escape = True
        elif in_str:
            if c == str_ch:
                in_str = False
        elif c in ('"', "'", '`'):
            in_str = True
            str_ch = c
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return src[open_pos:i + 1]
        i += 1
    raise ValueError(f'No closing {closer} for marker: {marker!r}')


# ── JS value extraction ───────────────────────────────────────────────────────

def extract_str_val(js_block: str, key: str) -> 'str | None':
    for q in ("'", '"'):
        esc_q = re.escape(q)
        pattern = (r'\b' + re.escape(key) + r':\s*' + esc_q +
                   r'((?:[^' + q + r'\\]|\\.)*)' + esc_q)
        m = re.search(pattern, js_block)
        if m:
            return m.group(1).replace('\\' + q, q)
    return None


def extract_array_val(js_block: str, key: str) -> 'list | None':
    m = re.search(r'\b' + re.escape(key) + r':\s*\[', js_block)
    if not m:
        return None
    arr_str = extract_block(js_block[m.start():], key + ':', '[')
    items = []
    for q in ("'", '"'):
        esc_q = re.escape(q)
        found = [
            mo.group(1).replace('\\' + q, q)
            for mo in re.finditer(esc_q + r'((?:[^' + q + r'\\]|\\.)*)'
                                  + esc_q, arr_str)
        ]
        if found:
            return found
    return items


def parse_qa_array(arr_str: str) -> list:
    qs = [m.group(1).replace("\\'", "'")
          for m in re.finditer(r"\bq:\s*'((?:[^'\\]|\\.)*)'", arr_str)]
    as_ = [m.group(1).replace("\\'", "'")
           for m in re.finditer(r"\ba:\s*'((?:[^'\\]|\\.)*)'", arr_str)]
    if not qs:
        qs = [m.group(1).replace('\\"', '"')
              for m in re.finditer(r'\bq:\s*"((?:[^"\\]|\\.)*)"', arr_str)]
        as_ = [m.group(1).replace('\\"', '"')
               for m in re.finditer(r'\ba:\s*"((?:[^"\\]|\\.)*)"', arr_str)]
    return [{'q': q, 'a': a} for q, a in zip(qs, as_)]


# ── HTML helpers ──────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def esc_attr(s: str) -> str:
    return str(s).replace('"', '&quot;')


# ── Translation application ───────────────────────────────────────────────────

def apply_translations(html: str, js_block: str) -> str:
    # data-i18n="key" → replace text content (leaf nodes, no child tags)
    keys_done: set = set()
    for m in re.finditer(r'data-i18n="([^"]+)"', html):
        key = m.group(1)
        if key in keys_done:
            continue
        keys_done.add(key)
        val = extract_str_val(js_block, key)
        if val is None:
            continue
        escaped_val = esc(val)
        html = re.sub(
            r'(data-i18n="' + re.escape(key) + r'"(?:[^>]*)>)[^<]*',
            lambda ma, ev=escaped_val: ma.group(1) + ev,
            html
        )

    # data-i18n-html="key" → replace innerHTML (may contain tags)
    for m in re.finditer(r'data-i18n-html="([^"]+)"', html):
        key = m.group(1)
        val = extract_str_val(js_block, key)
        if val is None:
            continue
        tm = re.search(r'<(\w+)[^>]*\bdata-i18n-html="' + re.escape(key) + r'"[^>]*>', html)
        if not tm:
            continue
        tag = tm.group(1)
        html = re.sub(
            r'(<' + tag + r'[^>]*\bdata-i18n-html="' + re.escape(key)
            + r'"[^>]*>)[\s\S]*?(</' + tag + r'>)',
            lambda ma, v=val: ma.group(1) + v + ma.group(2),
            html
        )

    # data-i18n-ph="key" → replace placeholder attribute value
    ph_done: set = set()
    for m in re.finditer(r'data-i18n-ph="([^"]+)"', html):
        key = m.group(1)
        if key in ph_done:
            continue
        ph_done.add(key)
        val = extract_str_val(js_block, key)
        if val is None:
            continue
        ev = esc_attr(val)
        # placeholder comes before data-i18n-ph
        html = re.sub(
            r'(\bplaceholder=")[^"]*("[^>]*\bdata-i18n-ph="' + re.escape(key) + r'")',
            lambda ma, ev=ev: ma.group(1) + ev + ma.group(2),
            html
        )
        # data-i18n-ph comes before placeholder
        html = re.sub(
            r'(\bdata-i18n-ph="' + re.escape(key) + r'"[^>]*\bplaceholder=")[^"]*(")',
            lambda ma, ev=ev: ma.group(1) + ev + ma.group(2),
            html
        )

    # data-i18n-select="key" → regenerate <option> list
    for m in re.finditer(r'data-i18n-select="([^"]+)"', html):
        key = m.group(1)
        opts_list = extract_array_val(js_block, key)
        if not opts_list:
            continue
        opts_html = ''.join(
            f'<option value="{esc_attr(opt) if i > 0 else ""}">{esc(opt)}</option>'
            for i, opt in enumerate(opts_list)
        )
        html = re.sub(
            r'(<select[^>]*\bdata-i18n-select="' + re.escape(key) + r'"[^>]*>)[\s\S]*?(</select>)',
            lambda ma, oh=opts_html: ma.group(1) + oh + ma.group(2),
            html
        )

    return html


# ── Static FAQ rendering ──────────────────────────────────────────────────────

def render_faq_html(faqs: list) -> str:
    parts = []
    for i, faq in enumerate(faqs):
        border_bottom = ';border-bottom:1px solid var(--border)' if i == len(faqs) - 1 else ''
        parts.append(
            f'    <div style="border-top:1px solid var(--border){border_bottom};">\n'
            f'      <button onclick="toggleFaq(this)" aria-expanded="false" '
            f'style="width:100%;display:flex;justify-content:space-between;align-items:center;'
            f'padding:1.3rem 0;background:none;border:none;cursor:pointer;text-align:left;'
            f'gap:1rem;font-family:\'Inter\',sans-serif;font-size:.95rem;font-weight:600;'
            f'color:var(--navy);">\n'
            f'        <span>{esc(faq["q"])}</span>\n'
            f'        <svg class="faq-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" '
            f'style="flex-shrink:0;transition:transform .2s;">'
            f'<line x1="8" y1="2" x2="8" y2="14" stroke="var(--blue)" stroke-width="1.5"/>'
            f'<line x1="2" y1="8" x2="14" y2="8" stroke="var(--blue)" stroke-width="1.5"/>'
            f'</svg>\n'
            f'      </button>\n'
            f'      <div class="faq-answer" style="max-height:0;overflow:hidden;'
            f'transition:max-height .3s ease;">\n'
            f'        <p style="padding:0 0 1.3rem;font-size:.9rem;color:var(--muted-text);'
            f'line-height:1.8;">{esc(faq["a"])}</p>\n'
            f'      </div>\n'
            f'    </div>'
        )
    return '\n'.join(parts)


# ── JSON-LD @graph ────────────────────────────────────────────────────────────

def build_jsonld(lang: str, faqs: list) -> str:
    nl = lang == 'nl'
    url_path = '' if nl else 'en/'
    graph = {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Organization',
                '@id': 'https://finaxis.nl/#org',
                'name': 'Finaxis',
                'legalName': 'Finaxis Financial Services',
                'url': 'https://finaxis.nl/',
                'logo': 'https://finaxis.nl/logo-icon.png',
                'founder': {'@id': 'https://finaxis.nl/#alexander'},
                'areaServed': [
                    {'@type': 'Country', 'name': 'Netherlands'},
                    {'@type': 'AdministrativeArea', 'name': 'European Union'}
                ],
                'contactPoint': [{
                    '@type': 'ContactPoint',
                    'telephone': '+31-6-25009505',
                    'contactType': 'sales',
                    'areaServed': ['NL', 'EU'],
                    'availableLanguage': ['nl', 'en'],
                    'email': 'info@finaxis.nl'
                }],
                'sameAs': ['https://www.linkedin.com/company/118834398/']
            },
            {
                '@type': 'ProfessionalService',
                '@id': 'https://finaxis.nl/#service',
                'name': 'Finaxis',
                'parentOrganization': {'@id': 'https://finaxis.nl/#org'},
                'description': (
                    'Specialistteam voor acceptatie, debiteurenadministratie en '
                    'CDD/KYC-compliance. EU-breed inzetbaar vanuit Nederland.'
                    if nl else
                    'Specialist financial operations team for underwriting, accounts '
                    'receivable, and CDD/KYC compliance. Netherlands-based, EU-deployed.'
                ),
                'serviceType': [
                    'Underwriting outsourcing',
                    'Accounts receivable management',
                    'CDD/KYC compliance'
                ],
                'knowsAbout': [
                    'Underwriting', 'Accounts Receivable', 'CDD', 'KYC',
                    'AML', 'WWFT', 'GDPR', 'DNB', 'Financial operations'
                ],
                'hasOfferCatalog': {
                    '@type': 'OfferCatalog',
                    'name': 'Financiële operatiediensten' if nl else 'Financial operations services',
                    'itemListElement': [
                        {'@type': 'Offer', 'itemOffered': {'@type': 'Service',
                         'name': 'Acceptatie' if nl else 'Underwriting'}},
                        {'@type': 'Offer', 'itemOffered': {'@type': 'Service',
                         'name': 'Debiteurenbeheer' if nl else 'Accounts Receivable'}},
                        {'@type': 'Offer', 'itemOffered': {'@type': 'Service',
                         'name': 'CDD/KYC Compliance'}}
                    ]
                }
            },
            {
                '@type': 'Person',
                '@id': 'https://finaxis.nl/#alexander',
                'name': 'Alexander Gevorgyan',
                'jobTitle': 'Oprichter' if nl else 'Founder',
                'worksFor': {'@id': 'https://finaxis.nl/#org'}
            },
            {
                '@type': 'WebSite',
                '@id': 'https://finaxis.nl/#website',
                'url': 'https://finaxis.nl/',
                'name': 'Finaxis',
                'publisher': {'@id': 'https://finaxis.nl/#org'},
                'inLanguage': ['nl-NL', 'en-GB']
            },
            {
                '@type': 'LocalBusiness',
                '@id': 'https://finaxis.nl/#local',
                'name': 'Finaxis',
                'image': 'https://finaxis.nl/logo-icon.png',
                'address': {
                    '@type': 'PostalAddress',
                    'addressCountry': 'NL',
                    'addressRegion': 'Nederland'
                },
                'telephone': '+31625009505',
                'email': 'info@finaxis.nl',
                'url': 'https://finaxis.nl/',
                'priceRange': '€€',
                'openingHours': 'Mo-Fr 09:00-18:00',
                'sameAs': ['https://www.linkedin.com/company/118834398/']
            },
            {
                '@type': 'FAQPage',
                '@id': f'https://finaxis.nl/{url_path}#faq',
                'mainEntity': [
                    {
                        '@type': 'Question',
                        'name': faq['q'],
                        'acceptedAnswer': {'@type': 'Answer', 'text': faq['a']}
                    }
                    for faq in faqs
                ]
            }
        ]
    }
    return json.dumps(graph, ensure_ascii=False, indent=2)


# ── Per-language <head> ───────────────────────────────────────────────────────

def build_head(lang: str) -> str:
    nl = lang == 'nl'
    p = '' if nl else 'en/'
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{"Finaxis | Outsourcing voor Acceptatie, Debiteurenbeheer en CDD/KYC | Nederland" if nl else "Finaxis | Outsourced Underwriting, Accounts Receivable &amp; CDD/KYC | Netherlands"}</title>
  <meta name="description" content="{"Specialistteam voor acceptatie, debiteurenbeheer en CDD/KYC. Bewezen trackrecord bij Stellantis, Generali en Ayvens. Operationeel binnen 5 werkdagen." if nl else "Specialist financial operations for underwriting, AR and CDD/KYC. Proven track record with Stellantis, Generali and Ayvens. Netherlands-based, EU-deployed."}" />
  <meta name="keywords" content="{"acceptatie outsourcing Nederland, debiteurenbeheer specialist, CDD KYC compliance outsourcing, financiële operaties outsourcing, AML compliance specialist, freelance underwriter Nederland, KYC onboarding specialist" if nl else "underwriting outsourcing Netherlands, accounts receivable specialist, CDD KYC compliance outsourcing, financial operations outsourcing, AML compliance specialist, freelance underwriter Netherlands"}" />
  <meta name="author" content="Finaxis" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large" />
  <meta name="theme-color" content="#0A2456" />
  <link rel="canonical"  href="https://finaxis.nl/{p}" />
  <link rel="alternate"  hreflang="nl"        href="https://finaxis.nl/" />
  <link rel="alternate"  hreflang="en"        href="https://finaxis.nl/en/" />
  <link rel="alternate"  hreflang="x-default" href="https://finaxis.nl/" />
  <link rel="manifest"   href="/site.webmanifest" />
  <link rel="icon"        type="image/png" href="/logo-icon.png" />
  <link rel="apple-touch-icon" href="/logo-icon.png" />
  <meta property="og:type"             content="website" />
  <meta property="og:url"              content="https://finaxis.nl/{p}" />
  <meta property="og:title"            content="{"Finaxis | Outsourcing voor Acceptatie, Debiteurenbeheer en CDD/KYC" if nl else "Finaxis | Outsourced Underwriting, Accounts Receivable &amp; CDD/KYC"}" />
  <meta property="og:description"      content="{"Specialist in financiële operaties. Bewezen trackrecord bij Stellantis, Generali, Ayvens, ALD en LeasePlan. Nederland · EU-breed inzetbaar." if nl else "Specialist financial operations team. Proven track record with Stellantis, Generali, Ayvens, ALD and LeasePlan. Netherlands-based, EU-deployed."}" />
  <meta property="og:site_name"        content="Finaxis" />
  <meta property="og:locale"           content="{"nl_NL" if nl else "en_GB"}" />
  <meta property="og:locale:alternate" content="{"en_GB" if nl else "nl_NL"}" />
  <meta property="og:image"            content="https://finaxis.nl/assets/og/finaxis-share-{lang}.png" />
  <meta property="og:image:width"      content="1200" />
  <meta property="og:image:height"     content="630" />
  <meta property="og:image:type"       content="image/png" />
  <meta property="og:image:alt"        content="{"Finaxis — Outsourcing voor financiële operaties" if nl else "Finaxis — Outsourced financial operations"}" />
  <meta name="twitter:card"            content="summary_large_image" />
  <meta name="twitter:title"           content="{"Finaxis | Outsourcing voor Acceptatie, Debiteurenbeheer en CDD/KYC" if nl else "Finaxis | Outsourced Underwriting, Accounts Receivable &amp; CDD/KYC"}" />
  <meta name="twitter:description"     content="{"Specialist in financiële operaties. Bewezen trackrecord bij Stellantis, Generali, Ayvens. Nederland · EU-breed inzetbaar." if nl else "Specialist financial operations team. Proven track record with Stellantis, Generali, Ayvens. Netherlands-based, EU-deployed."}" />
  <meta name="twitter:image"           content="https://finaxis.nl/assets/og/finaxis-share-{lang}.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet" media="print" onload="this.media='all'" />
  <noscript><link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet" /></noscript>
  <link rel="dns-prefetch" href="https://www.linkedin.com" />'''


# ── Sitemap ───────────────────────────────────────────────────────────────────

def build_sitemap() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://finaxis.nl/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
    <xhtml:link rel="alternate" hreflang="nl"        href="https://finaxis.nl/"/>
    <xhtml:link rel="alternate" hreflang="en"        href="https://finaxis.nl/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://finaxis.nl/"/>
  </url>
  <url>
    <loc>https://finaxis.nl/en/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
    <xhtml:link rel="alternate" hreflang="nl"        href="https://finaxis.nl/"/>
    <xhtml:link rel="alternate" hreflang="en"        href="https://finaxis.nl/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://finaxis.nl/"/>
  </url>
</urlset>'''


# ── IndexNow ──────────────────────────────────────────────────────────────────

def ping_indexnow(key: str) -> None:
    payload = json.dumps({
        'host': 'finaxis.nl',
        'key': key,
        'keyLocation': f'https://finaxis.nl/{key}.txt',
        'urlList': ['https://finaxis.nl/', 'https://finaxis.nl/en/']
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.indexnow.org/indexnow',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f'  IndexNow: HTTP {resp.status}')
    except urllib.error.HTTPError as e:
        print(f'  IndexNow error: {e.code} {e.reason}')
    except Exception as e:
        print(f'  IndexNow error: {e}')


# ── Build one language ────────────────────────────────────────────────────────

def build_page(lang: str, template: str, js_block: str, faqs: list) -> str:
    nl = lang == 'nl'

    # Strip everything before <style> (the old <head>); prepend new head
    style_marker = '\n  <style>\n    /* ── DESIGN TOKENS'
    style_idx = template.index(style_marker)
    html = build_head(lang) + template[style_idx:]

    # Apply translations
    html = apply_translations(html, js_block)

    # Render FAQ statically (for crawlers; JS rebuilds it for users)
    faq_html = render_faq_html(faqs)
    html = re.sub(
        r'<div id="faq-list"[^>]*></div>',
        f'<div id="faq-list" style="max-width:800px;">\n{faq_html}\n      </div>',
        html
    )

    # Replace JSON-LD block with full @graph
    jsonld = build_jsonld(lang, faqs)
    html = re.sub(
        r'<script type="application/ld\+json">[\s\S]*?</script>',
        f'<script type="application/ld+json">\n{jsonld}\n  </script>',
        html
    )

    # EN page: change default setLang call so toggle starts on English
    if not nl:
        html = re.sub(r"\bsetLang\('nl'\);", "setLang('en');", html)

    return html


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f'Reading {SRC}')
    template = SRC.read_text(encoding='utf-8')

    # Extract translation blocks
    trans_block = extract_block(template, 'var translations = {', '{')
    en_block    = extract_block(trans_block, 'en: {', '{')
    nl_block    = extract_block(trans_block, 'nl: {', '{')

    # Extract FAQ arrays from buildFaq()
    faq_func    = extract_block(template, 'function buildFaq(lang)', '{')
    faqs_en     = parse_qa_array(extract_block(faq_func, 'var faqsEN = [', '['))
    faqs_nl     = parse_qa_array(extract_block(faq_func, 'var faqsNL = [', '['))
    print(f'  {len(faqs_en)} EN FAQs, {len(faqs_nl)} NL FAQs extracted')

    # Create output dirs
    (DIST / 'en').mkdir(parents=True, exist_ok=True)

    # Build NL
    nl_html = build_page('nl', template, nl_block, faqs_nl)
    (DIST / 'index.html').write_text(nl_html, encoding='utf-8')
    print(f'  dist/index.html       {len(nl_html):,} chars')

    # Build EN
    en_html = build_page('en', template, en_block, faqs_en)
    (DIST / 'en' / 'index.html').write_text(en_html, encoding='utf-8')
    print(f'  dist/en/index.html    {len(en_html):,} chars')

    # Sitemap
    (DIST / 'sitemap.xml').write_text(build_sitemap(), encoding='utf-8')
    print(f'  dist/sitemap.xml')

    # IndexNow key file
    (DIST / f'{INDEXNOW_KEY}.txt').write_text(INDEXNOW_KEY, encoding='utf-8')
    print(f'  dist/{INDEXNOW_KEY}.txt')

    print('\nBuild complete.')

    if '--ping' in sys.argv:
        print('Pinging IndexNow...')
        ping_indexnow(INDEXNOW_KEY)


if __name__ == '__main__':
    main()
