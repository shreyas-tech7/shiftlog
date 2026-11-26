"""Repo quality bar: files, README order, writing rules, CI shape."""

import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/workflows/ci.yml",
    ".github/workflows/bench.yml",
    "docs/topics.txt",
    "docs/GITHUB_ABOUT.md",
    "docs/social-preview.png",
    "docs/index.html",
    "docs/DEMO.md",
    "docs/SAFETY.md",
    "docs/WALKTHROUGH.md",
    "docs/INTERVIEW_QA.md",
    "docs/HUMAN_STEPS.md",
    "docs/build/BUILD_PROMPT.md",
    "DECISIONS.md",
    ".env.example",
    ".pre-commit-config.yaml",
]


@pytest.mark.parametrize("rel", REQUIRED)
def test_required_file_exists(rel):
    assert (ROOT / rel).is_file()


def test_license_is_mit_for_shreyas():
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License") and "Copyright (c) 2026 Shreyas" in text


def test_readme_sections_in_order():
    text = (ROOT / "README.md").read_text()
    marks = [
        "**Status:**",
        "## The problem",
        "```mermaid",
        "## Results",
        "## Cost per task",
        "## Run it in 10 minutes",
        "## Limits",
        "## Glossary",
        "## Related work",
        "## How this was built",
    ]
    pos = [text.index(m) for m in marks]
    assert pos == sorted(pos)
    assert "actions/workflows/ci.yml/badge.svg" in text
    assert "sequenceDiagram" in text
    assert "docs/build/BUILD_PROMPT.md" in text and "not done yet" in text


def prose_files():
    files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    files += [
        ROOT / "CONTRIBUTING.md",
        ROOT / "CHANGELOG.md",
    ]
    return files


@pytest.mark.parametrize("path", prose_files(), ids=lambda p: p.name)
def test_writing_rules(path):
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    assert "—" not in text and "–" not in text, "no em or en dashes"
    for phrase in ("it is important to note", "testament", "pivotal", "seamless", "delve"):
        assert phrase not in text.lower()
    prose = [ln for ln in text.splitlines() if ln and not ln.startswith(("|", "<", "    "))]
    assert not [ln for ln in prose if ";" in ln], "no semicolons in prose"


def test_social_preview_size():
    head = (ROOT / "docs/social-preview.png").read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", head[16:24]) == (1280, 640)


def test_topics_are_valid():
    topics = (ROOT / "docs/topics.txt").read_text().split()
    assert 5 <= len(topics) <= 20
    assert all(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,24}", t) for t in topics)


def test_ci_shape():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    for needle in (
        "workflow_dispatch",
        "pull_request",
        "cancel-in-progress: true",
        '"3.11"',
        "./init.sh",
        "timeout-minutes: 5",
    ):
        assert needle in ci
    assert "workflow_dispatch" in (ROOT / ".github/workflows/bench.yml").read_text()


def test_study_later_kit():
    qa = (ROOT / "docs/INTERVIEW_QA.md").read_text()
    assert len(re.findall(r"^\*\*\d+\.", qa, re.M)) >= 15
    for point in ("separate evaluator", "each gate prevent", "not do"):
        assert point in qa
    walk = (ROOT / "docs/WALKTHROUGH.md").read_text()
    for f in sorted((ROOT / "src/gatedcrew").glob("*.py")):
        assert f.name in walk, f.name
