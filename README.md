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

## Dagelijkse run (GitHub Actions)

Het dashboard staat op **https://jolietjakeblues.github.io/kwaliteitscheck/**. De workflow `.github/workflows/dagelijks.yml` draait elke dag om 05:30 UTC (07:30 zomertijd, 06:30 wintertijd): checks draaien, dashboard renderen, publiceren op GitHub Pages. Handmatig starten kan via *Actions → Dagelijkse kwaliteitscheck → Run workflow*.

De workflow commit niets. De historie staat in de gepubliceerde site (`/data/historie.csv` en `/data/graphs_historie.csv`). Elke run haalt die op, voegt een run toe en publiceert opnieuw. De CSV's in `data/` in de repo zijn alleen het startpunt voor de allereerste run.

Eenmalig instellen: *Settings → Pages → Build and deployment → Source: GitHub Actions*.

Let op: GitHub zet geplande workflows uit in een openbare repo zonder activiteit gedurende 60 dagen. Je krijgt daar vooraf een mail over, en één klik op *Enable workflow* zet hem weer aan.

## Lokale run (Windows-taak)

De Windows-taak **CHO-KENNIS kwaliteitscheck** start elke dag om 07:30 `dagelijks.cmd`. Dat is na de verversing van de dataset, rond 06:45. Staat de pc op dat moment uit, dan loopt de run zodra hij weer aan is. Het script draait de checks, rendert `dashboard.html` opnieuw en schrijft alle uitvoer naar `data/dagelijks.log`.

- Handmatig starten: `Start-ScheduledTask -TaskName 'CHO-KENNIS kwaliteitscheck'` of dubbelklik op `dagelijks.cmd`.
- Uitzetten: `Disable-ScheduledTask -TaskName 'CHO-KENNIS kwaliteitscheck'`.
- Verwijderen: `Unregister-ScheduledTask -TaskName 'CHO-KENNIS kwaliteitscheck'`.

## Afbakening

- **Endpoint:** `https://api.linkeddata.cultureelerfgoed.nl/datasets/rce/cho/sparql` (TriplyDB, niet de Virtuoso-service).
- **Gecontroleerd:** alleen de hoofdgraph `graph/instanties-rce`, met ~92% van alle triples. Elke query beperkt zich expliciet met `GRAPH`, want zonder die beperking tellen objecten dubbel: het type `ceo:Rijksmonument` staat ook in `punten`, `image`, `image-1` en `groenaanleg`.
- **Naslag:** OWMS, de waardelijst achter `ceo:heeftGemeente` en `ceo:heeftProvincie`, met types en `owms:endDate` voor opgeheven gemeenten. De dataset bevat OWMS twee keer (`koop/owms/graphs/default` en `graph/owms`). De checks toetsen tegen het KOOP-origineel, en check 23 bewaakt dat de kopieën gelijk blijven.
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

**Lijst** (`checks/NN_naam.lijst.rq`, optioneel): een SELECT die de objecten achter de bevindingen teruggeeft, zonder LIMIT, want de runner pagineert zelf. Na elke volledige run komt er per check met bevindingen een `data/lijsten/NN_naam.csv`. Heeft de lijst een kolom `rijksmonumentnummer`, dan komt er automatisch een link naar het monumentenregister bij. Het dashboard toont de eerste 25 rijen en linkt naar de CSV. Check 15b heeft (nog) geen lijst: de query loopt op ~55 seconden tegen de timeout aan.

Placeholders zoals `{G_INSTANTIES}` en `{JS_RIJKSMONUMENT}`, en de prefixes, staan centraal in `kwaliteit.py`.

**Python** (`checks/NN_naam.py`): voor checks die op het endpoint te zwaar zijn en beter lokaal kunnen joinen. Definieer `META` en `run(sparql) -> (fout, totaal)`.

Een selectie (`python kwaliteit.py 09 22`) toont alleen de uitkomst. Alleen volledige runs komen in de historie.

## Valkuilen van dit endpoint (opgedaan bij het bouwen)

- Het endpoint breekt queries na ~60 seconden af. `EXISTS` per node over ~900.000 dateringen is te zwaar; tel in dat geval verschillen tussen twee `COUNT`s (zie 15 en 15b).
- `FILTER` op een buitenvariabele binnen `EXISTS` matcht op dit endpoint niet betrouwbaar. Bind de waarde vooraf en gebruik die in het triple-patroon.
- Een join die vanaf de grote kant begint (63.000 monumenten → OWMS) loopt op een timeout. Begin met de kleine set (bv. opgeheven gemeenten) in een subquery en koppel dan (zie 09 en 22).
- Een eventuele TOOI-koppeling: `tooi:owmsId` is daar een `xsd:anyURI`-literal, geen IRI, dus join met `STRDT(STR(?gm), xsd:anyURI)`.
- Identieke queries komen uit de cache. Een tweede run op dezelfde dag is daardoor bijna gratis.
