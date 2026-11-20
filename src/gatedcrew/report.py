"""The daily report: one Markdown page a person can read in two minutes."""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import audit
from .spec import state_dir

NEXT = {
    "DONE": "Nothing. Every feature passes. Read the diff and merge it.",
    "PENDING_APPROVAL": "Read PENDING_APPROVAL.md, then run `gatedcrew approve` or `gatedcrew reject`.",
    "STOPPED": "The run is over. Read the stop reason. Raise the budget in the policy or start a new run.",
    "READY": "The run paused between sessions. Run `gatedcrew run` to go on.",
}


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def daily(work: str | Path, date: str | None = None) -> str:
    work = Path(work)
    sd = state_dir(work)
    state = json.loads((sd / "state.json").read_text())
    entries = audit.read(sd / "audit.jsonl")
    ok, msg = audit.verify(sd / "audit.jsonl", state.get("audit_head"))
    if date:
        entries = [e for e in entries if _day(e["ts"]) == date]
    sessions = [e for e in entries if e["event"] == "session"]
    passed = [s for s in sessions if s.get("outcome") == "pass"]
    gates = [e for e in entries if e["event"] == "gate"]
    listing = json.loads((work / "feature_list.json").read_text())
    tokens = sum(s.get("tokens", 0) for s in sessions)
    cost = sum(s.get("cost_usd", 0.0) for s in sessions)
    span = date or (f"{_day(entries[0]['ts'])} to {_day(entries[-1]['ts'])}" if entries else "-")

    machine = state["machine"]
    status = machine
    if machine == "PENDING_APPROVAL" and state.get("pending"):
        status += f" (gate: {state['pending']['reason']})"
    stop = [e for e in entries if e["event"] == "stopped"]
    if stop:
        status += f" (stop: {stop[-1]['reason']})"

    lines = [
        f"# gatedcrew daily report: {state['name']}",
        "",
        f"- Period: {span} (UTC)",
        f"- Status: **{status}**",
        f"- Audit log: {'OK' if ok else 'TAMPERED'}, {msg}",
        f"- Features passing: {sum(f['passes'] for f in listing)} of {len(listing)}",
        "",
        "| Sessions | Passed | Wasted | Gates fired | Tokens | Cost (reported) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {len(sessions)} | {len(passed)} | {len(sessions) - len(passed)} | {len(gates)} "
        f"| {tokens:,} | ${cost:.4f} |",
        "",
        "## Features",
        "",
    ]
    for f in listing:
        tries = [s for s in sessions if s.get("feature") == f["id"]]
        mark = "passes" if f["passes"] else "not yet"
        lines.append(f"- {f['id']} {f['description']}: {mark}, {len(tries)} session(s) in period")
    lines += ["", "## Sessions that did not pass", ""]
    bad = [s for s in sessions if s.get("outcome") != "pass"]
    if not bad:
        lines.append("None.")
    for s in bad:
        extra = ""
        if s.get("blocked"):
            extra = " blocked: `" + "; ".join(" ".join(a) for a in s["blocked"]) + "`"
        if s.get("forbidden_paths_touched"):
            extra = " touched: " + ", ".join(s["forbidden_paths_touched"])
        gate = f", gate {s['gate']}" if s.get("gate") else ""
        lines.append(f"- session {s['session']} {s['feature']}: {s['outcome']}{gate}{extra}")
    decisions = [e for e in entries if e["event"] in ("approved", "rejected", "stopped")]
    if decisions:
        lines += ["", "## Human decisions and stops", ""]
        for e in decisions:
            lines.append(f"- {e['event']}: {e.get('reason')} {e.get('note') or ''}".rstrip())
    lines += ["", "## Next step", "", NEXT.get(machine, "Check `gatedcrew status`."), ""]
    return "\n".join(lines)
