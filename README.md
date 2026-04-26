# Danske nyheder til Home Assistant

En Home Assistant custom integration med et Lovelace-kort til et hurtigt overblik over dagens danske nyheder.

Integrationens backend henter nyheder server-side, filtrerer tydelige betalingsmur-artikler fra og gemmer korte overskrifter i `sensor.nyheder`. Lovelace-kortet viser dagens nyheder fra de udbydere, du har valgt i kortets UI-opsætning. Når du klikker på en overskrift, skifter kortet til en intern artikelvisning med tilbageknap i stedet for at navigere væk fra dashboardet.

## Funktioner

- Udbydervalg i kortets UI-opsætning: TV 2, DR, EB og B.T.
- Små udbyderlogoer på hver artikel.
- Gul breaking news-markering, når en artikel er markeret som breaking.
- Automatisk skalering af tekst og logoer efter dashboardbredden plus en `scale`-indstilling.
- Config flow i Home Assistant til valg af udbydere, antal artikler og opdateringsinterval.
- Server-side hentning, så kortet ikke rammer browserens CORS-begrænsninger.
- Korte overskrifter og resumeer i dashboardet.
- Intern artikelvisning via Home Assistant WebSocket API.
- Best-effort filtrering af artikler med betalingsmur. Integrationens mål er gratis artikler, ikke omgåelse af login eller abonnement.
- Bundlet Lovelace-resource på `/danish_news/danish-news-card.js`.

## Installer manuelt

1. Kopiér mappen `custom_components/danish_news` til din Home Assistant `config/custom_components/danish_news`.
2. Genstart Home Assistant.
3. Gå til **Indstillinger → Enheder og tjenester → Tilføj integration**.
4. Søg efter **Danske nyheder** og vælg udbydere.
5. Tilføj Lovelace-resource:

```yaml
url: /danish_news/danish-news-card.js
type: module
```

6. Tilføj kortet til dit dashboard:

```yaml
type: custom:danish-news-card
title: Dagens nyheder
providers:
  - tv2
  - dr
  - eb
  - bt
max_articles: 8
scale: 1
show_summaries: true
```

Kortet finder normalt `sensor.nyheder` automatisk. Hvis du har flere instanser, kan du vælge sensoren manuelt:

```yaml
type: custom:danish-news-card
entity: sensor.nyheder
```

## Build

```bash
npm run build
```

Build skriver kortet til både:

```text
dist/danish-news-card.js
custom_components/danish_news/www/danish-news-card.js
examples/danish-news-demo/danish-news-card.js
```

## Lokal demo

Der ligger en isoleret demo i:

```text
examples/danish-news-demo/
```

Den bruger mock-data og kan køres uden Home Assistant:

```bash
python3 -m http.server 4183 --directory examples/danish-news-demo
```

Åbn derefter `http://localhost:4183`.

## Nyhedskilder

Integrationens standardkilder er:

- TV 2: `https://services.tv2.dk/api/feeds/nyheder/rss`, med fallback til `https://nyheder.tv2.dk`
- DR: `https://www.dr.dk/nyheder/service/feeds/allenyheder`
- Ekstra Bladet: `https://ekstrabladet.dk/rssfeed/all/`
- B.T.: `https://www.bt.dk/bt/seneste/rss`

Nyhedssites kan ændre feeds, HTML og betalingsmurmarkører uden varsel. Derfor er filtrering og artikeludtræk best-effort.

## Kortkonfiguration

| Option | Type | Default | Beskrivelse |
| --- | --- | --- | --- |
| `title` | string | `Dagens nyheder` | Kortets titel. |
| `entity` | string | auto | Nyhedssensoren fra integrationen. |
| `providers` | list | `tv2`, `dr`, `eb`, `bt` | Udbydere kortet må vise. Vælges i kortets UI-opsætning. |
| `max_articles` | number | `8` | Maks. synlige overskrifter i kortet. |
| `scale` | number | `1` | Grundskalering fra `0.75` til `1.35`; kortet autoskalerer også med dashboardbredden. |
| `show_summaries` | boolean | `true` | Vis korte resumeer under overskrifter. |
| `show_source_link` | boolean | `false` | Vis et eksternt kildelink i artikelvisningen. |
| `compact` | boolean | `false` | Strammere layout. |

## Bemærkninger

Artikelvisningen henter kun offentligt tilgængeligt indhold og stopper, hvis siden tydeligt markerer artiklen som abonnementsindhold. Brug integrationen privat og respekter udgivernes vilkår.
