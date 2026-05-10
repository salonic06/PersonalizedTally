"""Application identity (single place for display strings and on-disk names)."""

from __future__ import annotations

# Shown in window title, Qt application name, README.
APP_DISPLAY_NAME = "Personalized Tally"
APP_TAGLINE = "Simple desktop accounting for small businesses"

# Primary SQLite file under <repo>/data/
DB_FILENAME = "personalized_tally.db"

# Older installs used this name; see get_paths() for one-time rename.
LEGACY_DB_FILENAME = "lamitech.db"
