"""End to end through the command line, the way a person runs it."""

import json
import sys

from helpers import ADD, GOOD, SPEC

from gatedcrew.cli import main


def test_cli_init_run_approve_report_verify(tmp_path, capsys):
    (tmp_path / "spec.md").write_text(SPEC)
    script = dict(GOOD)
    script["F01"] = [{"fault": "network", "edits": {"calc.py": ADD}}, {"edits": {"calc.py": ADD}}]
    (tmp_path / "s.json").write_text(json.dumps(script))
    worker = f"{sys.executable} -I -m gatedcrew fake-worker --script {tmp_path / 's.json'}"
    w = str(tmp_path / "w")
    assert main(["init", str(tmp_path / "spec.md"), "--work", w]) == 0
    assert main(["run", "--work", w, "--worker", worker]) == 3
    assert "Pending approval" in capsys.readouterr().out
    assert main(["approve", "--work", w, "--note", "fine"]) == 0
    assert main(["approve", "--work", w]) == 2
    assert main(["run", "--work", w, "--worker", worker]) == 0
    assert main(["verify", "--work", w]) == 0
    assert "OK" in capsys.readouterr().out
    assert main(["report", "--work", w, "--out", str(tmp_path / "r.md")]) == 0
    assert "Status: **DONE**" in (tmp_path / "r.md").read_text()
    assert main(["status", "--work", w]) == 0
    assert '"machine": "DONE"' in capsys.readouterr().out


def test_cli_verify_fails_on_tamper(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC)
    w = tmp_path / "w"
    main(["init", str(tmp_path / "spec.md"), "--work", str(w)])
    p = w / ".git" / "gatedcrew" / "audit.jsonl"
    p.write_text(p.read_text().replace('"session": 0', '"session": 5'))
    assert main(["verify", "--work", str(w)]) == 1


def test_cli_reject_stops(tmp_path):
    (tmp_path / "spec.md").write_text(SPEC)
    (tmp_path / "s.json").write_text(json.dumps({"*": [{"fault": "forbidden_path"}]}))
    worker = f"{sys.executable} -I -m gatedcrew fake-worker --script {tmp_path / 's.json'}"
    w = str(tmp_path / "w")
    main(["init", str(tmp_path / "spec.md"), "--work", w])
    main(["run", "--work", w, "--worker", worker])
    assert main(["reject", "--work", w]) == 0
    assert main(["run", "--work", w, "--worker", worker]) == 3
