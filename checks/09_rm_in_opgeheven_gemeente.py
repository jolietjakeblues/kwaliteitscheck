"""Rijksmonumenten gekoppeld aan een opgeheven gemeente.

Als lokale join in plaats van SPARQL: de join tussen instanties-rce en TOOI
(tooi:owmsId is een xsd:anyURI-literal) loopt op het endpoint tegen de
timeout aan. Twee kleine queries plus een join in pandas kost ~2 seconden.
"""

import pandas as pd

META = {
    "titel": "Rijksmonument gekoppeld aan opgeheven gemeente",
    "dimensie": "actualiteit",
    "populatie": "actieve rijksmonumenten met gemeente",
    "toelichting": "Gemeente die in TOOI alleen met een einddatum voorkomt (herindeling niet doorgevoerd).",
}

Q_RM = """SELECT ?m ?gm WHERE { GRAPH {G_INSTANTIES} {
  ?m ceo:heeftJuridischeStatus {JS_RIJKSMONUMENT} ; ceo:heeftBasisregistratieRelatie/ceo:heeftGemeente ?gm } }"""

Q_TOOI = """SELECT ?owms ?eind WHERE { GRAPH {G_TOOI} {
  ?t tooi:owmsId ?owms OPTIONAL { ?t tooi:einddatum ?eind } } }"""


def run(sparql):
    rm = pd.DataFrame(sparql(Q_RM))
    tooi = pd.DataFrame(sparql(Q_TOOI))
    if "eind" not in tooi:
        tooi["eind"] = None
    # Een owmsId kan bij meerdere TOOI-records horen; opgeheven = geen enkel record zonder einddatum
    actueel = tooi.groupby("owms")["eind"].apply(lambda s: s.isna().any())
    opgeheven = set(actueel[~actueel].index)
    fout = rm[rm["gm"].isin(opgeheven)]["m"].nunique()
    return fout, rm["m"].nunique()
