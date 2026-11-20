# USCIS Capacity Scenarios

An interactive dashboard of U.S. Citizenship and Immigration Services (USCIS) caseloads, fiscal years 2013 to 2026, with scenarios for the pending caseload through FY2030.

**Live dashboard:** https://ksekyere.github.io/uscis-capacity-scenarios/

It is built for researchers who want to see, quickly and transparently, whether USCIS processing keeps pace with the applications it receives, and how the backlog could change under different assumptions about demand and processing capacity.

## What the dashboard shows

One selector at the top chooses the scope: all forms, a USCIS category (citizenship, permanent residence, family-based, employment-based, humanitarian, other, supplemental processing) or a single form. Every section follows it.

| Section | Question it answers |
|---|---|
| Findings | How large is the pending caseload, how long would it take to clear, and how has the processing pace changed? |
| Caseload | How many applications were received, completed and left pending each year? |
| Capacity | Is processing keeping up (completed per 100 received), and how many months of work are in the backlog? Which years show changes in pending that receipts and completions don't explain? |
| Scenarios | Where could the pending caseload be by FY2030 under different growth rates for receipts and completions? |
| Asylum demand | What would affirmative asylum filings (I-589) be if they followed global asylum claims, and what would that mean for the asylum backlog? |
| Citizenship | How are naturalization (N-400) and the forms that lead to it (I-130, I-485, I-751) moving? |
| Global context | How many people are forcibly displaced, which countries host them, how much of that falls on high-income countries, and how are ageing, fertility and migration changing in high-income countries and the US? |
| Data notes | What the data can and can't show, cleaning steps, sources |

## Definitions

- **Received:** applications and petitions filed during the fiscal year.
- **Completed:** applications decided or otherwise closed during the year. For most forms this equals approved plus denied. For some humanitarian forms (affirmative asylum, credible fear and reasonable fear screenings) it also includes other outcomes, such as referrals to immigration court and administrative closures, so it can be larger than approved plus denied.
- **Pending:** applications awaiting a decision at the end of the period (September 30, or June 30 for FY2026).
- **Completed per 100 received:** completed ÷ received × 100. Below 100 means the backlog grew that year.
- **Months of work:** pending ÷ (annual completions ÷ 12). How long it would take to finish everything pending at that year's completion pace if nothing new arrived.
- **Fiscal year:** October 1 to September 30. FY2026 covers October 2025 to June 2026 (9 months). Where a full-year rate is needed, FY2026 received and completed counts are annualized (× 12/9). Pending is never annualized.

## Scenario method

Each scenario starts from the pending count on June 30, 2026 and steps forward one fiscal year at a time:

```
pending (end of FY2026) = pending (June 2026) + (receipts − completions) × 3/12
pending (FY t)          = pending (FY t−1) + receipts (t) − completions (t)
receipts (t)            = starting receipts × (1 + receipt growth)^(t − 2026)
completions (t)         = starting completions × (1 + completion growth)^(t − 2026)
```

Pending is not allowed to fall below zero. Starting rates can be the FY2026 pace (annualized), FY2025, or the FY2023–FY2025 average.

Presets, all starting from the FY2026 pace:

| Preset | Receipts | Completions |
|---|---|---|
| Current pace continues | flat | flat |
| Capacity returns to FY2024 level | flat | grow at the steady rate that reaches FY2024 completions by FY2030 |
| Demand returns to FY2025 level | grow at the steady rate that reaches FY2025 receipts by FY2030 | flat |
| Both return | as above | as above |
| Capacity falls 10% a year | flat | −10% a year |

These are arithmetic projections of stated assumptions, not forecasts. They ignore cases closed without a decision (see below), changes in the mix of forms, and policy changes.

## Asylum demand method

Receipts measure what people were able to file, not how many people seek protection. For affirmative asylum (form I-589) the dashboard also estimates demand from UNHCR's count of new asylum claims worldwide:

```
US claims (t)         = world new claims (latest full year, or 3-year average) × US share of world claims
                        × [ (1 − m) × (1 + world growth)^(t − latest)
                            +    m  × (1 + main-origin displacement growth)^(t − latest) ]
modeled I-589s (FY t) = US claims (t) × I-589 forms per 100 US claims ÷ 100
```

`m` is the share of US claims with a recorded origin that came from the ten main origin countries in 2022 to the latest full year (about 73%). Claims from those countries follow the displacement slider; claims from everywhere else follow world claims. With both sliders at the same value the formula reduces to world claims × share × ratio.

- **World new claims:** first-time asylum applications in every country, calendar years, from UNHCR (`app_type = "N"`, so appeals and repeat claims are excluded). UNHCR counts most countries' claims as people. US claims filed with USCIS are reported as cases (one application can cover a family) in 2013–2020 and 2025, and as people in 2021–2024; immigration court claims are counted as people.
- **US share of world claims:** averaged 10% in 2013–2019 and 30% in 2022–2025.
- **I-589 forms per 100 US claims:** USCIS fiscal-year I-589 receipts ÷ UNHCR's calendar-year US claims × 100. It combines the share of US claims filed with USCIS rather than in immigration court, whether UNHCR's USCIS figures were cases or people that year (people in 2021–2024, which lowers the ratio), and the three-month offset between fiscal and calendar years. It averaged 55 in FY2013–FY2019 and 42 in FY2022–FY2025; FY2026 filings so far are about 15 per 100 2025 claims.
- **Main-origin displacement:** people displaced abroad (refugees, asylum seekers and others in need of international protection) from the ten countries with the most new US claims since 2022. It grew about 11% a year from 2019 to 2025, mostly from Venezuela; one preset continues that trend.
- **Pending paths:** both start from June 30, 2026 and finish FY2026 at the current pace. From FY2027, one path adds modeled demand and the other holds filings at the FY2026 pace; both subtract the same completions (FY2026 pace, changed by the completions slider).

Presets use the 2022–2025 or 2013–2019 averages, with world claims flat, +5% or −5% a year, or with main-origin displacement continuing its 2019–2025 trend.

### Countries of origin and their conditions

The section also shows where US claims come from (any of 2019, 2023, the latest full year and UNHCR's mid-year figures) and a table of conditions in the ten main origin countries: US claims and the US share of each country's claims worldwide, people displaced abroad and the change since 2019, deaths in organized violence (UCDP), homicides per 100,000, change in GDP per person since 2019 and political stability (World Bank). These describe conditions people leave; they do not show why people choose the United States, and they are not used to fit a statistical model, since about a dozen years of data for ten countries, with large policy changes in between, is too little for that.

Two data gaps: in 2025, 31% of US claims (mostly those filed with USCIS) have no recorded origin, so per-country figures for that year are too low; and UCDP counts deaths in organized violence (state-based conflict, non-state conflict including cartel fighting, and one-sided violence), not ordinary crime, which the homicide rate covers. The gap between modeled demand and current filings could reflect people who are turned away or deterred, claims made in immigration court instead, or an estimate that is too high; the data can't tell these apart. Only asylum is modeled this way: family and employment filings are limited by visa caps and eligibility rules, and naturalization depends on the number of permanent residents eligible to apply.

## Data

### USCIS

**Source:** U.S. Citizenship and Immigration Services, *Number of Service-wide Forms by Fiscal Year To-Date, Quarter, and Form Status* (quarterly "All Forms" reports), [USCIS Immigration and Citizenship Data](https://www.uscis.gov/tools/reports-and-studies/immigration-and-citizenship-data). USCIS data is a work of the U.S. federal government and generally in the public domain in the United States.

| File | Contents |
|---|---|
| `data/raw/as_of_june_2026_pending_uscis_applications.csv` | The compiled source file, unchanged |
| `data/uscis_forms_clean.csv` | Cleaned rows: one per form (or form subtype) per fiscal year |
| `data/uscis_dashboard.json` | The series the dashboard reads |

### Compiling the source file (R)

`data/raw/as_of_june_2026_pending_uscis_applications.csv` was compiled from the quarterly reports in R. The compiling script will be added to this repository in a later update; its steps were:

1. **One reader per report layout.** USCIS changed the layout of its reports over time: Excel reports from FY2024 on are read from cells A5:M80, and the older CSV layouts (the 2014, 2018 and 2019–2020 formats) are read after skipping their header rows.
2. **Common column names:** form, description, forms_received, approved, denied, total_completed, pending.
3. **Numbers:** thousands separators removed; dashes (USCIS's "none") set to 0.
4. **Completions in older layouts:** denials, spread across several columns, are summed, and `total_completed` is calculated as approved + denied. In the compiled file every row through FY2019 has completed = approved + denied; from FY2020 most forms carry USCIS's reported total completions, which also include other closures (see Limitations).
5. **Form codes:** footnote numbers attached to codes are stripped ("I-58913" → I-589, "N-40021" → N-400), and remaining variants are matched by pattern.
6. **Categories:** each form is assigned to one of seven categories (Citizenship, Lawful Permanent Resident, Family Based, Employee Based, Humanitarian, Other, Supplemental Processing).
7. **Rows without a description** (headings, totals and notes) are dropped.

### Preparing the data for the dashboard (Python)

1. Read the raw file as Latin-1 (it mixes encodings) and repaired garbled characters, for example "FiancÃ©e" → "Fiancée".
2. Trimmed stray spaces (FY2021–FY2022 descriptions end in a space).
3. Merged codes that record the same workload:
   - N-600/600K → N-600, I-600/600A → I-600, I-800/800A → I-800
   - I-924/924A and I-924A → I-924 (legacy regional center program)
   - I-889 → I-899 (reasonable fear; I-889 appears to be a typo, and the two never appear in the same year)
   - I-867 → I-870 (credible fear: the referral form was replaced by the worksheet in FY2020)
4. Marked FY2026 as a partial year.

Forms that never reached 1,000 receipts or pending cases are included in all totals but not listed individually in the selector. The original form code is kept in the `form_original` column of the clean file.

### Global context (UN and World Bank)

Built by `pipeline/build_global.py`, which writes `data/global_context.json` (what the dashboard reads) and `data/global_context_long.csv` (every value in long format).

| Data | Source | Years |
|---|---|---|
| Refugees, asylum seekers, others in need of international protection, by host country | UNHCR Refugee Data Finder, via UNHCR's [`refugees` R package](https://github.com/PopulationStatistics/refugees) (version recorded in the JSON) | 2000–latest |
| Palestine refugees under UNRWA's mandate | UNRWA, via the same package | 2000–latest |
| New asylum claims, by country where filed; US split between USCIS (affirmative) and immigration court (defensive) | UNHCR, via the same package | 2006–latest |
| Internally displaced people (conflict) | Internal Displacement Monitoring Centre (IDMC), via the same package | 2000–latest |
| Deaths in organized violence by country (state-based, non-state, one-sided; best estimates) | Uppsala Conflict Data Program, [Country-Year Dataset on Organized Violence within Country Borders](https://ucdp.uu.se/downloads/) | 1989–latest |
| Homicides per 100,000, GDP per person, inflation (origin countries) | World Bank World Development Indicators | 2013–latest |
| Political stability and absence of violence (origin countries) | World Bank Worldwide Governance Indicators | 2013–latest |
| Country income groups (high income, low and middle income) | World Bank country classification | current |
| Old-age dependency ratio, fertility rate, working-age share, with projections to 2050 | World Bank *Population estimates and projections* (based on UN *World Population Prospects*), falling back to World Development Indicators | 2000–2050 |
| Net migration, international migrant stock (% of population), population | World Bank World Development Indicators (based on UN DESA and UN WPP estimates) | 2000–latest |

The section is meant to show the data as it falls, including where it complicates the USCIS picture. Things to know when reading it:

- **Totals are a sum of components.** The dashboard adds refugees, UNRWA refugees, others in need of international protection, asylum seekers and IDMC's conflict IDPs. This differs slightly from UNHCR's published headline (for example 117.8 million in *Global Trends 2025*), which uses UNHCR's own IDP figures and some other adjustments.
- **The US refugee and asylum series break before 2013.** UNHCR's US estimates change method around then, so the US chart starts in 2013. UNHCR's US asylum-seeker count is a broader measure than USCIS's pending I-589 caseload (it also covers cases in immigration court).
- **Hosting is measured where people are, not where they are resettled.** Refugees per 1,000 residents is shown only for countries with at least 1 million residents.
- **Mid-year releases.** UNHCR's June releases add figures for the first half of the current year. The script detects them from the package version (for example 2026.6.1): stocks are labeled "mid-2026", and January–June flows such as asylum claims are left out of the charts and the model, which use the latest full year. IDMC publishes once a year, so the mid-year internally displaced figure repeats the end-of-year count.
- **Projections are UN scenarios.** Values after the latest observed year are UN *World Population Prospects* medium-variant projections and are drawn dashed.
- **UCDP and World Bank columns need internet access.** UCDP data is downloaded from ucdp.uu.se as a zip file; if it can't be reached, the conflict column shows "–" and a "not loaded" note.
- **World Bank panels need the World Bank API.** If it can't be reached when the script runs, the JSON records `meta.world_bank.included = false` and the dashboard shows a "not loaded" note in place of those charts instead of guessing. Rerun the script to fill them in.

## Limitations

- **Every application counts the same.** A green card renewal (I-90) and an asylum case (I-589) each count as one.
- **Applications, not people.** One person may file several forms (for example I-485, I-765 and I-131 together).
- **No causes.** The data shows that receipts and completions changed, not why (policy, staffing, fees, litigation or demand).
- **Unexplained changes in pending.** In some years pending changes by more than receipts minus completions implies, for example, Temporary Protected Status (I-821) in FY2026, when pending fell by about 580,000 more than completions explain. These usually reflect cases closed without a decision, reclassification or reporting corrections. The dashboard lists them for any selection.
- **Completions changed definition in FY2020.** Through FY2019, completed is approved plus denied. From FY2020, USCIS's reported total completions also include referrals to immigration court and administrative closures for some forms (affirmative asylum, credible and reasonable fear screenings, TPS). Completions per 100 received and months of work for those forms are not fully comparable across FY2020.
- **USCIS only (for the caseload sections).** The USCIS data does not cover immigration courts (EOIR), visas issued abroad by the State Department, refugee admissions or border encounters. The Global context section adds displacement, demographic and migration data, but it describes conditions, not how many migrants any country needs or can absorb.

## Updating

When USCIS publishes a new quarter:

1. Replace the file in `data/raw/` (keep the same columns).
2. In `pipeline/build_data.py`, update `RAW` if the file name changed, and `LATEST_FY`, `LATEST_FY_MONTHS` and `AS_OF`.
3. Rebuild the data:

```bash
python3 -m pip install -r pipeline/requirements.txt
python3 pipeline/build_data.py
python3 pipeline/build_global.py   # UN and World Bank context; needs internet access
```

UNHCR and the World Bank update once or twice a year, so `build_global.py` only needs rerunning when they publish. Downloaded UNHCR files are cached in `data/raw/unhcr/` (ignored by git).

The dashboard reads the new JSON automatically. To view it locally, run `python3 -m http.server` in the repository folder and open http://localhost:8000; opening `index.html` directly from disk won't load the data.

## Repository structure

```
uscis-capacity-scenarios/
├── index.html                 # the dashboard (no build step)
├── data/
│   ├── raw/                   # source file, unchanged
│   ├── uscis_forms_clean.csv
│   ├── uscis_dashboard.json
│   ├── global_context.json      # UN and World Bank series
│   └── global_context_long.csv
└── pipeline/
    ├── build_data.py            # USCIS
    ├── build_global.py          # UNHCR, UNRWA, IDMC, World Bank
    └── requirements.txt
```

## About

Maintained by Kofi Forkuo-Sekyere, Research and Evaluation Associate at the [Acacia Center for Justice](https://acaciajustice.org).

This is independent research. The analysis, interpretations and any errors are the author's own and do not represent the views or positions of the Acacia Center for Justice. The work also reflects the research infrastructure, training and support the Center provides its researchers, without which it would have been much harder to build.

## Citation

Forkuo-Sekyere, K. (2026). *USCIS Capacity Scenarios* [Dashboard and data]. https://github.com/ksekyere/uscis-capacity-scenarios. Data: U.S. Citizenship and Immigration Services; UNHCR; World Bank; United Nations.

Developed with the assistance of Claude, an AI model made by Anthropic.
