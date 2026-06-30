# Kristiansand Eventguide

Gratis statisk eventguide som kan publiseres på GitHub Pages og oppdateres daglig med GitHub Actions.

## Slik bruker du den

1. Lag et public repository på GitHub, f.eks. `kristiansand-eventguide`.
2. Last opp alle filene i denne mappen.
3. Gå til **Settings → Pages**.
4. Velg **Deploy from a branch**, branch `main`, folder `/root`.
5. Gå til **Actions → Daily event update → Run workflow** for å teste.
6. Åpne Pages-URL-en når GitHub er ferdig med å publisere.

## Filer

- `index.html` viser guiden.
- `events.json` er eventdata.
- `sources.json` er kilderegisteret.
- `scripts/update_events.py` lager ny `events.json`.
- `.github/workflows/daily-update.yml` kjører scriptet daglig.

## Viktig

Første parser er konservativ. Den finner mulige eventer fra åpne HTML-sider, men må bygges ut kilde-for-kilde for høy kvalitet. Sosiale medier behandles som signalkilder, ikke komplett automatisk datakilde.

## Datastatus

`events.json` kan inneholde udaterte startoppføringer fra sentrale kilder når scraperen ikke finner trygge, daterte eventer. De er ikke ment som faktiske eventer på bestemte dager. Neste forbedring er egne parser-funksjoner for prioriterte offentlige kilder som Kultur i kveld, Kilden, Kunstsilo, Kvadraturen og Visit Sørlandet.

## Parsere

`scripts/update_events.py` har parser for Kultur i kveld, Kvadraturen sitt kalender-API og generelle Schema.org Event-data fra offentlige kilder som Ticketmaster og Songkick. Nye kilder legges til som egne `parse_*`-funksjoner og registreres i `parsers` i `main()`. Parsere bør bare returnere eventer med tittel, dato og kilde-URL. Generisk scraping er opt-in per kilde med `generic_scrape: true`.

Noen registrerte kilder mangler åpne strukturerte eventdata, blokkerer enkel serverhenting, eller krever egne API-/HTML-parsere. De står fortsatt i `sources.json`, men returnerer trygt null eventer til en egen parser er lagt inn.
