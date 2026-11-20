from helpers import ADD, GOOD, make

from gatedcrew import loop
from gatedcrew.report import daily


def test_report_for_a_done_run(tmp_path):
    work, worker = make(tmp_path, GOOD)
    loop.Run(work, worker).go()
    text = daily(work)
    assert "Status: **DONE**" in text
    assert "Audit log: OK" in text
    assert "Features passing: 2 of 2" in text
    assert "| 2 | 2 | 0 | 0 |" in text
    assert "## Sessions that did not pass\n\nNone." in text
    assert len(text.splitlines()) < 40  # two-minute read


def test_report_names_the_gate_and_next_step(tmp_path):
    script = {"F01": [{"fault": "forbidden_command", "edits": {"calc.py": ADD}}]}
    work, worker = make(tmp_path, script)
    loop.Run(work, worker).go()
    text = daily(work)
    assert "PENDING_APPROVAL (gate: forbidden_command)" in text
    assert "blocked: `git push origin main`" in text
    assert "gatedcrew approve" in text


def test_report_shows_a_tampered_log(tmp_path):
    from gatedcrew.spec import state_dir

    work, worker = make(tmp_path, GOOD)
    loop.Run(work, worker).go()
    p = state_dir(work) / "audit.jsonl"
    p.write_text(p.read_text().replace('"features": 2', '"features": 3'))
    assert "Audit log: TAMPERED" in daily(work)


def test_report_date_filter(tmp_path):
    work, worker = make(tmp_path, GOOD)
    loop.Run(work, worker).go()
    assert "| 0 | 0 | 0 | 0 |" in daily(work, "1999-01-01")
