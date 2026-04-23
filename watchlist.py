"""
corridor-canary watchlist
US-1 corridor, southern region (below the Mason-Dixon line).

Each tuple is (city, state_postal). The matcher requires BOTH to co-occur
in the "City, ST" pattern within a feed entry, so "Columbia, MD" won't
trigger the "Columbia, SC" watch.

Edit this file to add/remove cities. Restart isn't needed — cron/timer
re-imports on each run.
"""

CITIES: list[tuple[str, str]] = [
    # Maryland
    ("Baltimore",        "MD"),
    ("College Park",     "MD"),

    # District of Columbia — state field may appear as DC or D.C.
    ("Washington",       "DC"),

    # Virginia
    ("Alexandria",       "VA"),
    ("Arlington",        "VA"),
    ("Richmond",         "VA"),
    ("Fredericksburg",   "VA"),
    ("Petersburg",       "VA"),

    # North Carolina
    ("Raleigh",          "NC"),
    ("Henderson",        "NC"),
    ("Rockingham",       "NC"),
    ("Southern Pines",   "NC"),

    # South Carolina
    ("Columbia",         "SC"),
    ("Aiken",            "SC"),
    ("Cheraw",           "SC"),

    # Georgia
    ("Augusta",          "GA"),
    ("Jesup",            "GA"),
    ("Folkston",         "GA"),

    # Florida
    ("Jacksonville",     "FL"),
    ("St. Augustine",    "FL"),
    ("Saint Augustine",  "FL"),   # alt spelling
    ("Daytona Beach",    "FL"),
    ("Cocoa",            "FL"),
    ("Melbourne",        "FL"),
    ("Vero Beach",       "FL"),
    ("Fort Pierce",      "FL"),
    ("West Palm Beach",  "FL"),
    ("Boca Raton",       "FL"),
    ("Fort Lauderdale",  "FL"),
    ("Hollywood",        "FL"),
    ("Miami",            "FL"),
    ("Homestead",        "FL"),
    ("Key West",         "FL"),
]

# Full state names keyed by postal abbreviation — the matcher also accepts
# these as the "state" half of a City/State pair.
STATE_FULL_NAMES: dict[str, str] = {
    "MD": "Maryland",
    "DC": "District of Columbia",
    "VA": "Virginia",
    "NC": "North Carolina",
    "SC": "South Carolina",
    "GA": "Georgia",
    "FL": "Florida",
}
