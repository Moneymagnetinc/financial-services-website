# Finaxis — Google Ads launch plan

Goal: generate qualified B2B leads (CFOs / heads of compliance / operations) that turn into
client conversations. High-value, low-volume niche → **Search only** (no Display, no Performance
Max to start). Send every click to the *specific* service page, never the homepage.

> Before spending: set up **conversion tracking** (see last section). Running ads without it is
> flying blind — you can't tell which keyword produced a lead.

---

## Account structure

Separate campaigns by market, because the landing page, language and intent differ:

| Campaign | Lang | Daily budget (start) | Landing pages |
|---|---|---|---|
| 1. NL — Core services | NL | €20 | `/debiteurenbeheer/`, `/acceptatie/`, `/cdd-kyc/`, `/freelance/` |
| 2. US — BSA/AML KYC | EN | €15 | `/us/cdd-kyc/` |
| 3. UAE — AML KYC | EN | €10 | `/ae/cdd-kyc/` |

Start one market (NL) for 2–3 weeks, learn, then switch the others on. Don't run all three cold.

Location targeting: Campaign 1 = Netherlands. Campaign 2 = United States (consider narrowing to
New York / NY metro first). Campaign 3 = United Arab Emirates (or Dubai only).
Set "Presence: people in your targeted locations" (not "interest").

---

## Campaign 1 — NL — Core services (ad groups)

Use **phrase** and **exact** match only at the start (broad match burns budget on a new account).

### Ad group A — Debiteurenbeheer → `/debiteurenbeheer/`
Keywords: "debiteurenbeheer uitbesteden", [debiteurenbeheer uitbesteden],
"debiteurenadministratie uitbesteden", "DSO verlagen", "accounts receivable uitbesteden",
"incasso uitbesteden b2b"

### Ad group B — Acceptatie / underwriting → `/acceptatie/`
Keywords: "acceptatie uitbesteden", "kredietacceptatie uitbesteden", "underwriting uitbesteden",
"acceptant inhuren", "freelance acceptant"

### Ad group C — CDD / KYC / WWFT → `/cdd-kyc/`
Keywords: "kyc uitbesteden", "cdd uitbesteden", "wwft specialist", "kyc specialist inhuren",
"klantonderzoek uitbesteden", "aml compliance uitbesteden"

### Ad group D — Freelance / interim → `/freelance/`
Keywords: "freelance kyc analist", "interim compliance specialist", "zzp acceptant",
"freelance debiteurenbeheer"

### Example ad copy (RSA — give Google 8–10 headlines, 3–4 descriptions)
Headlines: `KYC & CDD Uitbesteden` · `WWFT-Specialist Inhuren` · `Operationeel in 5 Werkdagen` ·
`Auditgereed Klantonderzoek` · `Vanuit Amsterdam, EU-breed` · `Geen Langetermijncontract` ·
`Bewezen bij Stellantis & Ayvens` · `Beheerde Dienst of Ingebed`
Descriptions: `Specialistteam voor acceptatie, debiteurenbeheer en CDD/KYC. Binnen 5 werkdagen
operationeel.` · `Auditgereed, WWFT- en EU-AML-conform. Plan een vrijblijvend gesprek.`
Path: `/kyc/uitbesteden`

---

## Campaign 2 — US — BSA/AML KYC → `/us/cdd-kyc/`
Keywords: "outsource kyc", "bsa aml outsourcing", "kyc outsourcing company",
"cdd outsourcing", "kyc remediation services", "ofac screening service", "edd outsourcing"
Headlines: `Outsource BSA/AML & KYC` · `Examination-Ready CDD` · `CIP, UBO & OFAC` ·
`Audit-Ready From Day One` · `Human-in-the-Loop Review`
Description: `Audit-ready KYC and customer due diligence — CIP, beneficial ownership, OFAC. Built
to withstand examination.`

## Campaign 3 — UAE — AML KYC → `/ae/cdd-kyc/`
Keywords: "kyc outsourcing uae", "aml compliance dubai", "cdd outsourcing uae",
"goaml reporting support", "kyc services dubai", "ubo verification uae"
Headlines: `Outsource AML & KYC — UAE` · `CBUAE, DFSA & ADGM` · `goAML-Ready` ·
`UBO & Sanctions Screening`

---

## Negative keywords (add at account level, expand weekly from the search-terms report)
`jobs`, `vacature`, `salaris`, `salary`, `opleiding`, `cursus`, `course`, `betekenis`,
`wat is`, `template`, `gratis`, `free`, `software`, `stage`, `internship`, `zzp worden`,
`zelf doen`, `voorbeeld`, `wikipedia`, `app`

(You want buyers, not students/job-seekers/DIY.)

---

## Ad extensions (assets) — set all of these, they lift CTR a lot
- **Sitelinks:** Acceptatie · Debiteurenbeheer · CDD/KYC · Over ons
- **Callouts:** "Operationeel in 5 werkdagen", "Geen langetermijncontract", "Auditgereed",
  "EU-breed inzetbaar"
- **Call extension:** +31 6 25 00 95 05
- **Structured snippet:** Services → Underwriting, Accounts Receivable, CDD/KYC, AI Automation
- **Lead form / location** as available

---

## Bidding & budget
1. Weeks 1–3: **Manual CPC** or **Maximize clicks** with a max CPC cap (~€4–6) to gather data.
2. Once you have ~15–30 conversions: switch to **Maximize conversions** (and later a target CPA).
3. Expect cost-per-click €4–€15 in this niche; a qualified B2B lead may cost €40–€150.
   One client is worth far more — but budget for a 4–6 week learning period, not instant ROI.

---

## Conversion tracking (do this FIRST — I can implement the site side)
1. In Google Ads → **Goals → Conversions → New conversion action → Website**.
2. Create actions for: **Contact form submit** (primary), **Phone click**, **WhatsApp click**.
3. Google gives you a **Conversion ID** (`AW-XXXXXXXXX`) and a tag.
4. **Paste the Conversion ID + labels to me** — I'll add the gtag to the site and fire the
   conversion event on form submit / phone / WhatsApp click, then deploy. Test with Tag Assistant.

Without this, optimisation is impossible. It's the single most important setup step.
