import json

import pytest
from helpers import SPEC

from gatedcrew import gitops
from gatedcrew.spec import SpecError, init, parse, state_dir


def test_parse_spec():
    spec = parse(SPEC)
    assert spec["name"] == "tiny-calc"
    assert [f["id"] for f in spec["features"]] == ["F01", "F02"]
    assert all(f["passes"] is False and f["steps"] for f in spec["features"])


@pytest.mark.parametrize(
    "text, msg",
    [
        ("## a\ncheck: true\n", "# name"),
        ("# x\n", "at least one"),
        ("# x\n## a\n", "no check"),
        ("# x\ncheck: true\n## a\ncheck: true\n", "before the first"),
    ],
)
def test_bad_specs(text, msg):
    with pytest.raises(SpecError, match=msg):
        parse(text)


def test_init_makes_files_and_first_commit(tmp_path):
    (tmp_path / "spec.md").write_text("# demo\nignore: build/\n## a\ncheck: true\n")
    work = init(tmp_path / "spec.md", tmp_path / "w")
    listing = json.loads((work / "feature_list.json").read_text())
    assert listing[0]["passes"] is False and listing[0]["steps"] == ["true"]
    assert "0 of 1 features pass" in (work / "PROGRESS.md").read_text()
    assert (work / "init.sh").stat().st_mode & 0o111
    assert "build/" in (work / ".gitignore").read_text()
    log = gitops.git(["log", "--format=%s"], work).out.splitlines()
    assert log == ["gatedcrew init: demo"]
    assert gitops.tree_matches_head(work)
    sd = state_dir(work)
    assert (sd / "policy.toml").exists() and (sd / "audit.jsonl").exists()
    assert gitops.run(["./init.sh"], cwd=work, timeout=30).ok


def test_init_refuses_a_non_empty_folder(tmp_path):
    (tmp_path / "spec.md").write_text("# demo\n## a\ncheck: true\n")
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / "x").write_text("x")
    with pytest.raises(SpecError, match="not empty"):
        init(tmp_path / "spec.md", tmp_path / "w")


def test_init_rejects_a_bad_policy_before_writing(tmp_path):
    (tmp_path / "spec.md").write_text("# demo\n## a\ncheck: true\n")
    (tmp_path / "p.toml").write_text("[nope]\n")
    with pytest.raises(ValueError):
        init(tmp_path / "spec.md", tmp_path / "w", tmp_path / "p.toml")
    assert not (tmp_path / "w").exists()


def test_pinned_git_ignores_machine_config(tmp_path, monkeypatch):
    """Broken case: a global config that turns on commit signing would break every commit."""
    cfg = tmp_path / "evil.gitconfig"
    cfg.write_text("[commit]\n\tgpgsign = true\n[user]\n\tsigningkey = nope\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    (tmp_path / "spec.md").write_text("# demo\n## a\ncheck: true\n")
    work = init(tmp_path / "spec.md", tmp_path / "w")
    assert gitops.git(["log", "--format=%an"], work).out.strip() == "gatedcrew"
