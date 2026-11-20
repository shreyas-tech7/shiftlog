"""The subprocess helper: timeouts are required, and nothing else starts a process."""

import re
import sys
import time
from pathlib import Path

import pytest

from gatedcrew.proc import run

ROOT = Path(__file__).resolve().parents[1]
# Ways to start a process in Python. Only src/gatedcrew/proc.py may use them.
SPAWN = re.compile(
    r"\bsubprocess\b|\bos\.(system|popen|exec\w*|spawn\w*|fork\w*|posix_spawn\w*)\b|\bpty\.spawn\b"
    r"|\basyncio\.create_subprocess"
)
ALLOWED = {ROOT / "src" / "gatedcrew" / "proc.py"}


def offenders(root: Path) -> list[str]:
    bad = []
    for folder in ("src", "scripts", "tests"):
        for p in sorted((root / folder).rglob("*.py")):
            if p in ALLOWED or p.name == "test_proc.py":
                continue
            for n, line in enumerate(p.read_text().splitlines(), 1):
                if SPAWN.search(line.split("#", 1)[0]):
                    bad.append(f"{p.relative_to(root)}:{n}")
    return bad


def test_no_subprocess_outside_the_helper():
    assert offenders(ROOT) == []


def test_scan_catches_a_planted_call(tmp_path):
    """Broken case: a module that calls subprocess.run directly must be reported."""
    (tmp_path / "src").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "sneaky.py").write_text("import subprocess\nsubprocess.run(['ls'])\n")
    (tmp_path / "scripts" / "ok.py").write_text("print('hi')\n")
    assert offenders(tmp_path) == ["src/sneaky.py:1", "src/sneaky.py:2"]


def test_timeout_is_required():
    with pytest.raises(ValueError):
        run(["true"], timeout=0)
    with pytest.raises(TypeError):
        run("true", timeout=5)


def test_timeout_kills_the_whole_process_tree():
    code = "import subprocess,time; subprocess.Popen(['sleep','30']); time.sleep(30)"
    t0 = time.monotonic()
    res = run([sys.executable, "-c", code], timeout=1)
    assert res.timed_out and not res.ok
    assert time.monotonic() - t0 < 10


def test_output_is_captured():
    res = run([sys.executable, "-c", "print('hi')"], timeout=10)
    assert res.ok and res.out.strip() == "hi"
