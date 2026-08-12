from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.bootstrap.content import DailyChallengeContent, HiddenCaseContent, load_content_bundle
from app.bootstrap.validate_catalog import FORBIDDEN_PUBLIC_FIELDS, _check_public_contracts

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "content"


@pytest.mark.unit
def test_full_catalog_has_required_coverage_and_six_scenarios() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")
    difficulties = [item.document.difficulty.value for item in bundle.problems.values()]
    tags = {tag for item in bundle.problems.values() for tag in item.document.tags}
    required_tags = {
        "basic-io", "array", "string", "hash-table", "two-pointers",
        "sliding-window", "prefix-sum", "stack", "queue", "binary-search",
        "sorting", "interval", "matrix", "bfs", "dfs", "graph-connectivity",
        "union-find", "shortest-path", "minimum-spanning-tree", "greedy",
        "zero-one-knapsack", "dynamic-programming",
        "longest-increasing-subsequence", "edit-distance",
    }
    assert len(bundle.problems) == 30
    assert difficulties.count("easy") >= 10
    assert difficulties.count("medium") >= 14
    assert difficulties.count("hard") >= 6
    assert required_tags <= tags
    for problem in bundle.problems.values():
        assert len(problem.cases) == 6
        assert problem.document.data_constraints
        assert problem.document.sample_explanation
        assert problem.document.reference_solutions.python.endswith(".py")
        assert problem.document.reference_solutions.cpp.endswith(".cpp")


@pytest.mark.unit
def test_catalog_collections_and_relative_challenges_are_complete() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")
    assert len(bundle.collections) == 3
    assert all(
        collection.is_public and len(collection.problems) >= 8
        for collection in bundle.collections
    )
    assert len(bundle.daily_challenges) == 14
    today = datetime.now(ZoneInfo(bundle.manifest.timezone)).date()
    actual = []
    for challenge in bundle.daily_challenges:
        if isinstance(challenge.date, date):
            actual.append(challenge.date)
        elif challenge.date == "today":
            actual.append(today)
        else:
            actual.append(today + timedelta(days=int(challenge.date[6:])))
    assert actual == [today + timedelta(days=offset) for offset in range(14)]


@pytest.mark.unit
def test_six_scenarios_and_relative_date_validation_are_strict() -> None:
    base = {
        "sequence": 1, "score": 10, "input_file": "a.in", "output_file": "a.out",
        "scenario": "normal", "scenario_description": "ordinary input",
    }
    assert HiddenCaseContent.model_validate(base).scenario == "normal"
    with pytest.raises(ValidationError):
        HiddenCaseContent.model_validate({**base, "scenario": "unknown"})
    assert DailyChallengeContent(date="today+13", problem="a").date == "today+13"
    with pytest.raises(ValidationError):
        DailyChallengeContent(date="today+999", problem="a")


@pytest.mark.unit
def test_public_problem_dtos_never_expose_reference_or_hidden_fields() -> None:
    _check_public_contracts()
    assert "reference_solutions" in FORBIDDEN_PUBLIC_FIELDS
    assert "test_set" in FORBIDDEN_PUBLIC_FIELDS
