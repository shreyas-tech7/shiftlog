"""Run a real gatedcrew session in a temp folder and save the terminal transcript to docs/DEMO.md."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gatedcrew.proc import run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="gatedcrew-demo-"))
    try:
        shutil.copy(ROOT / "examples" / "tiny-calc.md", tmp / "tiny-calc.md")
        shutil.copy(ROOT / "examples" / "tiny-calc-script.json", tmp / "script.json")
        exe = str(Path(sys.executable).with_name("gatedcrew"))
        env = dict(os.environ, PATH=f"{Path(exe).parent}{os.pathsep}{os.environ['PATH']}")
        worker = "gatedcrew fake-worker --script ../script.json"
        steps = [
            "gatedcrew init tiny-calc.md --work work",
            f'gatedcrew run --work work --worker "{worker}"',
            "gatedcrew approve --work work --note 'push was blocked, go on'",
            f'gatedcrew run --work work --worker "{worker}"',
            "gatedcrew approve --work work --note 'the next try will be honest'",
            f'gatedcrew run --work work --worker "{worker}"',
            "gatedcrew verify --work work",
            "git -C work log --format='%h %s'",
            "gatedcrew report --work work",
            'sed -i \'s/"features": 3/"features": 4/\' work/.git/gatedcrew/audit.jsonl',
            "gatedcrew verify --work work",
        ]
        out = [
            "# Demo: a real terminal transcript",
            "",
            "Made by `python scripts/make_demo.py`. The worker is the scripted fake worker,",
            "so no model and no network take part. The script `examples/tiny-calc-script.json`",
            "injects a forbidden `git push`, a hidden dependency that only works in the work",
            "repo, and a broken edit. The temp folder path is shortened to `$TMP`.",
            "",
            "```console",
        ]
        for cmd in steps:
            res = run(["/bin/sh", "-c", cmd], cwd=tmp, env=env, timeout=120)
            text = (res.out + res.err).replace(str(tmp), "$TMP").rstrip()
            out.append(f"$ {cmd}")
            if text:
                out.append(text)
        out += ["```", ""]
        (ROOT / "docs" / "DEMO.md").write_text("\n".join(out))
        print("wrote docs/DEMO.md")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
