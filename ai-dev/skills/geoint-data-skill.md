# GEOINT Data Skill — Echelon

Domain knowledge for working with Echelon's five open-data signal streams.

## ACLED
- API base: https://api.acleddata.com/acled/read
- Auth: key= and email= query params; pagination via limit/page
- Date filter: event_date_where=BETWEEN&event_date=YYYY-MM-DD|YYYY-MM-DD
- Geo: no native bbox — filter post-fetch by lat/lon range
- Rate limit: ~1 req/sec; Research tier higher
- Dedup key: data_id + event_date
- Attribution required: "Data from ACLED (acleddata.com)"

## GlobalFishingWatch
- API base: https://gateway.api.globalfishingwatch.org/v3
- Auth: Authorization: Bearer {token}
- Events: POST /events with JSON {datasets, geometry (GeoJSON Polygon), startDate, endDate, types}
- Rate limit: 1 concurrent report — Celery must serialize
- Data lag: ~24 hours
- Event types: gap, loitering, port_visit, encounter
- Dedup key: event id

## Element84 Earth Search (Sentinel-2)
- STAC URL: https://earth-search.aws.element84.com/v1
- Collection: sentinel-2-l2a
- Cloud filter: {"op":"<=","args":[{"property":"eo:cloud_cover"},20]}
- Bands for conflict: B08 (NIR), B11 (SWIR1) → NBR; B04+B08 → NDVI
- Asset keys: nir (B08), swir16 (B11), red (B04)
- COG reads: ALWAYS windowed reads scoped to AOI bbox — never load full scene

## GDELT
- Last update: http://data.gdeltproject.org/gdeltv2/lastupdate.txt
- Format: TSV, 61 columns, zipped, every 15 minutes
- Conflict CAMEO codes: 190-196 (fight/attack), 200-204 (conventional military force)
- Geo columns: Actor1Geo_Lat/Long, ActionGeo_Lat/Long
- No API key required
- Dedup key: GlobalEventID

## OSM Overpass
- URL: https://overpass-api.de/api/interpreter
- Tags: military=*, aeroway=aerodrome, aeroway=helipad, man_made=petroleum_well, landuse=military
- Rate: max 1 large bbox query per 60s
- Sample QL:
  [out:json][timeout:120];
  (node["military"](S,W,N,E); way["military"](S,W,N,E););
  out geom;

## H3 Resolution Reference
| Res | Avg Area   | Echelon Use         |
|-----|-----------|---------------------|
| 5   | ~252 km²  | Global (zoom < 5)   |
| 7   | ~5.2 km²  | Regional (zoom 5–9) |
| 9   | ~0.1 km²  | Tactical (zoom > 9) |
