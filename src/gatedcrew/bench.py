"""Fault-injection benchmark.

30 small specs. For each feature attempt a seeded draw picks a scripted fault for
the fake worker. Every spec runs twice on the same fault plan: once with the
separate evaluator and once without it. A simulated human approves each gate
(up to 4 times per spec, then rejects).

This measures how the harness reacts to scripted faults. It says nothing about
how good any model is.
"""

from __future__ import annotations

import json
import platform
import random
import sys
import tempfile
import time
from pathlib import Path

from . import audit, loop
from .evaluate import ground_truth
from .spec import init, state_dir

# name, correct body, broken body, check
POOL = [
    (
        "add",
        "def add(a, b):\n    return a + b\n",
        "def add(a, b):\n    return a - b\n",
        "add(2, 3) == 5",
    ),
    (
        "sub",
        "def sub(a, b):\n    return a - b\n",
        "def sub(a, b):\n    return b - a\n",
        "sub(5, 3) == 2",
    ),
    (
        "mul",
        "def mul(a, b):\n    return a * b\n",
        "def mul(a, b):\n    return a + b\n",
        "mul(4, 3) == 12",
    ),
    (
        "is_even",
        "def is_even(n):\n    return n % 2 == 0\n",
        "def is_even(n):\n    return n % 2 == 1\n",
        "is_even(4) and not is_even(3)",
    ),
    (
        "clamp",
        "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n",
        "def clamp(x, lo, hi):\n    return min(lo, max(x, hi))\n",
        "clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0",
    ),
    (
        "reverse",
        "def reverse(s):\n    return s[::-1]\n",
        "def reverse(s):\n    return s\n",
        "reverse('abc') == 'cba'",
    ),
    (
        "vowels",
        "def vowels(s):\n    return sum(c in 'aeiou' for c in s.lower())\n",
        "def vowels(s):\n    return len(s)\n",
        "vowels('Banana') == 3",
    ),
    (
        "mean",
        "def mean(xs):\n    return sum(xs) / len(xs)\n",
        "def mean(xs):\n    return sum(xs) // 2\n",
        "mean([1, 2, 3, 6]) == 3",
    ),
    (
        "slug",
        "def slug(s):\n    return '-'.join(s.lower().split())\n",
        "def slug(s):\n    return s.lower()\n",
        "slug('Hello Big World') == 'hello-big-world'",
    ),
    (
        "fizz",
        "def fizz(n):\n    return 'Fizz' if n % 3 == 0 else str(n)\n",
        "def fizz(n):\n    return str(n)\n",
        "fizz(9) == 'Fizz' and fizz(4) == '4'",
    ),
    (
        "dedupe",
        "def dedupe(xs):\n    return list(dict.fromkeys(xs))\n",
        "def dedupe(xs):\n    return sorted(set(xs))\n",
        "dedupe([3, 1, 3, 2]) == [3, 1, 2]",
    ),
    (
        "palin",
        "def palin(s):\n    return s == s[::-1]\n",
        "def palin(s):\n    return True\n",
        "palin('abba') and not palin('abc')",
    ),
]

N_SPECS = 30
# First attempt at a feature: probability of each fault. Later attempts are cleaner.
FIRST = {
    "none": 0.40,
    "break": 0.15,
    "claim_done": 0.08,
    "hidden_dependency": 0.12,
    "forbidden_command": 0.08,
    "network": 0.05,
    "forbidden_path": 0.07,
    "timeout": 0.03,
    "token_burn": 0.02,
}
LATER = {"none": 0.70, "break": 0.15, "claim_done": 0.05, "hidden_dependency": 0.10}
APPROVALS_PER_SPEC = 4
BURN = 10**8  # sessions at or above this are the token burn fault

POLICY = """[budget]
max_sessions = {max_sessions}
max_wall_seconds = 600
session_timeout_seconds = 4
max_tokens = 10000000
backoff_seconds = 0

[gates]
max_consecutive_failures = 2
evaluator = {evaluator}
"""


def spec_text(i: int) -> tuple[str, list[tuple]]:
    """Spec i (1-based). The content is fixed; only the fault plan depends on the seed."""
    rng = random.Random(1000 + i)
    picks = rng.sample(POOL, rng.randint(3, 5))
    lines = [f"# bench-{i:02d}", ""]
    for n, (name, *_rest) in enumerate(picks, 1):
        lines += [
            f"## {name}",
            f'check: python3 -c "from f{n:02d} import {name}; assert {_rest[2]}"',
            "",
        ]
    return "\n".join(lines), picks


def fault_plan(seed: int, spec: int, features: int) -> dict[str, list[str]]:
    rng = random.Random(seed * 100003 + spec)
    plan = {}
    for n in range(1, features + 1):
        first = rng.choices(list(FIRST), weights=list(FIRST.values()))[0]
        later = rng.choices(list(LATER), weights=list(LATER.values()), k=3)
        plan[f"F{n:02d}"] = [first, *later, "none"]
    return plan


def script_for(picks: list[tuple], plan: dict[str, list[str]]) -> dict:
    script = {}
    for n, (name, good, bad, _check) in enumerate(picks, 1):
        fid, mod = f"F{n:02d}", f"f{n:02d}.py"
        attempts = []
        for fault in plan[fid]:
            act = {"fault": fault, "tokens": 1500}
            if fault == "break":
                act["edits"] = {mod: bad}
            elif fault == "hidden_dependency":
                act["edits"] = {
                    mod: f"import sys\nsys.path.insert(0, 'local')\nfrom helper_{n:02d} import {name}  # noqa\n"
                }
                act["hidden"] = {f"local/helper_{n:02d}.py": good}
            else:
                act["edits"] = {mod: good}
            attempts.append(act)
        script[fid] = attempts
    return script


def run_one(tmp: Path, i: int, seed: int, evaluator: bool) -> dict:
    text, picks = spec_text(i)
    base = tmp / f"s{i:02d}-{'eval' if evaluator else 'noeval'}"
    base.mkdir()
    (base / "spec.md").write_text(text)
    plan = fault_plan(seed, i, len(picks))
    (base / "script.json").write_text(json.dumps(script_for(picks, plan)))
    (base / "policy.toml").write_text(
        POLICY.format(max_sessions=len(picks) * 3, evaluator=str(evaluator).lower())
    )
    work = base / "work"
    init(base / "spec.md", work, base / "policy.toml")
    worker = f"{sys.executable} -I -m gatedcrew fake-worker --script {base / 'script.json'}"
    t0 = time.perf_counter()
    approvals = 0
    while True:
        final = loop.Run(work, worker).go()
        if final != "PENDING_APPROVAL":
            break
        if approvals < APPROVALS_PER_SPEC:
            approvals += 1
            loop.approve(work, "benchmark: simulated human approves")
        else:
            loop.reject(work, "benchmark: simulated human rejects after 4 approvals")
    seconds = time.perf_counter() - t0
    sd = state_dir(work)
    state = json.loads((sd / "state.json").read_text())
    entries = audit.read(sd / "audit.jsonl")
    sessions = [e for e in entries if e["event"] == "session"]
    gates: dict[str, int] = {}
    for e in entries:
        if e["event"] == "gate":
            gates[e["reason"]] = gates.get(e["reason"], 0) + 1
        if e["event"] == "stopped":
            gates[e["reason"]] = gates.get(e["reason"], 0) + 1
    listing = json.loads((work / "feature_list.json").read_text())
    truth = ground_truth(work, state["good_commit"])
    claimed = {f["id"]: f["passes"] for f in listing}
    ok, _ = audit.verify(sd / "audit.jsonl", state["audit_head"])
    return {
        "spec": i,
        "evaluator": evaluator,
        "features": len(listing),
        "true_pass": sum(truth.values()),
        "claimed_pass": sum(claimed.values()),
        "false_pass": sum(1 for k, v in claimed.items() if v and not truth[k]),
        "sessions": len(sessions),
        "wasted_sessions": sum(1 for s in sessions if s.get("outcome") != "pass"),
        "gates": gates,
        "final": state["machine"],
        "approvals": approvals,
        "tokens": state["tokens"],
        "tokens_without_burn": sum(
            s.get("tokens", 0) for s in sessions if s.get("tokens", 0) < BURN
        ),
        "seconds": round(seconds, 2),
        "log_ok": ok,
        "faults_drawn": {k: v[0] for k, v in plan.items()},
    }


def bootstrap(rows: list[dict], fn, seed: int, n: int = 2000) -> tuple[float, float]:
    """95% interval by resampling whole specs (features inside a spec share a run)."""
    rng = random.Random(seed)
    vals = sorted(fn([rng.choice(rows) for _ in rows]) for _ in range(n))
    return round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)


def summarize(rows: list[dict], seed: int) -> dict:
    def rate(rs, key):
        return sum(r[key] for r in rs) / sum(r["features"] for r in rs)

    def per_spec(rs, key):
        return sum(r[key] for r in rs) / len(rs)

    out = {}
    for mode in (True, False):
        rs = [r for r in rows if r["evaluator"] is mode]
        gates: dict[str, int] = {}
        for r in rs:
            for k, v in r["gates"].items():
                gates[k] = gates.get(k, 0) + v
        done = sum(r["true_pass"] for r in rs)
        out["with_evaluator" if mode else "without_evaluator"] = {
            "specs": len(rs),
            "features": sum(r["features"] for r in rs),
            "completion_rate": round(rate(rs, "true_pass"), 4),
            "completion_ci95": bootstrap(rs, lambda x: rate(x, "true_pass"), seed),
            "claimed_rate": round(rate(rs, "claimed_pass"), 4),
            "false_passes": sum(r["false_pass"] for r in rs),
            "sessions": sum(r["sessions"] for r in rs),
            "wasted_sessions": sum(r["wasted_sessions"] for r in rs),
            "wasted_per_spec": round(per_spec(rs, "wasted_sessions"), 3),
            "wasted_per_spec_ci95": bootstrap(rs, lambda x: per_spec(x, "wasted_sessions"), seed),
            "gate_triggers": dict(sorted(gates.items())),
            "gate_triggers_total": sum(v for k, v in gates.items() if not k.startswith("budget")),
            "budget_stops": sum(v for k, v in gates.items() if k.startswith("budget")),
            "sessions_per_completed_feature": round(
                sum(r["sessions"] for r in rs) / max(done, 1), 3
            ),
            "tokens_per_completed_feature": round(
                sum(r["tokens_without_burn"] for r in rs) / max(done, 1), 1
            ),
            "seconds_per_spec": round(per_spec(rs, "seconds"), 2),
            "logs_intact": all(r["log_ok"] for r in rs),
        }
    return out


def main(seed: int, specs: int, out: str) -> int:
    rows = []
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="gatedcrew-bench-") as tmp:
        for i in range(1, specs + 1):
            for evaluator in (True, False):
                rows.append(run_one(Path(tmp), i, seed, evaluator))
            print(f"spec {i:02d} done ({time.perf_counter() - t0:.0f}s)", flush=True)
    result = {
        "seed": seed,
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "model": "none (scripted fake worker)",
        "machine": {"cpu": _cpu(), "python": platform.python_version(), "cores_used": 1},
        "total_seconds": round(time.perf_counter() - t0, 1),
        "fault_weights_first_attempt": FIRST,
        "fault_weights_later_attempts": LATER,
        "summary": summarize(rows, seed),
        "runs": rows,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))
    return 0


def _cpu() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def export_specs(folder: str | Path) -> list[Path]:
    """Write the 30 benchmark specs as plain files, so a reader can see them."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(1, N_SPECS + 1):
        p = folder / f"bench-{i:02d}.md"
        p.write_text(spec_text(i)[0])
        out.append(p)
    return out
