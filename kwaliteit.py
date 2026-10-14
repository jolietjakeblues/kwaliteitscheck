"""Datakwaliteitschecks voor CHO-KENNIS (RCE Linked Data Voorziening).

Draait alle checks in checks/*.rq tegen het TriplyDB SPARQL-endpoint en
schrijft per run een regel per check naar data/historie.csv. Daarnaast wordt
de graph-metadata (aantal triples, importdatum) vastgelegd in
data/graphs_historie.csv.

Gebruik:
    python kwaliteit.py              # alle checks
    python kwaliteit.py 01 05        # alleen checks waarvan de id zo begint
"""

from __future__ import annotations

import csv
import importlib.util
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ENDPOINT = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/sparql"
GRAPHS_API = "https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/graphs"
TIMEOUT_S = 300

ROOT = Path(__file__).parent
CHECKS_DIR = ROOT / "checks"
DATA_DIR = ROOT / "data"
HISTORIE = DATA_DIR / "historie.csv"
GRAPHS_HISTORIE = DATA_DIR / "graphs_historie.csv"

# Prefixes en vaste URI's die in elke check beschikbaar zijn. In de .rq-bestanden
# staan placeholders als {G_INSTANTIES} zodat graph-URI's op één plek staan.
PREFIXES = """\
PREFIX ceo: <https://linkeddata.cultureelerfgoed.nl/def/ceo#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX tooi: <https://identifier.overheid.nl/tooi/def/ont/>
"""

PLACEHOLDERS = {
    # Hoofdgraph: actuele, levende instantiedata (~92% van alle triples)
    "G_INSTANTIES": "<https://linkeddata.cultureelerfgoed.nl/graph/instanties-rce>",
    # Naslaggraph: wordt niet zelf gecontroleerd, alleen gebruikt om gemeenteverwijzingen
    # te toetsen (TOOI kent owmsId + einddatum, dus ook opgeheven gemeenten)
    "G_TOOI": "<https://linkeddata.cultureelerfgoed.nl/rce/tooi/graph/gemeenten>",
    # Juridische status (geverifieerde concept-URI's, zie MCP topic legal_status)
    "JS_RIJKSMONUMENT": "<https://data.cultureelerfgoed.nl/term/id/rn/2/b2d9a59a-fe1e-4552-9a05-3c2acddff864>",
    "JS_VOORBESCHERMD": "<https://data.cultureelerfgoed.nl/term/id/rn/2/2e93edd1-098f-4f31-ae7e-72cb77f4d2ca>",
    "JS_GEEN_RM": "<https://data.cultureelerfgoed.nl/term/id/rn/2/3e79bb7c-b459-4998-a9ed-78d91d069227>",
}

HISTORIE_VELDEN = [
    "run", "id", "titel", "dimensie", "populatie", "fout", "totaal",
    "pct_fout", "duur_s", "status", "melding",
]


def vul_in(query: str) -> str:
    for naam, waarde in PLACEHOLDERS.items():
        query = query.replace("{" + naam + "}", waarde)
    return PREFIXES + query


def lees_check(pad: Path) -> dict:
    """Lees een check.

    .rq: '# sleutel: waarde'-regels bovenaan zijn metadata; de query levert één
         rij met ?fout en ?totaal.
    .py: module met een META-dict en run(sparql) -> (fout, totaal). Voor checks
         die op het endpoint te zwaar zijn en beter lokaal kunnen joinen.
    """
    meta = {"id": pad.stem}
    if pad.suffix == ".py":
        spec = importlib.util.spec_from_file_location(f"check_{pad.stem}", pad)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        meta.update(module.META)
        meta["run"] = module.run
        return meta
    tekst = pad.read_text(encoding="utf-8")
    for regel in tekst.splitlines():
        m = re.match(r"#\s*(\w+)\s*:\s*(.+)", regel)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
        elif regel.strip() and not regel.startswith("#"):
            break
    meta["query"] = vul_in(tekst)
    return meta


def alle_checks(filters: list[str] | None = None) -> list[dict]:
    paden = sorted(list(CHECKS_DIR.glob("*.rq")) + list(CHECKS_DIR.glob("*.py")))
    checks = [lees_check(p) for p in paden]
    if filters:
        checks = [c for c in checks if any(c["id"].startswith(f) for f in filters)]
    return checks


def sparql(query: str) -> list[dict]:
    """Voer een query uit. Placeholders en prefixes worden aangevuld als ze ontbreken."""
    if "{G_" in query or "{JS_" in query or "PREFIX ceo:" not in query:
        query = vul_in(query)
    r = requests.post(
        ENDPOINT,
        data=query.encode("utf-8"),
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
        timeout=TIMEOUT_S,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return [
        {k: v["value"] for k, v in b.items()}
        for b in r.json()["results"]["bindings"]
    ]


def draai_check(check: dict) -> dict:
    """Een check levert precies één rij met ?fout en ?totaal."""
    start = time.time()
    uitkomst = {k: check.get(k, "") for k in ("id", "titel", "dimensie", "populatie")}
    try:
        if "run" in check:
            fout, totaal = check["run"](sparql)
        else:
            rij = sparql(check["query"])[0]
            fout, totaal = rij["fout"], rij["totaal"]
        fout, totaal = int(fout), int(totaal)
        uitkomst.update(
            fout=fout,
            totaal=totaal,
            pct_fout=round(100 * fout / totaal, 3) if totaal else 0.0,
            status="ok",
            melding="",
        )
    except Exception as e:  # noqa: BLE001 - een falende check mag de run niet stoppen
        uitkomst.update(fout="", totaal="", pct_fout="", status="fout", melding=str(e)[:300])
    uitkomst["duur_s"] = round(time.time() - start, 1)
    return uitkomst


def leg_graphs_vast(run: str) -> None:
    graphs = requests.get(GRAPHS_API, timeout=60).json()
    nieuw = not GRAPHS_HISTORIE.exists()
    with GRAPHS_HISTORIE.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nieuw:
            w.writerow(["run", "graph", "triples", "geimporteerd"])
        for g in graphs:
            w.writerow([run, g["graphName"], g.get("numberOfStatements", ""), g.get("importedAt", "")])


def main(filters: list[str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    run = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks = alle_checks(filters)
    print(f"Run {run}: {len(checks)} checks tegen {ENDPOINT}")

    nieuw = not HISTORIE.exists()
    with HISTORIE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HISTORIE_VELDEN)
        if nieuw:
            w.writeheader()
        for check in checks:
            u = draai_check(check)
            u["run"] = run
            w.writerow(u)
            f.flush()
            if u["status"] == "ok":
                print(f"  {u['id']:<40} {u['fout']:>8,} / {u['totaal']:>9,}  ({u['pct_fout']}%)  {u['duur_s']}s")
            else:
                print(f"  {u['id']:<40} FOUT: {u['melding'][:80]}")

    if not filters:
        leg_graphs_vast(run)


if __name__ == "__main__":
    main(sys.argv[1:])
