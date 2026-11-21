import re
import shutil
from pathlib import Path

from gatedcrew import readme

ROOT = Path(__file__).resolve().parents[1]


def test_readme_matches_results():
    assert readme.main(check=True) == 0


def test_a_typed_number_is_caught(tmp_path):
    """Broken case: someone edits a README number by hand."""
    for rel in ("README.md", "docs/index.html", *readme.RESULTS):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    text = (tmp_path / "README.md").read_text()
    row = re.search(r"\| 1 \| with evaluator \| (\d+\.\d)%", text)
    (tmp_path / "README.md").write_text(text.replace(row.group(0), row.group(0)[:-5] + "99.9%", 1))
    assert readme.main(check=True, root=tmp_path) == 1


def test_readme_says_what_the_benchmark_measures():
    text = (ROOT / "README.md").read_text()
    assert "injects scripted faults into a fake worker" in text
    assert "not how good any model is" in text


def test_every_readme_percent_is_from_the_results():
    text = (ROOT / "README.md").read_text()
    body = "".join(readme.render().values())
    for pct in re.findall(r"\d+\.\d%", text):
        assert pct in body
