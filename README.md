# corridor-canary 🐦

corridor-canary is a lightweight monitoring utility that watches the National Center for Missing & Exploited Children (NCMEC) public RSS feed and surfaces new missing-child alerts originating along a defined geographic corridor. Built for OSINT analysts, volunteer investigators, journalists, and researchers focused on trafficking patterns along major U.S. transit routes, it filters incoming alerts against a configurable watchlist of cities and delivers a single, deduplicated push notification per match via ntfy. The default configuration covers the southern segment of the U.S. Route 1 corridor — from the Maryland/Pennsylvania border through Key West — a region with documented relevance to interstate trafficking activity. The utility is platform-agnostic and can run anywhere Python and cron-style scheduling are available: a home server, small cloud VM, NAS, or a containerized environment.

## What it does

- Polls NCMEC's XML servlet RSS feed (`/missingkids/servlet/XmlServlet?act=rss&LanguageCountry=en_US&orgPrefix=NCMC`) every 20 minutes.
- Matches entries whose location is a US-1 corridor city from Maryland through Key West.
- Matching requires "City, State" to co-occur, so `Columbia, MD` won't hit a `Columbia, SC` watch.
- Dedupes by feed GUID — each alert fires once.
- First run seeds silently (no backlog flood).
- Publishes to a private ntfy.sh topic (free tier, no token). Silent — no voice, no audible alert beyond the ntfy push.

## Why this is OK to run

NCMEC publishes the RSS feed publicly and explicitly for redistribution. This script hits it on a 20-minute interval with an identifying User-Agent, respects HTTP errors, and only fans one notification to one device.

## Analytical use

Once alerts are captured, the downstream value is analytical rather than reactive. Timestamped, geolocated alert data accumulated over weeks and months allows analysts to identify clustering around specific exits, municipalities, and transit nodes; correlate missing-child reports with known trafficking indicators such as truck stops, budget lodging, bus terminals, and event venues; and build temporal baselines that make anomalous spikes visible. Cross-referenced with open-source datasets — court records, licensing boards, zoning data, social media, and existing NGO reporting — the corridor view supports pattern-of-life analysis, tip development for law enforcement partners, briefings for community stakeholders, and longitudinal reporting that individual case-by-case awareness cannot produce. In short, corridor-canary is not a response tool; it is the ingestion layer for a regional intelligence picture.

## Quick start

See `SETUP.md` for the full walkthrough. In brief:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

mkdir -p ~/.config/corridor-canary
cp env.example ~/.config/corridor-canary/env
chmod 600 ~/.config/corridor-canary/env
$EDITOR ~/.config/corridor-canary/env    # fill in NTFY_TOPIC

# Verify ntfy works
set -a; . ~/.config/corridor-canary/env; set +a
.venv/bin/python corridor-canary.py --test
```

Timer/service units are in `SETUP.md` (system-level systemd).

## Editing the watchlist

Open `watchlist.py`. Add or remove `(city, state_postal)` tuples. No restart needed — each timer fire re-imports.

## Files

| Path | What |
|---|---|
| `corridor-canary.py` | Main script |
| `watchlist.py` | Cities to alert on |
| `env.example` | Env template (never commit the real one) |
| `requirements.txt` | Python deps |
| `SETUP.md` | Pi install walkthrough (includes systemd units) |

## Ops notes

- State file lives at `~/.local/state/corridor-canary/seen.json`.
- Logs: `sudo journalctl -u corridor-canary.service -f` (system-level install).
- `corridor-canary.py --test` sends a dummy push to verify ntfy.
- `corridor-canary.py --dry-run` runs the matcher but pushes nothing and doesn't update state.
- `corridor-canary.py --reseed` wipes seen-state so the next run behaves as first-run (silent seed).
- Don't lower the poll interval below 10 minutes. Be a good citizen.

## Ethical Notice & Attribution

### Legal & Ethical Notice

"All data collected by this tool is publicly posted information. This project is intended strictly for anti-human trafficking research and to support law enforcement referrals. Do not use this tool for any other purpose."

### Author Credit

Designed by [@ohgollybritta](https://github.com/ohgollybritta)

OSINT analyst — anti-human trafficking / ICAC research
