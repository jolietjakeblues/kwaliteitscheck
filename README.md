# Datakwaliteit CHO-KENNIS

Datakwaliteitschecks op de CHO-KENNIS-dataset van de RCE Linked Data Voorziening, met een Jupyter-dashboard dat de uitkomsten over tijd toont.

## Gebruik

```bash
pip install -r requirements.txt
python kwaliteit.py                 # alle checks, voegt een run toe aan data/historie.csv
python kwaliteit.py 09 13           # alleen checks waarvan de id zo begint (geen graph-snapshot)
jupyter lab dashboard.ipynb         # dashboard bekijken
jupyter nbconvert --to html --execute --no-input dashboard.ipynb   # statische HTML om te delen
```

## Afbakening

- **Endpoint:** `https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/sparql` (TriplyDB, niet de Virtuoso-service).
- **Gecontroleerd:** alleen de hoofdgraph `graph/instanties-rce`, met ~92% van alle triples. Elke query beperkt zich expliciet met `GRAPH`, want zonder die beperking tellen objecten dubbel: het type `ceo:Rijksmonument` staat ook in `punten`, `image`, `image-1` en `groenaanleg`.
- **Naslag:** TOOI-gemeenten, alleen om gemeenteverwijzingen te toetsen.
- **Graphoverstijgend:** één check (20) zoekt rijksmonumenten die alleen in een bijgraph staan.
- **Actieve rijksmonumenten** = `ceo:heeftJuridischeStatus` *rijksmonument*. De klasse `ceo:Rijksmonument` bevat ook objecten met de status *voorbeschermd* of *geen rijksmonument*.

## Een check toevoegen

**SPARQL** (`checks/NN_naam.rq`): metadata als commentaar bovenaan, en de query levert één rij met `?fout` en `?totaal`.

```sparql
# titel: Rijksmonument zonder geometrie
# dimensie: volledigheid
# populatie: actieve rijksmonumenten
SELECT (SUM(?f) AS ?fout) (COUNT(?m) AS ?totaal) WHERE {
  GRAPH {G_INSTANTIES} { ?m ceo:heeftJuridischeStatus {JS_RIJKSMONUMENT} }
  BIND(IF(EXISTS { GRAPH {G_INSTANTIES} { ?m ceo:heeftGeometrie ?g } }, 0, 1) AS ?f)
}
```

Placeholders zoals `{G_INSTANTIES}` en `{JS_RIJKSMONUMENT}`, en de prefixes, staan centraal in `kwaliteit.py`.

**Python** (`checks/NN_naam.py`): voor checks die op het endpoint te zwaar zijn. Definieer `META` en `run(sparql) -> (fout, totaal)`. Zie `09_rm_in_opgeheven_gemeente.py`.

## Valkuilen van dit endpoint (opgedaan bij het bouwen)

- Het endpoint breekt queries na ~60 seconden af. `EXISTS` per node over ~900.000 dateringen is te zwaar; tel in dat geval verschillen tussen twee `COUNT`s (zie 15 en 15b).
- `tooi:owmsId` is een `xsd:anyURI`-literal, geen IRI. Een join met `ceo:heeftGemeente` vraagt `STRDT(STR(?gm), xsd:anyURI)`.
- `FILTER` op een buitenvariabele binnen `EXISTS` matcht op dit endpoint niet betrouwbaar. Bind de waarde vooraf en gebruik die in het triple-patroon.
- Een join tussen instanties-rce en TOOI over 63.000 monumenten loopt op een timeout. Twee kleine queries plus een lokale join kosten ~2 seconden.
- Identieke queries komen uit de cache. Een tweede run op dezelfde dag is daardoor bijna gratis.
