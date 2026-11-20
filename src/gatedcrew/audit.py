"""Append-only audit log in JSON Lines with a hash chain.

Each line holds `prev`, the hash of the line before it, and `hash`, the SHA-256 of
its own canonical JSON without the `hash` field. Editing, deleting or reordering
an earlier line breaks every hash after it. The newest hash is also kept in
state.json, so cutting lines off the end shows up too.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def last_hash(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, GENESIS
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return 0, GENESIS
    last = json.loads(lines[-1])
    return last["seq"], last["hash"]


def append(path: Path, event: str, clock=time.time, **fields) -> dict:
    seq, prev = last_hash(path)
    entry = {"seq": seq + 1, "ts": round(clock(), 3), "event": event, **fields, "prev": prev}
    entry["hash"] = _digest(entry)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, ensure_ascii=True) + "\n")
    return entry


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify(path: Path, expected_head: str | None = None) -> tuple[bool, str]:
    """Check the whole chain. Returns (ok, message)."""
    prev = GENESIS
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for n, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return False, f"line {n} is not valid JSON"
        if not isinstance(entry, dict) or "hash" not in entry or "prev" not in entry:
            return False, f"line {n} has no hash fields"
        if entry.get("seq") != n:
            return False, f"line {n} has seq {entry.get('seq')}"
        if entry["prev"] != prev:
            return False, f"line {n} does not link to line {n - 1}"
        if _digest(entry) != entry["hash"]:
            return False, f"line {n} was edited (hash mismatch)"
        prev = entry["hash"]
    if expected_head is not None and prev != expected_head:
        return False, "the newest line does not match the saved head hash (lines removed?)"
    return True, f"{len(lines)} lines, chain intact"
