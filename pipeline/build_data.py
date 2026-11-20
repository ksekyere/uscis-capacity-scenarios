"""
build_data.py

Cleans USCIS application counts (fiscal years 2013 to the latest quarter) and builds the
data file behind the dashboard.

Input
    data/raw/as_of_june_2026_pending_uscis_applications.csv
        One row per form (or form subtype) per fiscal year: forms received, approved, denied,
        total completed, and pending at the end of the period. Compiled from USCIS's quarterly
        "Number of Service-wide Forms by Fiscal Year To-Date, Quarter, and Form Status" reports.

Outputs
    data/uscis_forms_clean.csv   tidy, harmonized rows (one per form or subtype per year)
    data/uscis_dashboard.json    series for every view the dashboard offers

Run from the repository root:
    python3 -m pip install -r pipeline/requirements.txt
    python3 pipeline/build_data.py

Cleaning steps (each one is listed in the README):
    1. Read the file as Latin-1 (it mixes encodings) and repair garbled characters ("FiancÃ©e").
    2. Trim stray spaces in descriptions (2021-2022 rows end in a space).
    3. Merge form codes that are the same workload under a different code:
         N-600/600K -> N-600, I-600/600A -> I-600, I-800/800A -> I-800,
         I-924/924A and I-924A -> I-924, I-889 -> I-899 (typo; the two never overlap),
         I-867 -> I-870 (credible fear referral, replaced by the worksheet in FY2020).
    4. Mark the latest fiscal year as partial, so the dashboard can annualize it.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "as_of_june_2026_pending_uscis_applications.csv"
OUT_CSV = ROOT / "data" / "uscis_forms_clean.csv"
OUT_JSON = ROOT / "data" / "uscis_dashboard.json"

# The latest fiscal year in the file is partial. The federal fiscal year starts October 1,
# so data "as of June 30" covers 9 months. Update both when a new quarter is added.
LATEST_FY = 2026
LATEST_FY_MONTHS = 9
AS_OF = "June 30, 2026"

CODE_MAP = {
    "N-600/600K": "N-600",
    "I-600/600A": "I-600",
    "I-800/800A": "I-800",
    "I-924/924A": "I-924",
    "I-924A": "I-924",
    "I-889": "I-899",
    "I-867": "I-870",
}

CATEGORY_LABELS = {
    "Citizenship": "Citizenship",
    "Lawful Permanent Resident": "Permanent residence",
    "Family Based": "Family-based",
    "Employee Based": "Employment-based",
    "Humanitarian": "Humanitarian",
    "Other": "Other",
    "Supplemental Processing": "Supplemental processing",
}

FORM_LABELS = {
    "N-400": "Naturalization",
    "N-600": "Certificate of citizenship",
    "N-565": "Replacement citizenship document",
    "N-336": "Naturalization hearing request",
    "N-648": "Disability exception for naturalization",
    "N-300": "Declaration of intention",
    "N-470": "Preserve residence for naturalization",
    "N-644": "Posthumous citizenship",
    "I-485": "Permanent residence (adjustment of status)",
    "I-130": "Petition for a relative",
    "I-129F": "Fiancé(e) petition",
    "I-751": "Remove conditions on residence",
    "I-601A": "Provisional unlawful presence waiver",
    "I-600": "Orphan petition",
    "I-800": "Convention adoptee petition",
    "I-589": "Asylum (affirmative)",
    "I-821": "Temporary Protected Status",
    "I-821D": "Deferred Action for Childhood Arrivals (DACA)",
    "I-918": "U visa (victims of crime)",
    "I-914": "T visa (victims of trafficking)",
    "I-929": "U visa family member",
    "I-730": "Refugee or asylee relative petition",
    "I-870": "Credible fear screening",
    "I-899": "Reasonable fear screening",
    "I-817": "Family unity benefits",
    "I-881": "NACARA suspension or cancellation of removal",
    "G-325A": "Biographic information (deferred action)",
    "Legalization": "Legalization / Special Agricultural Workers",
    "I-765": "Employment authorization (work permit)",
    "I-129": "Temporary worker petition",
    "I-140": "Employment-based immigrant petition",
    "I-526": "Investor petition",
    "I-526E": "Regional center investor petition",
    "I-829": "Investor: remove conditions",
    "I-924": "Regional center (legacy program)",
    "I-956": "Regional center designation",
    "I-956F": "Regional center investment approval",
    "I-956G": "Regional center annual statement",
    "I-956H": "Regional center bona fides",
    "I-956K": "Regional center promoter registration",
    "I-90": "Replace or renew a green card",
    "I-131": "Travel document or parole",
    "I-539": "Extend or change nonimmigrant status",
    "I-360": "Special immigrant petition",
    "I-290B": "Appeal or motion",
    "I-824": "Action on an approved petition",
    "I-102": "Arrival-departure record",
    "I-193": "Passport or visa waiver",
    "I-941": "Entrepreneur parole",
    "Waivers": "Waivers (various forms)",
    "DS-230 (IV)": "Immigrant visa processing",
    "EOIR Adjustment": "Adjustment cases from immigration court",
}

# Forms pinned at the top of the dashboard's selector
KEY_FORMS = ["N-400", "I-485", "I-130", "I-589", "I-765", "I-821", "I-140", "I-129", "I-751", "I-90"]

# A form appears in the selector if it ever reached this many receipts or pending cases
MIN_VOLUME = 1000


def repair_text(s: str) -> str:
    """Undo UTF-8 text that was decoded as Latin-1 ("FiancÃ©e" -> "Fiancée")."""
    s = str(s).strip()
    if "Ã" in s:
        try:
            s = s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return s


def clean() -> pd.DataFrame:
    d = pd.read_csv(RAW, encoding="latin-1")
    d["description"] = d["description"].map(repair_text)
    d["form_original"] = d["form"].str.strip()
    d["form"] = d["form_original"].replace(CODE_MAP)
    d["category"] = d["app_category"].map(CATEGORY_LABELS).fillna(d["app_category"])
    d = d.rename(columns={"forms_received": "received", "total_completed": "completed"})
    d["partial_year"] = d["fiscal_year"] == LATEST_FY
    cols = ["fiscal_year", "category", "form", "form_original", "description",
            "received", "approved", "denied", "completed", "pending", "partial_year"]
    return d[cols].sort_values(["fiscal_year", "category", "form", "description"]).reset_index(drop=True)


def to_list(s: pd.Series, years: list[int]) -> list:
    s = s.reindex(years)
    return [None if (v is None or (isinstance(v, float) and math.isnan(v))) else round(float(v)) for v in s]


def series(frame: pd.DataFrame, years: list[int], with_outcomes: bool) -> dict:
    g = frame.groupby("fiscal_year")
    out = {k: to_list(g[k].sum(min_count=1), years) for k in ("received", "completed", "pending")}
    if with_outcomes:
        out["approved"] = to_list(g["approved"].sum(min_count=1), years)
        out["denied"] = to_list(g["denied"].sum(min_count=1), years)
    return out


def main() -> None:
    d = clean()
    years = sorted(d["fiscal_year"].unique().tolist())
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT_CSV, index=False)

    groups, data = [], {}
    groups.append({"id": "all", "label": "All forms", "kind": "all"})
    data["all"] = series(d, years, with_outcomes=False)

    for cat in CATEGORY_LABELS.values():
        sub = d[d["category"] == cat]
        if sub.empty:
            continue
        gid = f"cat:{cat}"
        groups.append({"id": gid, "label": cat, "kind": "category"})
        data[gid] = series(sub, years, with_outcomes=False)

    for (cat, form), sub in d.groupby(["category", "form"]):
        if max(sub["received"].max(skipna=True) or 0, sub["pending"].max(skipna=True) or 0) < MIN_VOLUME:
            continue
        gid = f"form:{form}"
        groups.append({
            "id": gid, "kind": "form", "form": form, "category": cat,
            "label": f"{form} · {FORM_LABELS.get(form, sub.sort_values('fiscal_year')['description'].iloc[-1])}",
            "key": form in KEY_FORMS,
        })
        data[gid] = series(sub, years, with_outcomes=True)

    out = {
        "meta": {
            "title": "US Immigration Processing Capacity",
            "source": "U.S. Citizenship and Immigration Services (USCIS), Number of Service-wide Forms by "
                      "Fiscal Year To-Date, Quarter, and Form Status (quarterly All Forms reports)",
            "source_url": "https://www.uscis.gov/tools/reports-and-studies/immigration-and-citizenship-data",
            "raw_file": RAW.name,
            "first_fy": years[0],
            "latest_fy": LATEST_FY,
            "latest_fy_months": LATEST_FY_MONTHS,
            "as_of": AS_OF,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "key_forms": KEY_FORMS,
        },
        "years": years,
        "groups": groups,
        "series": data,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    forms = [g for g in groups if g["kind"] == "form"]
    print(f"Wrote {OUT_CSV.relative_to(ROOT)} ({len(d)} rows) and {OUT_JSON.relative_to(ROOT)} "
          f"({OUT_JSON.stat().st_size / 1024:.0f} KB)")
    print(f"FY{years[0]}–FY{years[-1]} (FY{LATEST_FY} through {AS_OF}); "
          f"{len(groups) - len(forms)} overview groups, {len(forms)} forms")


if __name__ == "__main__":
    main()
