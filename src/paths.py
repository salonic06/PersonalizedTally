from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .app_info import DB_FILENAME, LEGACY_DB_FILENAME


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    db_path: Path


def get_paths() -> AppPaths:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / DB_FILENAME
    _maybe_upgrade_legacy_db(data_dir, db_path)
    return AppPaths(root=root, data_dir=data_dir, db_path=db_path)


def _maybe_upgrade_legacy_db(data_dir: Path, db_path: Path) -> None:
    """If the new DB file is missing but the old lamitech.db exists, rename once."""
    if db_path.exists():
        return
    legacy = data_dir / LEGACY_DB_FILENAME
    if not legacy.exists():
        return
    try:
        legacy.replace(db_path)
    except OSError:
        # Another process may hold the file; user can rename manually.
        pass

