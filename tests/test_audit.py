"""The hash chain catches edits, deletions, reordering and a cut tail."""

import json

from gatedcrew import audit


def make_log(tmp_path, n=4):
    p = tmp_path / "audit.jsonl"
    ticks = iter(range(100))
    last = None
    for i in range(n):
        last = audit.append(p, "session", clock=lambda: next(ticks), session=i, cost_usd=0.01)
    return p, last["hash"]


def test_intact_chain_verifies(tmp_path):
    p, head = make_log(tmp_path)
    assert audit.verify(p, head) == (True, "4 lines, chain intact")


def test_edit_to_an_earlier_line_is_detected(tmp_path):
    """Broken case: lowering the cost on line 2 after the fact."""
    p, head = make_log(tmp_path)
    lines = p.read_text().splitlines()
    e = json.loads(lines[1])
    e["cost_usd"] = 0.0
    lines[1] = json.dumps(e, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    ok, msg = audit.verify(p, head)
    assert not ok and msg == "line 2 was edited (hash mismatch)"


def test_edit_with_a_recomputed_hash_breaks_the_next_link(tmp_path):
    p, head = make_log(tmp_path)
    lines = p.read_text().splitlines()
    e = json.loads(lines[1])
    e["cost_usd"] = 0.0
    e["hash"] = audit._digest(e)
    lines[1] = json.dumps(e, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    ok, msg = audit.verify(p, head)
    assert not ok and msg == "line 3 does not link to line 2"


def test_deleted_line_is_detected(tmp_path):
    p, head = make_log(tmp_path)
    lines = p.read_text().splitlines()
    del lines[1]
    p.write_text("\n".join(lines) + "\n")
    assert not audit.verify(p, head)[0]


def test_cut_tail_is_detected_with_the_saved_head(tmp_path):
    p, head = make_log(tmp_path)
    lines = p.read_text().splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n")
    assert audit.verify(p)[0]  # the chain alone cannot see a cut tail
    ok, msg = audit.verify(p, head)
    assert not ok and "head hash" in msg


def test_garbage_line_is_detected(tmp_path):
    p, head = make_log(tmp_path)
    with p.open("a") as f:
        f.write("not json\n")
    assert audit.verify(p, head) == (False, "line 5 is not valid JSON")


def test_each_line_links_to_the_one_before(tmp_path):
    p, _ = make_log(tmp_path)
    rows = audit.read(p)
    assert rows[0]["prev"] == audit.GENESIS
    assert all(rows[i]["prev"] == rows[i - 1]["hash"] for i in range(1, len(rows)))
