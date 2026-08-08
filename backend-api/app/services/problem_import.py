from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.problem import Problem, ProblemTag, Tag
from app.schemas.problem import ProblemCreate


class SeedTag(BaseModel):
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=50)


class SeedProblem(ProblemCreate):
    pass


class ProblemSeedDocument(BaseModel):
    tags: list[SeedTag] = Field(default_factory=list)
    problems: list[SeedProblem]


class ImportResult(BaseModel):
    tags_created: int = 0
    tags_updated: int = 0
    problems_created: int = 0
    problems_updated: int = 0


class SeedImportError(ValueError):
    pass


def load_seed_document(path: Path) -> ProblemSeedDocument:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SeedImportError(f"无法读取种子文件: {path}") from exc
    try:
        raw = json.loads(content) if path.suffix.lower() == ".json" else yaml.safe_load(content)
        return ProblemSeedDocument.model_validate(raw)
    except (json.JSONDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise SeedImportError(f"种子文件格式无效: {exc}") from exc


async def import_problem_seed(
    db: AsyncSession, document: ProblemSeedDocument
) -> ImportResult:
    result = ImportResult()
    tag_slugs = [tag.slug for tag in document.tags]
    problem_slugs = [problem.slug for problem in document.problems]
    if len(tag_slugs) != len(set(tag_slugs)):
        raise SeedImportError("种子文件包含重复的标签 slug")
    if len(problem_slugs) != len(set(problem_slugs)):
        raise SeedImportError("种子文件包含重复的题目 slug")

    existing_tags = {
        tag.slug: tag for tag in (await db.scalars(select(Tag))).all()
    }
    for seed_tag in document.tags:
        tag = existing_tags.get(seed_tag.slug)
        if tag is None:
            tag = Tag(slug=seed_tag.slug, name=seed_tag.name)
            db.add(tag)
            existing_tags[tag.slug] = tag
            result.tags_created += 1
        elif tag.name != seed_tag.name:
            tag.name = seed_tag.name
            result.tags_updated += 1
    await db.flush()

    existing_problems = {
        problem.slug: problem
        for problem in (
            await db.scalars(
                select(Problem).options(
                    selectinload(Problem.tag_links).selectinload(ProblemTag.tag)
                )
            )
        ).all()
    }
    for seed_problem in document.problems:
        missing_tags = sorted(set(seed_problem.tag_slugs) - set(existing_tags))
        if missing_tags:
            raise SeedImportError(
                f"题目 {seed_problem.slug} 引用了未知标签: {', '.join(missing_tags)}"
            )
        values = seed_problem.model_dump(exclude={"tag_slugs"})
        problem = existing_problems.get(seed_problem.slug)
        if problem is None:
            problem = Problem(**values)
            db.add(problem)
            existing_problems[problem.slug] = problem
            result.problems_created += 1
        else:
            for field_name, value in values.items():
                setattr(problem, field_name, value)
            result.problems_updated += 1
        existing_links = {link.tag.slug: link for link in problem.tag_links}
        links: list[ProblemTag] = []
        for tag_slug in seed_problem.tag_slugs:
            link = existing_links.get(tag_slug)
            links.append(
                link
                if link is not None
                else ProblemTag(tag_id=existing_tags[tag_slug].id)
            )
        problem.tag_links = links

    await db.commit()
    return result
