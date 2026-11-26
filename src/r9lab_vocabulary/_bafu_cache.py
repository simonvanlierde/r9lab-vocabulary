"""Reuse the names extracted from a BAFU archive on this machine."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
import zlib
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING
from xml.parsers.expat import EXPAT_VERSION

if TYPE_CHECKING:
    from collections.abc import Callable

DIRECTORY = Path("data/raw/.bafu-cache")
NAME_COLUMNS = ["code", "name", "location"]  # each row a name-list reader returns, and the cache keeps
_MAX_BYTES = 4 * 1024 * 1024


def reader_version(path: Path) -> str | None:
    """Fingerprint the reader file when its module loads."""
    with suppress(OSError):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def read_names(
    source_id: str,
    payload: bytes,
    *,
    reader: Callable[[bytes], list[dict[str, str]]],
    version: str | None,
) -> list[dict[str, str]]:
    """Read one archive. Reuse private cached rows for the same bytes and reader."""
    if version is None:
        return reader(payload)
    path = DIRECTORY / source_id
    key = None
    with suppress(OSError):
        reader_identity = (
            version,
            sys.version,
            EXPAT_VERSION,
            zlib.ZLIB_RUNTIME_VERSION,
            sqlite3.sqlite_version,
        )
        DIRECTORY.mkdir(mode=0o700, exist_ok=True)
        if not DIRECTORY.is_symlink() and (
            not hasattr(os, "getuid") or not DIRECTORY.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        ):
            key = json.dumps([hashlib.sha256(payload).hexdigest(), reader_identity]).encode()
            if (cached := _read(path, key)) is not None:
                return cached

    rows = reader(payload)
    if key is not None:
        with suppress(OSError):
            _write(path, key, rows)
    return rows


def _read(path: Path, key: bytes) -> list[dict[str, str]] | None:
    try:
        if not path.is_file():
            return None
        with path.open("rb") as file:
            data = file.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            return None
        name, digest, payload = data.split(b"\n", 2)
        if name != key or digest != hashlib.sha256(payload).hexdigest().encode():
            return None
        rows = json.loads(payload)
    except FileNotFoundError, ValueError, RecursionError:
        return None
    fields = set(NAME_COLUMNS)
    if isinstance(rows, list) and all(
        isinstance(row, dict) and row.keys() == fields and all(isinstance(value, str) for value in row.values())
        for row in rows
    ):
        return rows
    return None


def _write(path: Path, key: bytes, rows: list[dict[str, str]]) -> None:
    with tempfile.TemporaryDirectory(dir=DIRECTORY) as temp:
        new = Path(temp) / "rows"
        new.touch(mode=0o600)
        with new.open("wb") as file:
            # Reserve one line for the checksum and fill it after writing the rows.
            file.write(key + b"\n" + b"0" * 64 + b"\n")
            digest = hashlib.sha256(b"[")
            file.write(b"[")
            for index, row in enumerate(rows):
                # SQLite can return BLOBs in text columns. SourceLedger formats those cells.
                if any(not isinstance(cell, str) for cell in row.values()):
                    return
                line = (b"," if index else b"") + json.dumps(row, ensure_ascii=True).encode()
                if file.tell() + len(line) + 1 > _MAX_BYTES:
                    return
                file.write(line)
                digest.update(line)
            file.write(b"]")
            digest.update(b"]")
            file.seek(len(key) + 1)
            file.write(digest.hexdigest().encode())
        new.replace(path)
