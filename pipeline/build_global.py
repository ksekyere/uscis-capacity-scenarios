"""
build_global.py

Builds data/global_context.json, the data behind the dashboard's Global context section.

Sources
    UNHCR    Refugee Population Statistics Database, read from UNHCR's official "refugees" data
             package (github.com/PopulationStatistics/refugees). Refugees, asylum-seekers, other
             people in need of international protection, Palestine refugees under UNRWA, and
             internally displaced people (IDMC), by country of asylum and year; and new asylum
             applications by country where they were filed, with the US split between USCIS
             (affirmative claims) and the immigration courts (defensive claims).
    World    World Bank API: country income groups; population; old-age dependency ratio,
    Bank     fertility and working-age share, including projections to 2050 (Population estimates
             and projections); net migration (UN World Population Prospects) and international
             migrant stock (UN DESA), both as republished in the World Development Indicators.
             For the main countries of origin of US asylum claims: homicide rate, GDP per person,
             inflation (WDI) and political stability (Worldwide Governance Indicators).
    UCDP     Uppsala Conflict Data Program, Country-Year Dataset on Organized Violence within Country
             Borders: deaths in state-based conflict, non-state conflict and one-sided violence.

Run from the repository root:
    python3 -m pip install -r pipeline/requirements.txt
    python3 pipeline/build_global.py

If the World Bank API can't be reached, the script still writes the UNHCR part and the dashboard
marks the World Bank charts as not loaded. Nothing is estimated or filled in.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "unhcr"
OUT_JSON = ROOT / "data" / "global_context.json"
OUT_CSV = ROOT / "data" / "global_context_long.csv"

UNHCR_BASE = "https://raw.githubusercontent.com/PopulationStatistics/refugees/main"
UNHCR_FILES = ["population", "unrwa", "idmc", "asylum_applications"]
WB_API = "https://api.worldbank.org/v2"
UCDP_URLS = [f"https://ucdp.uu.se/downloads/organizedviolencecy/organizedviolencecy-{v}-csv.zip"
             for v in ("261", "251", "241")]
N_ORIGINS = 10   # main countries of origin of US asylum claims shown on the dashboard

# Gleditsch-Ward country numbers (used by UCDP) for likely origin countries -> ISO3
GW_ISO = {2: "USA", 20: "CAN", 40: "CUB", 41: "HTI", 42: "DOM", 51: "JAM", 70: "MEX", 90: "GTM", 91: "HND",
          92: "SLV", 93: "NIC", 94: "CRI", 95: "PAN", 100: "COL", 101: "VEN", 110: "GUY", 130: "ECU", 135: "PER",
          140: "BRA", 145: "BOL", 150: "PRY", 155: "CHL", 160: "ARG", 365: "RUS", 369: "UKR", 370: "BLR",
          371: "ARM", 372: "GEO", 373: "AZE", 433: "SEN", 435: "MRT", 438: "GIN", 452: "GHA", 471: "CMR",
          475: "NGA", 490: "COD", 520: "SOM", 530: "ETH", 531: "ERI", 540: "AGO", 625: "SDN", 630: "IRN",
          640: "TUR", 645: "IRQ", 651: "EGY", 652: "SYR", 666: "ISR", 679: "YEM", 700: "AFG", 702: "TJK",
          703: "KGZ", 704: "UZB", 705: "KAZ", 710: "CHN", 750: "IND", 770: "PAK", 771: "BGD", 775: "MMR",
          780: "LKA", 790: "NPL", 816: "VNM", 840: "PHL", 850: "IDN"}

FIRST_YEAR = 2000
# Shorter display names for long UNHCR country names
SHORT_NAMES = {"United States of America": "United States", "Iran (Islamic Rep. of)": "Iran",
               "Dem. Rep. of the Congo": "DR Congo", "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
               "Venezuela (Bolivarian Republic of)": "Venezuela", "Syrian Arab Rep.": "Syria",
               "United Rep. of Tanzania": "Tanzania", "Russian Federation": "Russia",
               "Bolivia (Plurinational State of)": "Bolivia", "Türkiye": "Türkiye"}
PROJECTION_END = 2050
# Some World Bank databases (such as Population estimates and projections) return aggregates
# with an empty ISO3 code and only the 2-letter World Bank id, so map those ids back.
WB_ID_ISO3 = {"XD": "HIC", "1W": "WLD", "XO": "LMY", "US": "USA"}
AGGREGATES = {"WLD": "World", "HIC": "High-income countries", "LMY": "Low- and middle-income countries", "USA": "United States"}

session = requests.Session()
session.headers["User-Agent"] = "uscis-capacity-scenarios (github.com/ksekyere)"


def get(url: str, params: dict | None = None, tries: int = 3, binary: bool = False):
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.content if binary else r.json()
        except (requests.RequestException, ValueError) as err:
            if attempt == tries:
                print(f"  ! could not fetch {url}: {err}", file=sys.stderr)
                return None
            time.sleep(2 * attempt)


# --------------------------------------------------------------------------------------
# UNHCR
# --------------------------------------------------------------------------------------

def unhcr_frames() -> tuple[dict[str, pd.DataFrame], str]:
    """Download (or reuse cached) UNHCR data files and return them as DataFrames."""
    import rdata  # reads R data files; listed in requirements.txt

    CACHE.mkdir(parents=True, exist_ok=True)
    desc = get(f"{UNHCR_BASE}/DESCRIPTION", binary=True)
    version = "unknown"
    if desc:
        for line in desc.decode("utf-8", "replace").splitlines():
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
    frames = {}
    for name in UNHCR_FILES:
        path = CACHE / f"{name}.rda"
        blob = get(f"{UNHCR_BASE}/data/{name}.rda", binary=True)
        if blob:
            path.write_bytes(blob)
        elif not path.exists():
            sys.exit(f"Could not download UNHCR file {name}.rda and no cached copy exists.")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            frames[name] = pd.DataFrame(list(rdata.read_rda(path).values())[0])
        frames[name]["year"] = frames[name]["year"].astype(int)
    return frames, version


def build_unhcr(frames: dict[str, pd.DataFrame]) -> dict:
    pop, unrwa, idmc = frames["population"], frames["unrwa"], frames["idmc"]
    pop = pop[pop["year"] >= FIRST_YEAR].copy()
    for col in ("refugees", "asylum_seekers", "oip"):
        pop[col] = pop[col].fillna(0)
    pop["refugees_oip"] = pop["refugees"] + pop["oip"]

    g = pop.groupby("year")[["refugees", "asylum_seekers", "oip"]].sum()
    g["unrwa"] = unrwa.groupby("year")["total"].sum()
    g["idps"] = idmc.groupby("year")["total"].sum()
    g = g.loc[FIRST_YEAR:].fillna(0)
    g["total"] = g[["refugees", "unrwa", "oip", "asylum_seekers", "idps"]].sum(axis=1)
    years = [int(y) for y in g.index]
    latest = years[-1]

    displacement = {"years": years, **{c: [round(v) for v in g[c]] for c in
                    ("refugees", "unrwa", "oip", "asylum_seekers", "idps", "total")}}

    us = pop[pop["coa_iso"] == "USA"].groupby("year")[["refugees_oip", "asylum_seekers"]].sum().reindex(years).fillna(0)
    us_hosting = {"years": years, "refugees_oip": [round(v) for v in us["refugees_oip"]],
                  "asylum_seekers": [round(v) for v in us["asylum_seekers"]]}

    host = (pop[pop["year"] == latest].groupby(["coa_iso", "coa_name"])[["refugees_oip", "asylum_seekers"]]
            .sum().reset_index())
    def rows(col: str, n: int) -> list[dict]:
        top = host.sort_values(col, ascending=False)
        rank = {iso: i + 1 for i, iso in enumerate(top["coa_iso"])}
        keep = top.head(n)
        if "USA" not in set(keep["coa_iso"]):
            keep = pd.concat([keep, top[top["coa_iso"] == "USA"]])
        return [{"iso": r.coa_iso, "name": SHORT_NAMES.get(r.coa_name, r.coa_name), "value": round(getattr(r, col)), "rank": rank[r.coa_iso]}
                for r in keep.itertuples(index=False)]

    return {
        "displacement": displacement,
        "us_hosting": us_hosting,
        "top_refugee_hosts": {"year": latest, "rows": rows("refugees_oip", 10)},
        "top_asylum_hosts": {"year": latest, "rows": rows("asylum_seekers", 10)},
        "_host_panel": pop[["year", "coa_iso", "refugees_oip", "asylum_seekers"]],
    }


def partial_year(version: str, latest: int) -> dict | None:
    """UNHCR's June releases (version YYYY.6.x) add mid-year figures for the current year:
    stocks as of June 30 and flows (such as asylum applications) for January to June."""
    try:
        y, m = (int(x) for x in version.split(".")[:2])
    except ValueError:
        return None
    return {"year": latest, "months": 6, "label": f"mid-{latest}"} if m == 6 and y == latest else None


def build_asylum(apps: pd.DataFrame, full_year: int) -> dict:
    """New asylum applications worldwide and in the US, by calendar year.

    Only first-time applications (app_type "N") are counted, so appeals and repeat claims are
    left out. UNHCR counts persons for most countries, including the US, so one USCIS form I-589
    (which can cover a spouse and children) may stand for more than one person here.
    US claims are split by where they were filed: "IN" = USCIS, "EO" = immigration court (EOIR).
    """
    a = apps[(apps["app_type"] == "N") & (apps["year"] >= 2006)].copy()
    a["applied"] = a["applied"].fillna(0)
    world = a.groupby("year")["applied"].sum()
    us = a[a["coa_iso"] == "USA"]
    lvl = us.pivot_table(index="year", columns="dec_level", values="applied", aggfunc="sum").reindex(world.index).fillna(0)
    years = [int(y) for y in world.index]
    col = lambda c: [round(v) for v in (lvl[c] if c in lvl else pd.Series(0, index=world.index))]
    latest = full_year   # the country ranking uses the latest full calendar year
    by_country = a[a["year"] == latest].groupby(["coa_iso", "coa_name"])["applied"].sum().reset_index()
    top = by_country.sort_values("applied", ascending=False)
    rank = {iso: i + 1 for i, iso in enumerate(top["coa_iso"])}
    keep = top.head(10)
    if "USA" not in set(keep["coa_iso"]):
        keep = pd.concat([keep, top[top["coa_iso"] == "USA"]])
    return {
        "years": years,
        "world": [round(v) for v in world],
        "us": [round(v) for v in us.groupby("year")["applied"].sum().reindex(world.index).fillna(0)],
        "us_uscis": col("IN"),
        "us_court": col("EO"),
        "top": {"year": latest, "rows": [{"iso": r.coa_iso, "name": SHORT_NAMES.get(r.coa_name, r.coa_name),
                                          "value": round(r.applied), "rank": rank[r.coa_iso]}
                                         for r in keep.itertuples(index=False)]},
    }


def build_origins(frames: dict[str, pd.DataFrame]) -> dict:
    """Main countries of origin of US asylum claims, with displacement from each country.

    Origins are the N_ORIGINS countries with the most new US claims from 2022 to the latest year,
    leaving out claims with unknown origin or from stateless people.
    """
    apps = frames["asylum_applications"]
    a = apps[(apps["app_type"] == "N") & (apps["year"] >= 2013)].copy()
    a["applied"] = a["applied"].fillna(0)
    years = sorted(int(y) for y in a["year"].unique())
    us = a[a["coa_iso"] == "USA"]
    unknown = us["coo_iso"].isin(["UNK", "XXA"])
    recent = us[(us["year"] >= 2022) & ~unknown].groupby(["coo_iso", "coo_name"])["applied"].sum()
    top = recent.sort_values(ascending=False).head(N_ORIGINS)
    isos = [i for i, _ in top.index]

    def by_year(frame: pd.DataFrame, col: str = "applied") -> list:
        return [round(v) for v in frame.groupby("year")[col].sum().reindex(years).fillna(0)]

    pop = frames["population"]
    pop = pop[pop["year"] >= 2013].copy()
    for col in ("refugees", "asylum_seekers", "oip"):
        pop[col] = pop[col].fillna(0)
    pop["abroad"] = pop["refugees"] + pop["asylum_seekers"] + pop["oip"]
    idmc = frames["idmc"]

    countries = []
    for iso, name in top.index:
        countries.append({
            "iso": iso, "name": SHORT_NAMES.get(name, name),
            "us_claims": by_year(us[us["coo_iso"] == iso]),
            "world_claims": by_year(a[a["coo_iso"] == iso]),
            "displaced_abroad": by_year(pop[pop["coo_iso"] == iso], "abroad"),
            "idps": by_year(idmc[(idmc["coo_iso"] == iso) & (idmc["year"] >= 2013)], "total"),
        })
    return {
        "years": years,
        "us_total": by_year(us),
        "us_unknown": by_year(us[unknown]),
        "countries": countries,
        "conditions": {},
        "sources": {"world_bank": False, "ucdp": None},
        "_isos": isos,
    }


def build_ucdp(isos: list[str], years: list[int]) -> tuple[dict, str | None]:
    """Deaths in organized violence (state-based + non-state + one-sided), best estimates."""
    for url in UCDP_URLS:
        blob = get(url, binary=True, tries=2)
        if not blob:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                df = pd.read_csv(z.open(name))
        except (zipfile.BadZipFile, StopIteration, ValueError) as err:
            print(f"  ! could not read {url}: {err}", file=sys.stderr)
            continue
        cols = ["sb_total_deaths_best_cy", "ns_total_deaths_best_cy", "os_total_deaths_best_cy"]
        if not all(c in df.columns for c in cols + ["country_id_cy", "year_cy"]):
            print(f"  ! unexpected columns in {url}", file=sys.stderr)
            continue
        df["iso"] = df["country_id_cy"].map(GW_ISO)
        df["deaths"] = df[cols].fillna(0).sum(axis=1)
        version = url.split("-")[-2]
        out = {}
        for iso in isos:
            s = df[df["iso"] == iso].groupby("year_cy")["deaths"].sum()
            # UCDP lists every country-year (0 = no recorded deaths); years after its coverage stay empty
            out[iso] = [None if y not in s.index else int(s[y]) for y in years]
        return out, f"{version[:2]}.{version[2:]}"
    return {}, None


ORIGIN_INDICATORS = {   # key: (World Bank code, source id)
    "homicide": ("VC.IHR.PSRC.P5", 2),        # intentional homicides per 100,000 people
    "gdp_pc": ("NY.GDP.PCAP.KD", 2),          # GDP per person, constant 2015 US$
    "inflation": ("FP.CPI.TOTL.ZG", 2),       # consumer price inflation, % a year
    "stability": ("PV.EST", 3),               # political stability and absence of violence, -2.5 to 2.5
}


def build_origin_conditions(isos: list[str], years: list[int]) -> dict:
    out: dict = {iso: {} for iso in isos}
    for key, (code, source) in ORIGIN_INDICATORS.items():
        df = wb_series(code, isos, source, datetime.now().year)
        for iso in isos:
            s = df[df["iso"] == iso].set_index("year")["value"]
            out[iso][key] = [None if y not in s.index or pd.isna(s[y]) else round(float(s[y]), 2) for y in years]
    return out


# --------------------------------------------------------------------------------------
# World Bank
# --------------------------------------------------------------------------------------

def wb_series(code: str, countries: list[str], source: int, end: int) -> pd.DataFrame:
    payload = get(f"{WB_API}/country/{';'.join(countries)}/indicator/{code}",
                  {"format": "json", "date": f"{FIRST_YEAR}:{end}", "per_page": 20000, "source": source})
    if not payload or len(payload) < 2 or not payload[1]:
        return pd.DataFrame(columns=["iso", "year", "value"])
    df = pd.DataFrame({"iso": r["countryiso3code"] or WB_ID_ISO3.get(r["country"]["id"], r["country"]["id"]),
                       "year": int(r["date"]), "value": r["value"]} for r in payload[1]).dropna(subset=["value"])
    # Some aggregates (such as high income) can be dropped from a multi-country request: ask for each
    # missing one on its own, by its 3-letter code and then its 2-letter World Bank id.
    alias = {v: k for k, v in WB_ID_ISO3.items()}
    if len(countries) > 1 and countries != ["all"]:
        for iso in [c for c in countries if c not in set(df["iso"])]:
            for code_try in (iso, alias.get(iso)):
                if not code_try:
                    continue
                one = wb_series(code, [code_try], source, end)
                if not one.empty:
                    df = pd.concat([df, one.assign(iso=iso)], ignore_index=True)
                    break
            else:
                print(f"  ! World Bank {code} (source {source}): no data for {iso}", file=sys.stderr)
    return df


def wb_with_projections(code: str) -> tuple[pd.DataFrame, str]:
    """Try the Population estimates and projections database (to 2050), then WDI history only."""
    df = wb_series(code, list(AGGREGATES), 40, PROJECTION_END)
    if not df.empty:
        missing = [iso for iso in AGGREGATES if iso not in set(df["iso"])]
        if missing:   # fill any group the projections database lacks with WDI history
            print(f"  ! {code}: no projections for {', '.join(missing)}; using WDI history for them", file=sys.stderr)
            df = pd.concat([df, wb_series(code, missing, 2, datetime.now().year)], ignore_index=True)
        return df, "Population estimates and projections"
    return wb_series(code, list(AGGREGATES), 2, datetime.now().year), "World Development Indicators"


def build_world_bank(host_panel: pd.DataFrame) -> dict | None:
    meta = get(f"{WB_API}/country", {"format": "json", "per_page": 400})
    if not meta or len(meta) < 2:
        return None
    income = {c["id"]: c["incomeLevel"]["id"] for c in meta[1] if c["region"]["id"] != "NA"}
    names = {c["id"]: c["name"] for c in meta[1]}
    out: dict = {}

    # Who hosts: share of refugees (and of asylum-seekers) in high-income countries
    hp = host_panel.copy()
    hp["group"] = hp["coa_iso"].map(lambda i: "HIC" if income.get(i) == "HIC" else ("LMY" if income.get(i) in ("LIC", "LMC", "UMC") else "Other"))
    shares = {}
    for col in ("refugees_oip", "asylum_seekers"):
        t = hp.groupby(["year", "group"])[col].sum().unstack(fill_value=0)
        known = t.get("HIC", 0) + t.get("LMY", 0)
        shares[col] = [round(float(v), 4) for v in (t.get("HIC", 0) / known.where(known > 0))]
    out["income_share"] = {"years": [int(y) for y in t.index], **shares,
                           "note": "Share of hosts with a World Bank income group; current classification applied to all years."}

    # Hosting per 1,000 residents, latest year with population
    popn = wb_series("SP.POP.TOTL", ["all"], 2, datetime.now().year)
    if not popn.empty:
        latest_host = int(hp["year"].max())
        p = popn[popn["year"] <= latest_host].sort_values("year").groupby("iso").tail(1).set_index("iso")["value"]
        h = hp[hp["year"] == latest_host].groupby("coa_iso")["refugees_oip"].sum()
        per = (h / p.reindex(h.index) * 1000).dropna()
        per = per[(p.reindex(per.index) >= 1_000_000) & (h.reindex(per.index) > 0)]   # skip micro-states
        top = per.sort_values(ascending=False)
        rank = {iso: i + 1 for i, iso in enumerate(top.index)}
        keep = list(top.head(10).index) + (["USA"] if "USA" in top.index and "USA" not in top.head(10).index else [])
        out["per_capita"] = {"year": latest_host, "rows": [
            {"iso": i, "name": names.get(i, i), "per1000": round(float(top[i]), 1), "rank": rank[i],
             "high_income": income.get(i) == "HIC"} for i in keep], "ranked": len(top)}

    # Demography with projections
    demo, used = {}, {}
    for key, code in (("old_age_dependency", "SP.POP.DPND.OL"), ("fertility", "SP.DYN.TFRT.IN"),
                      ("working_age_share", "SP.POP.1564.TO.ZS")):
        df, src = wb_with_projections(code)
        if df.empty:
            continue
        used[key] = {"code": code, "source": src}
        piv = df.pivot_table(index="year", columns="iso", values="value")
        demo[key] = {"years": [int(y) for y in piv.index],
                     **{iso: [None if pd.isna(v) else round(float(v), 2) for v in piv.get(iso, pd.Series(index=piv.index))]
                        for iso in AGGREGATES}}
    if demo:
        out["demography"] = {"series": demo, "sources": used, "names": AGGREGATES,
                             "projection_from": datetime.now().year - 1}

    # Migration
    mig = {}
    for key, code in (("net_migration", "SM.POP.NETM"), ("migrant_stock_pct", "SM.POP.TOTL.ZS")):
        df = wb_series(code, list(AGGREGATES), 2, datetime.now().year)
        if df.empty:
            continue
        piv = df.pivot_table(index="year", columns="iso", values="value")
        mig[key] = {"years": [int(y) for y in piv.index],
                    **{iso: [None if pd.isna(v) else round(float(v), 2) for v in piv.get(iso, pd.Series(index=piv.index))]
                       for iso in AGGREGATES}}
    if mig:
        out["migration"] = mig
    return out


def main() -> None:
    frames, version = unhcr_frames()
    unhcr = build_unhcr(frames)
    host_panel = unhcr.pop("_host_panel")
    partial = partial_year(version, unhcr["displacement"]["years"][-1])
    full_year = unhcr["displacement"]["years"][-1] - (1 if partial else 0)
    unhcr["asylum_applications"] = build_asylum(frames["asylum_applications"], full_year)
    origins = build_origins(frames)
    isos = origins.pop("_isos")
    deaths, ucdp_version = build_ucdp(isos, origins["years"])
    for iso in isos:
        origins["conditions"][iso] = {"conflict_deaths": deaths.get(iso)}
    origins["sources"]["ucdp"] = ucdp_version
    print(f"  Main US asylum origins       {', '.join(c['name'] for c in origins['countries'])}")
    print(f"  UCDP organized violence      {'version ' + ucdp_version if ucdp_version else 'not available'}")
    d = unhcr["displacement"]
    aa = unhcr["asylum_applications"]
    print(f"  UNHCR (package {version})  {d['years'][0]}–{d['years'][-1]}, "
          f"{d['total'][-1] / 1e6:.1f} million forcibly displaced in {d['years'][-1]} (sum of components)")
    fi = aa["years"].index(full_year)
    print(f"  UNHCR asylum applications    {aa['years'][0]}–{aa['years'][-1]}, {aa['world'][fi] / 1e6:.2f} million new claims "
          f"worldwide in {full_year}, {aa['us'][fi] / aa['world'][fi]:.0%} in the US"
          + (f"; {partial['label']} figures cover January–June" if partial else ""))

    wb = build_world_bank(host_panel)
    if wb is None:
        print("  ! World Bank API unavailable: the dashboard will mark those charts as not loaded", file=sys.stderr)
    else:
        print(f"  World Bank                   {', '.join(wb)}")
        cond = build_origin_conditions(isos, origins["years"])
        for iso in isos:
            origins["conditions"][iso].update(cond[iso])
        origins["sources"]["world_bank"] = True
    unhcr["origins"] = origins

    out = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "unhcr": {"source": "UNHCR Refugee Population Statistics Database, via UNHCR's refugees data package",
                      "version": version, "url": "https://www.unhcr.org/refugee-statistics/",
                      "latest_year": d["years"][-1], "partial": partial, "latest_full_year": full_year},
            "world_bank": {"included": wb is not None,
                           "source": "World Bank, World Development Indicators and Population estimates and projections "
                                     "(net migration from UN World Population Prospects; migrant stock from UN DESA)",
                           "url": "https://data.worldbank.org"},
        },
        **unhcr,
        **(wb or {}),
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Long CSV of the displacement series, for analysis outside the dashboard
    disp = pd.DataFrame(d).melt(id_vars="years", var_name="series").assign(dataset="displacement")
    asy = pd.DataFrame({k: aa[k] for k in ("years", "world", "us", "us_uscis", "us_court")}).melt(
        id_vars="years", var_name="series").assign(dataset="new_asylum_applications")
    pd.concat([disp, asy]).rename(columns={"years": "year"})[["dataset", "series", "year", "value"]].to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_JSON.relative_to(ROOT)} ({OUT_JSON.stat().st_size / 1024:.0f} KB) and {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
