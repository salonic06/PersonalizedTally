from __future__ import annotations

import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request

from src.repo import Repo


def get_repo(request: Request) -> Repo:
    repo: Repo = request.app.state.repo
    return repo


RepoDep = Annotated[Repo, Depends(get_repo)]


def get_conn(request: Request) -> Generator[sqlite3.Connection, None, None]:
    # Shared connection per process; read-only routes do not commit.
    yield request.app.state.conn
