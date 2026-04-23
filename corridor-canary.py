#!/usr/bin/env python3
"""
corridor-canary
Silent RSS watcher for NCMEC missing-child alerts along the southern US-1 corridor.
Pushes a single ntfy notification per new matching entry.

Config lives in environment variables (loaded by systemd EnvironmentFile or cron env).
Watchlist lives in watchlist.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

import feedparser
import requests

from watchlist import CITIES, STATE_FULL_NAMES

# ---- CONFIG (from env) ---------------------------------------------------

FEED_URL       = os.environ.get(
    "CANARY_FEED_URL",
    "https://www.missingkids.org/missingkids/servlet/XmlServlet?act=rss&LanguageCountry=en_US&orgPrefix=NCMC",
)
NTFY_SERVER    = os.environ.get("NTFY_SERVER",  "").rstrip("/")   # e.g. https://ntfy.yourdomain.tld
NTFY_TOPIC     = os.environ.get("NTFY_TOPIC",   "")               # e.g. canary-corridor
NTFY_TOKEN     = os.environ.get("NTFY_TOKEN",   "")               # bearer token for publish
NTFY_PRIORITY  = os.environ.get("NTFY_PRIORITY","default")
NTFY_TAGS      = os.environ.get("NTFY_TAGS",    "rotating_light,child")
USER_AGENT     = os.environ.get("CANARY_UA",    "corridor-canary/1.0 (OSINT volunteer; contact: you@example.com)")

STATE_FILE = Path(os.environ.get(
    "CANARY_STATE_FILE",
    str(Path.home() / ".local" / "state" / "corridor-canary" / "seen.json"),
))

REQUEST_TIMEOUT = 20
MAX_SEEN = 3000

# ---- LOGGING -------------------------------------------------------------

logging.basicConfig(
    level=os.environ.get("CANARY_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("canary")

# ---- MATCHING ------------------------------------------------------------

# Build regex patterns once at import. For each (city, ST) we match either
# "City, ST" or "City, FullStateName" with case-insensitive, flexible whitespace,
# and optional period after "St" etc. Word-boundary on the state side prevents
# "VA" from matching "Nevada" or "value".
def _build_patterns() -> list[tuple[re.Pattern, str, str]]:
    patterns = []
    for city, st in CITIES:
        # Allow "St." or "St" or "Saint" flexibility by just matching literally —
        # watchlist already lists both "St. Augustine" and "Saint Augustine".
        city_re = re.escape(city).replace(r"\ ", r"\s+")
        full = STATE_FULL_NAMES.get(st, st)
        full_re = re.escape(full).replace(r"\ ", r"\s+")
        # "City, ST" — ST may have periods like D.C.
        # We allow an optional period inside short abbrevs via a relaxed pattern.
        st_relaxed = r"\.?".join(re.escape(c) for c in st)
        p = re.compile(
            rf"{city_re}\s*,\s*(?:{st_relaxed}|{full_re})\b",
            re.IGNORECASE,
        )
        patterns.append((p, city, st))
    return patterns

COMPILED = _build_patterns()


def entry_haystack(entry) -> str:
    parts = [
        entry.get("title", "") or "",
        entry.get("summary", "") or "",
        entry.get("description", "") or "",
    ]
    for tag in entry.get("tags", []) or []:
        parts.append(tag.get("term", "") or "")
    # Feed descriptions are often HTML — strip tags cheaply.
    text = " ".join(parts)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def entry_match(entry) -> tuple[str, str] | None:
    hay = entry_haystack(entry)
    for pat, city, st in COMPILED:
        if pat.search(hay):
            return (city, st)
    return None

# ---- STATE FILE (dedup) --------------------------------------------------

def load_seen() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        return set(json.loads(STATE_FILE.read_text()))
    except Exception as e:
        log.warning("Couldn't read state file (%s); starting fresh.", e)
        return set()


def save_seen(seen: set[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = list(seen)[-MAX_SEEN:]
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trimmed))
    tmp.replace(STATE_FILE)  # atomic


def entry_id(entry) -> str:
    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title", "")
    )

# ---- NETWORK -------------------------------------------------------------

def fetch_feed():
    resp = requests.get(
        FEED_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def push_ntfy(title: str, body: str, click: str = "") -> None:
    if not (NTFY_SERVER and NTFY_TOPIC):
        raise RuntimeError("NTFY_SERVER and NTFY_TOPIC must be set in the environment.")
    # NTFY_TOKEN is optional — ntfy.sh free tier publishes without auth;
    # self-hosted/Pro can add Bearer below.

    def safe_header(s: str) -> str:
        return s.encode("ascii", "replace").decode("ascii")[:200]

    headers = {
        "Title":      safe_header(title),
        "Priority":   NTFY_PRIORITY,
        "Tags":       NTFY_TAGS,
        "User-Agent": USER_AGENT,
    }
    if click:
        headers["Click"] = click
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"

    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    r = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()


def build_push_body(entry, matched: tuple[str, str]) -> tuple[str, str, str]:
    city, st = matched
    title = entry.get("title", "Missing child alert")
    summary = entry.get("summary", "") or entry.get("description", "") or ""
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    link = entry.get("link", "")

    hit = f"[{city}, {st}] "
    body = hit + (summary[:1000] + "…" if len(summary) > 1000 else summary)
    if link:
        body = f"{body}\n\n{link}"
    return (f"{hit}{title}", body, link)

# ---- CLI -----------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="corridor-canary NCMEC watcher")
    parser.add_argument("--test", action="store_true",
                        help="Send a test push and exit (no feed fetched).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run normally but don't push or update state.")
    parser.add_argument("--reseed", action="store_true",
                        help="Wipe seen.json so the next run treats the feed as first-run.")
    args = parser.parse_args()

    if args.reseed:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            log.info("Removed %s", STATE_FILE)
        return 0

    if args.test:
        push_ntfy(
            "corridor-canary test",
            "If you got this, your ntfy config works. 🐦",
            click="",
        )
        log.info("Test push sent.")
        return 0

    seen = load_seen()
    first_run = len(seen) == 0

    try:
        parsed = fetch_feed()
    except Exception as e:
        log.error("Feed fetch failed: %s", e)
        return 1

    if parsed.bozo:
        log.warning("Feed parse warning: %s", parsed.bozo_exception)

    new_count = 0
    pushed = 0

    for entry in parsed.entries:
        eid = entry_id(entry)
        if not eid or eid in seen:
            continue

        seen.add(eid)
        new_count += 1

        match = entry_match(entry)
        if not match:
            continue

        if first_run:
            # Seed the dedupe store without flooding the phone on initial deploy.
            continue

        if args.dry_run:
            log.info("[dry-run] would push: %s [%s, %s]",
                     entry.get("title", "<no title>"), match[0], match[1])
            continue

        title, body, click = build_push_body(entry, match)
        try:
            push_ntfy(title, body, click)
            pushed += 1
            log.info("Pushed: %s [%s, %s]", entry.get("title", "<no title>"), match[0], match[1])
        except Exception as e:
            # On push failure, un-see so the next run retries this entry.
            seen.discard(eid)
            log.error("ntfy push failed: %s", e)

    if not args.dry_run:
        save_seen(seen)

    log.info("entries=%d new=%d pushed=%d first_run=%s dry_run=%s",
             len(parsed.entries), new_count, pushed, first_run, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
