# Finaxis — ready-to-import Google Ads files

Three CSVs you (or an agency) can import into **Google Ads Editor** to launch in minutes.

## Files
- `finaxis-keywords.csv` — campaigns, ad groups, keywords, match types, max CPC
- `finaxis-ads-rsa.csv` — Responsive Search Ads (10 headlines + 4 descriptions each)
- `finaxis-negative-keywords.csv` — campaign-level negatives (blocks job/DIY/student searches)

All ad copy is within Google's limits (headline ≤30, description ≤90, path ≤15 chars).

## How to import
1. Download **Google Ads Editor** (free desktop app) and sign in to your Ads account.
2. Create the three campaigns first (or let import create them): **NL - Core**, **US - BSA AML KYC**, **UAE - AML KYC**.
3. Account menu → **Import** → **From file** → select `finaxis-keywords.csv`. Review, then **Keep**.
4. Repeat Import for `finaxis-ads-rsa.csv` and `finaxis-negative-keywords.csv`.
5. Set per campaign: **daily budget** (NL €20, US €15, UAE €10), **location** (NL / US / UAE),
   **language**, and **bidding** (start Manual CPC or Maximize clicks with the max CPC caps).
6. **Post** to push live.

## Before you spend
Set up **conversion tracking** first (see `../google-ads-campaign.md`). Send me the
Google Ads **Conversion ID** and I'll wire form/phone/WhatsApp conversions into the site.

## Launch order
Start **NL - Core** only for 2–3 weeks. Use the **Search terms report** weekly to add new
negatives. Once you have ~15–30 conversions, switch bidding to **Maximize conversions**.
Then turn on US and UAE.
