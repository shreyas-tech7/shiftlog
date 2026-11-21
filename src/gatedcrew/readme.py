"""Write the README result tables and docs/index.html from results/*.json.

Nobody types the numbers. `gatedcrew readme --check` fails when the files on disk
do not match what the result files say.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ["results/bench-seed1.json", "results/bench-seed2.json"]
ARMS = [("with_evaluator", "with evaluator"), ("without_evaluator", "without evaluator")]
GATES = [
    "forbidden_command",
    "network",
    "forbidden_path",
    "evaluator_disagrees",
    "failed_twice",
    "budget_tokens",
    "budget_sessions",
]


def load(root: Path = ROOT) -> list[dict]:
    return [json.loads((root / p).read_text()) for p in RESULTS if (root / p).exists()]


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def ci(pair, as_pct=True) -> str:
    lo, hi = pair
    return f"{pct(lo)} to {pct(hi)}" if as_pct else f"{lo:.2f} to {hi:.2f}"


def results_block(runs: list[dict]) -> str:
    lines = [
        "| Seed | Arm | Features done (true) | 95% interval | Claimed done | False passes | Sessions | Wasted sessions | Wasted per spec (95% interval) |",
        "| ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in runs:
        for key, name in ARMS:
            s = r["summary"][key]
            lines.append(
                f"| {r['seed']} | {name} | {pct(s['completion_rate'])} | {ci(s['completion_ci95'])} "
                f"| {pct(s['claimed_rate'])} | {s['false_passes']} | {s['sessions']} "
                f"| {s['wasted_sessions']} | {s['wasted_per_spec']:.2f} ({ci(s['wasted_per_spec_ci95'], False)}) |"
            )
    lines += [
        "",
        "Gate triggers, summed over 30 specs. These are fixed counts for each seed, with no sampling interval.",
        "",
        "| Seed | Arm | " + " | ".join(GATES) + " |",
        "| ---: | --- | " + " | ".join("---:" for _ in GATES) + " |",
    ]
    for r in runs:
        for key, name in ARMS:
            g = r["summary"][key]["gate_triggers"]
            lines.append(
                f"| {r['seed']} | {name} | " + " | ".join(str(g.get(x, 0)) for x in GATES) + " |"
            )
    stamp = " ".join(
        f"Seed {r['seed']}: {r['date']}, {r['model']}, {r['machine']['cpu']}, "
        f"{r['machine']['cores_used']} core, {r['total_seconds']} s."
        for r in runs
    )
    lines += ["", f"Source: `{'`, `'.join(RESULTS)}`. {stamp}"]
    return "\n".join(lines)


def cost_block(runs: list[dict]) -> str:
    lines = [
        "| Seed | Arm | Sessions per finished feature | Reported tokens per finished feature | Wall seconds per spec | Money spent |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in runs:
        for key, name in ARMS:
            s = r["summary"][key]
            lines.append(
                f"| {r['seed']} | {name} | {s['sessions_per_completed_feature']:.2f} "
                f"| {s['tokens_per_completed_feature']:,.0f} | {s['seconds_per_spec']:.2f} | $0 |"
            )
    return "\n".join(lines)


def headline(runs: list[dict]) -> str:
    first = runs[0]["summary"]["with_evaluator"]
    parts = []
    for r in runs:
        w, wo = r["summary"]["with_evaluator"], r["summary"]["without_evaluator"]
        parts.append(
            f"Seed {r['seed']}: {pct(w['completion_rate'])} of features truly done with the evaluator "
            f"against {pct(wo['completion_rate'])} without it ({wo['false_passes']} false passes "
            f"without, {w['false_passes']} with)."
        )
    return (
        f"Setup: {first['specs']} specs, {first['features']} features, seeds "
        + " and ".join(str(r["seed"]) for r in runs)
        + ". Headline (scripted faults, fake worker). "
        + " ".join(parts)
    )


def fill(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", re.S)
    if not pat.search(text):
        raise ValueError(f"README has no {name} markers")
    return pat.sub(lambda m: m.group(1) + body + m.group(2), text)


def page(runs: list[dict]) -> str:
    rows = []
    for r in runs:
        for key, name in ARMS:
            s = r["summary"][key]
            rows.append(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(str(v))}</td>"
                    for v in (
                        r["seed"],
                        name,
                        pct(s["completion_rate"]),
                        ci(s["completion_ci95"]),
                        pct(s["claimed_rate"]),
                        s["false_passes"],
                        s["sessions"],
                        s["wasted_sessions"],
                        s["gate_triggers_total"],
                        s["budget_stops"],
                    )
                )
                + "</tr>"
            )
    head = "".join(
        f"<th>{h}</th>"
        for h in (
            "Seed",
            "Arm",
            "Done (true)",
            "95% interval",
            "Claimed",
            "False passes",
            "Sessions",
            "Wasted",
            "Gates fired",
            "Budget stops",
        )
    )
    return PAGE.format(head=head, rows="\n".join(rows), headline=html.escape(headline(runs)))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gatedcrew benchmark results</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1b1f24; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; text-align: right; }}
th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
th {{ background: #f6f8fa; }}
.note {{ background: #fff8c5; padding: 0.75rem 1rem; border-radius: 6px; }}
</style>
</head>
<body>
<h1 id="results">gatedcrew benchmark results</h1>
<p class="note">The benchmark injects scripted faults into a fake worker. It measures how the harness reacts, not how good any model is.</p>
<p>{headline}</p>
<table>
<thead><tr>{head}</tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p>This page is generated by <code>gatedcrew readme</code> from <code>results/bench-seed1.json</code> and <code>results/bench-seed2.json</code>. It opens from disk with no sign-in.</p>
<p><a href="../README.md">README</a> · <a href="SAFETY.md">Safety limits</a> · <a href="DEMO.md">Terminal demo</a></p>
</body>
</html>
"""


def render(root: Path = ROOT) -> dict[Path, str]:
    runs = load(root)
    readme = (root / "README.md").read_text()
    readme = fill(readme, "results", results_block(runs))
    readme = fill(readme, "cost", cost_block(runs))
    readme = fill(readme, "headline", headline(runs))
    return {root / "README.md": readme, root / "docs" / "index.html": page(runs)}


def main(check: bool = False, root: Path = ROOT) -> int:
    stale = []
    for path, text in render(root).items():
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.name)
        else:
            path.write_text(text)
    if stale:
        print("out of date:", ", ".join(stale), "(run `gatedcrew readme`)")
        return 1
    print(
        "README.md and docs/index.html match the result files"
        if check
        else "wrote README.md and docs/index.html"
    )
    return 0
