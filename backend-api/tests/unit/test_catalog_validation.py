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
    tags = {tag for item in bundle.problems.values() for tag in item.document.tags}
    required_tags = {
        "stdin", "stdout", "javascript-v8", "nodejs", "single-value",
        "single-line-values", "multi-line", "test-cases", "read-until-eof",
        "sentinel", "arrays", "matrices", "strings", "mixed-nested", "large-input",
        "output-format",
    }
    assert len(bundle.problems) == 168
    assert required_tags <= tags
    for problem in bundle.problems.values():
        assert len(problem.cases) == 6
        assert problem.document.data_constraints
        assert problem.document.sample_explanation
        assert len(problem.document.samples) >= 2
        assert problem.document.learning_objective
        assert problem.document.v8_hint
        assert problem.document.nodejs_hint
        assert problem.document.common_errors
        assert problem.document.chapter
        assert problem.document.chapter_order
        assert problem.document.estimated_minutes
        assert problem.document.reference_solutions.javascript_v8.endswith(".js")
        assert problem.document.reference_solutions.nodejs.endswith(".js")


@pytest.mark.unit
def test_catalog_collections_and_relative_challenges_are_complete() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")
    assert len(bundle.collections) == 18
    assert all(collection.is_public and collection.problems for collection in bundle.collections)
    assert sum(len(collection.problems) for collection in bundle.collections) == 168
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


@pytest.mark.unit
def test_course_prerequisites_form_a_valid_ordered_dag() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")
    positions = {
        slug: index
        for index, slug in enumerate(bundle.problems)
    }
    for slug, materialized in bundle.problems.items():
        document = materialized.document
        assert all(
            positions[prerequisite] < positions[slug]
            for prerequisite in document.prerequisites
        )
        collection = next(item for item in bundle.collections if item.slug == document.chapter)
        assert collection.problems[document.chapter_order - 1] == slug


@pytest.mark.unit
def test_output_course_covers_every_requested_chapter_and_contract() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")
    output_problems = {
        slug: item
        for slug, item in bundle.problems.items()
        if slug.startswith("js-acm-output-")
    }
    chapter_sizes = {
        collection.slug: len(collection.problems)
        for collection in bundle.collections
        if collection.slug.startswith("js-acm-output-")
    }

    assert len(output_problems) == 63
    assert sorted(chapter_sizes.values()) == [7, 8, 8, 10, 10, 10, 10]
    for problem in output_problems.values():
        document = problem.document
        assert document.training_category.value == "output-format"
        assert document.test_set.checker_type.value == "exact"
        assert "### 正确示例" in document.description
        assert "### 常见错误示例" in document.description
        assert "exact checker" in document.description
        assert "精确输出要求" in document.output_description
        assert len(problem.cases) == 6


@pytest.mark.unit
def test_output_course_precision_bigint_and_buffering_examples_are_safe() -> None:
    bundle = load_content_bundle(CONTENT_ROOT / "manifest.yaml")

    rounded = bundle.problems["js-acm-output-decimal-rounding"].document
    safe_sum = bundle.problems["js-acm-output-floating-error-format"].document
    bigint = bundle.problems["js-acm-output-bigint-without-suffix"].document
    assert rounded.sample_output == "3.14\n"
    assert safe_sum.sample_output == "0.30\n"
    assert bigint.sample_output == "9007199254740993\n"
    assert not bigint.sample_output.rstrip().endswith("n")

    performance = [
        item.document
        for item in bundle.problems.values()
        if item.document.chapter == "js-acm-output-performance"
    ]
    assert len(performance) == 7
    for document in performance:
        node_path = CONTENT_ROOT / document.reference_solutions.nodejs
        v8_path = CONTENT_ROOT / document.reference_solutions.javascript_v8
        node_source = node_path.read_text(encoding="utf-8")
        v8_source = v8_path.read_text(encoding="utf-8")
        assert "console.log(" not in node_source
        assert node_source.count("process.stdout.write(") == 1
        assert v8_source.count("print(") == 1
