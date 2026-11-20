import json
from pathlib import Path

from gatedcrew import bench

ROOT = Path(__file__).resolve().parents[1]


def test_thirty_specs_are_committed_and_match_the_generator(tmp_path):
    files = bench.export_specs(tmp_path / "specs")
    assert len(files) == 30
    for f in files:
        assert f.read_text() == (ROOT / "bench" / "specs" / f.name).read_text()


def test_fault_plan_is_seeded():
    assert bench.fault_plan(1, 3, 4) == bench.fault_plan(1, 3, 4)
    assert bench.fault_plan(1, 3, 4) != bench.fault_plan(2, 3, 4)
    faults = {f for s in range(1, 31) for v in bench.fault_plan(1, s, 5).values() for f in v}
    assert faults == set(bench.FIRST)


def test_small_bench_run(tmp_path):
    out = tmp_path / "b.json"
    assert bench.main(seed=7, specs=2, out=str(out)) == 0
    data = json.loads(out.read_text())
    assert len(data["runs"]) == 4
    w = data["summary"]["with_evaluator"]
    assert w["false_passes"] == 0 and w["logs_intact"] is True
    for r in data["runs"]:
        assert r["claimed_pass"] - r["false_pass"] <= r["true_pass"]
        assert r["final"] in ("DONE", "STOPPED")


def test_hidden_dependency_is_a_false_pass_only_without_the_evaluator(tmp_path, monkeypatch):
    """Broken case: without the evaluator, the hidden helper earns a passes flag."""
    monkeypatch.setattr(
        bench,
        "fault_plan",
        lambda seed, i, n: {f"F{k:02d}": ["hidden_dependency", "none"] for k in range(1, n + 1)},
    )
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    on = bench.run_one(tmp_path / "a", 1, 1, True)
    off = bench.run_one(tmp_path / "b", 1, 1, False)
    assert on["false_pass"] == 0 and on["true_pass"] == on["features"]
    assert off["false_pass"] == off["features"] and off["true_pass"] == 0
    assert on["gates"]["evaluator_disagrees"] == on["features"]


def test_result_files_say_no_model_ran():
    for seed in (1, 2):
        data = json.loads((ROOT / "results" / f"bench-seed{seed}.json").read_text())
        assert data["seed"] == seed and data["model"].startswith("none")
        assert data["summary"]["with_evaluator"]["specs"] == 30
