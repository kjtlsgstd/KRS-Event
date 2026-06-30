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
